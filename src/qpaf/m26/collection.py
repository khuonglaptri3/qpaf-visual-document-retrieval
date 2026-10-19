"""Atomic local extraction and explicit partial snapshots after worker termination."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from qpaf.m11.artifacts import digest, file_manifest, read_json, utc, write_json
from qpaf.m23.policy import load_frozen_policy
from .bundle import checked_path, validate_records
from .config import validate


def atomic_payload(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_bytes(payload)
    temporary.replace(path)


def collect_partial(folder, volume):
    """Download committed terminal records; never publish a complete-run receipt."""
    folder = Path(folder)
    config = validate(read_json(folder / 'resolved_config.json'))
    inputs = read_json(folder / 'input_manifest.json')
    expected = {r['page_id']: r for r in inputs['scheduled_pages']}
    policy = load_frozen_policy(folder / 'ocr_policy_frozen.toml', config['policy']['sha256'])
    remote = 'runs/' + folder.name + '/output/'
    output = folder / 'partial-output'
    output.mkdir(exist_ok=True)
    entries = [entry.path.lstrip('/') for entry in volume.iterdir('/' + remote + 'pages', recursive=True)
               if entry.path.endswith('/record.json')]

    def saved(path, payload, sha=None):
        if sha is not None and hashlib.sha256(payload).hexdigest() != sha:
            raise ValueError('Committed partial artifact checksum mismatch')
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError('Committed terminal partial artifact changed')
        else:
            atomic_payload(path, payload)

    def collect_record(name):
        if not name.startswith(remote):
            raise ValueError('Partial record escapes the run namespace')
        payload = b''.join(volume.read_file('/' + name))
        row = json.loads(payload)
        if row['page_id'] not in expected or row['policy_sha256'] != config['policy']['sha256']:
            raise ValueError('Partial record has an unknown page/policy')
        relative = name[len(remote):]
        if relative != 'pages/' + row['page_id'] + '/record.json':
            raise ValueError('Partial record path differs from its page ID')
        for item in row['artifacts'].values():
            path = checked_path(output, item['path'])
            data = b''.join(volume.read_file('/' + remote + item['path']))
            if len(data) != item['size_bytes']:
                raise ValueError('Committed partial artifact size mismatch')
            saved(path, data, item['sha256'])
        saved(checked_path(output, relative), payload)
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = sorted(pool.map(collect_record, entries), key=lambda r: r['page_id'])
    if rows:
        validate_records(rows, [expected[r['page_id']] for r in rows], output, policy,
                         config['policy']['sha256'], maximum_fraction=1.)
    found = {r['page_id'] for r in rows}
    incomplete = sorted(set(expected) - found)
    failures = [r for r in rows if r['technical_failure']] + [
        {**expected[page_id], 'technical_failure': True, 'extraction_status': 'NO_COMMITTED_TERMINAL_RECORD',
         'reason': 'Worker interrupted or record not committed; execution completion is unknown'} for page_id in incomplete]
    write_json(output / 'resolved_pages.json', rows)
    write_json(output / 'failures.json', failures)
    write_json(output / 'hashes.json', file_manifest(output, exclude=('hashes.json',)))
    receipt = {'status': 'PARTIAL_NOT_COMPLETE', 'run_id': folder.name, 'collected_utc': utc(),
               'scheduled_pages': len(expected), 'completed_records_verified': len(rows),
               'incomplete_page_ids': incomplete, 'policy_sha256': config['policy']['sha256'],
               'partial_hash_manifest_sha256': digest(output / 'hashes.json'),
               'note': 'Committed raw evidence retained. This snapshot does not complete M2.6.'}
    write_json(folder / 'partial_collection.json', receipt)
    print(f"Partial snapshot: {len(rows)}/{len(expected)} terminal records; saved to {output}", flush=True)
    return receipt
