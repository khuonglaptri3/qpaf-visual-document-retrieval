"""Bind workbook M3.1 and accepted D1 inputs to a create-once, replayable pilot seal."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from qpaf.m24.config import METHODS, load_config
from qpaf.m24.dataset import SCORE_COLUMNS, build_records, read_score_rows, read_split_ids
from qpaf.m25.leakage import audit_score_rows
from qpaf.m27.binding import HANDOVER_HASHES, load_binding
from qpaf.m27.matched import _unique_pairs, load_base, load_manifest, resolve, semantic_diff
from qpaf.m31.parity import compare_views

SOURCE_FILES = (
    'src/qpaf/m31/seal.py', 'src/qpaf/m31/parity.py', 'scripts/seal_m31_inputs.py',
    'src/qpaf/m12/features.py', 'src/qpaf/m12/model.py', 'src/qpaf/m12/losses.py',
    'src/qpaf/m24/config.py', 'src/qpaf/m24/dataset.py', 'src/qpaf/m24/trainer.py',
    'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/checkpoint.py',
    'src/qpaf/m25/leakage.py', 'src/qpaf/m27/matched.py', 'src/qpaf/m27/binding.py',
    'scripts/run_m24_pipeline.py', 'requirements-learned-local.txt',
)
ROLES = ('train', 'validation', 'test')
NAMES = {'train': 'train_ids.txt', 'validation': 'val_ids.txt', 'test': 'test_ids.txt'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)


def _write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def _inside(root, relative):
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f'Path escapes its root: {relative}')
    return path


def _checked(root, reference):
    path = _inside(root, reference['path'])
    if not path.is_file() or sha(path) != reference['sha256']:
        raise ValueError(f'Missing file or hash drift: {reference["path"]}')
    return path


def _runtime(root):
    requirements = (Path(root)/'requirements-learned-local.txt').read_text(encoding='utf-8')
    pins = re.findall(r'^torch==([^\s]+)\s*$', requirements, re.MULTILINE)
    if len(pins) != 1 or version('torch') != pins[0]:
        raise ValueError('torch runtime differs from the matched CPU requirements')
    return {'python': sys.version.split()[0], 'platform': platform.platform(),
            **{name: version(name) for name in ('torch', 'numpy', 'pandas', 'pyarrow')}}


def workbook_task(path):
    """Read the authoritative Milestones row using only the standard library."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    with zipfile.ZipFile(path) as archive:
        strings = [''.join(item.itertext()) for item in
                   ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        relationships = {item.get('Id'): item.get('Target') for item in
                         ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets = ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns)
        sheet = next(item for item in sheets if item.get('name') == 'Milestones')
        target = relationships[sheet.get(rid)]
        member = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        for row in ET.fromstring(archive.read(member)).findall('.//s:row', ns):
            cells = {}
            for cell in row.findall('s:c', ns):
                value = cell.findtext('s:v', '', ns)
                if cell.get('t') == 's' and value:
                    value = strings[int(value)]
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(cell.find('s:is', ns).itertext())
                cells[''.join(c for c in cell.get('r') if c.isalpha())] = value
            if cells.get('D') == 'M3.1':
                if (cells.get('H') != 'Khương' or 'Dependency: D1' not in cells.get('I', '')
                        or any(word not in cells['I'] for word in ('cache/splits', 'rows', 'order', 'features', 'qrels'))):
                    raise ValueError('Workbook M3.1 scope/owner/dependency differs')
                return {'sheet': 'Milestones', 'row': int(row.get('r')), 'task_id': 'M3.1',
                        'owner': cells['H'], 'title': cells['E'], 'deliverable': cells['I']}
    raise ValueError('M3.1 is missing from the authoritative workbook')


def prerequisites(root, config):
    if set(config) != {'authority', 'binding', 'd1', 'prior_binding_verification'}:
        raise ValueError('Seal configuration must pin the workbook, binding, D1 and prior verification')
    paths = {name: _checked(root, ref) for name, ref in config.items()}
    task = workbook_task(paths['authority'])
    binding = load_binding(paths['binding'])
    d1, prior = read_json(paths['d1']), read_json(paths['prior_binding_verification'])
    if (d1.get('task_id') != 'M2.11' or d1.get('decision') != 'PASS'
            or d1.get('pilot_input_package_ready') is not True):
        raise ValueError('D1 has not accepted this pilot input package')
    accepted = d1['decision_basis']
    if (accepted['m2_7']['binding_sha256'] != config['binding']['sha256']
            or accepted['m2_7']['sha256'] != config['prior_binding_verification']['sha256']
            or accepted['m2_8']['sha256'] != binding['handover']['sha256']
            or prior.get('status') != 'PASS' or prior.get('binding_sha256') != config['binding']['sha256']
            or prior['real_row_parity'].get('identical') is not True
            or prior['real_row_parity'].get('training_executed') is not False):
        raise ValueError('D1/M2.7/M2.8 accepted-input lineage differs')
    matched_path = _checked(root, binding['matched_manifest'])
    matched = load_manifest(matched_path)
    _checked(root, matched['base_config'])
    for ref in matched['shared_inputs'].values():
        if isinstance(ref, dict):
            _checked(root, ref)
    base = load_base(matched, root)
    diff = semantic_diff(load_config(Path(root)/'configs/m2.4/pipeline.toml'), base)
    if set(diff) != {'experiment_id'} or diff['experiment_id'][1] != matched['experiment_id']:
        raise ValueError('Shared pilot base differs from the accepted M2.4 config')
    if {k: v['gate_granularity'] for k,v in matched['methods'].items()} != METHODS:
        raise ValueError('Matched gate mapping differs from the actual trainer')
    seed = matched['seeds']['development_gate']
    if semantic_diff(resolve(matched, 'QARF', seed, root), resolve(matched, 'QPAF', seed, root)) != {
            'gate_granularity': ['query', 'page']}:
        raise ValueError('Pilot configs differ beyond gate granularity')
    return task, binding, matched, base, prior


def audit_cache(scores, candidates, splits, cap):
    """Reject label-bearing schemas, key/order mismatch, duplicates and invalid scores."""
    import pyarrow.parquet as pq
    if pq.read_schema(scores).names != list(SCORE_COLUMNS):
        raise ValueError('Score schema must contain exactly the five label-free columns')
    if pq.read_schema(candidates).names != ['query_id', 'page_id']:
        raise ValueError('Invalid candidate schema')
    rows = read_score_rows(scores)
    keys = [(r['query_id'], r['page_id']) for r in rows]
    candidate_keys = [(r['query_id'], r['page_id']) for r in pq.read_table(candidates).to_pylist()]
    if not keys or keys != candidate_keys or len(set(keys)) != len(keys):
        raise ValueError('Frozen candidate keys/order differ from score rows')
    audit = audit_score_rows(rows, splits, roles=ROLES, max_candidates=cap)
    return audit


def _data_check(root, output, inputs, binding, matched, base, prior):
    paths = {name: _checked(output, ref) for name, ref in inputs.items()}
    handover = read_json(paths['handover'])
    if (handover.get('status') != 'PASS' or handover.get('policy_id') != binding['policy_id']
            or handover.get('run_id') != binding['source_run_id']
            or handover.get('uncovered_query_ids') != []
            or handover.get('macro_candidate_recall', 0) < 0.95
            or not 0 < handover.get('max_candidates_per_query', 0) <= base['data']['max_candidates']):
        raise ValueError('M2.8 handover has not passed the pilot candidate gate')
    for name, field in HANDOVER_HASHES.items():
        if inputs[name]['sha256'] != handover.get(field):
            raise ValueError(f'{name}: handover hash differs')
    splits = read_split_ids(paths['split_train'].parent)
    master = read_json(Path(root)/matched['shared_inputs']['split_manifest']['path'])
    if master.get('status') != 'VERIFIED_ACTIVE_PRIMARY_SPLITS':
        raise ValueError('Split roles have not been frozen by M2.1')
    for role in ROLES:
        ref = inputs['split_'+role]
        accepted = master['roles'][role]
        if (ref['sha256'] != accepted['sha256'] or len(splits[role]) != accepted['count']
                or handover['split_role_sha256'][role] != ref['sha256']):
            raise ValueError(f'{role}: frozen split hash/count differs')
    audit = audit_cache(paths['score_cache'], paths['candidate_set'], splits, base['data']['max_candidates'])
    if audit['candidate_count'] != handover['candidate_count']:
        raise ValueError('Candidate row count differs from the accepted handover')
    if 'm24_m25_row_audit' in handover and audit != handover['m24_m25_row_audit']:
        raise ValueError('Candidate keys differ from the accepted M2.8 row audit')
    qrels = read_json(paths['qrels_development'])
    if set(qrels) != set(splits['train']) | set(splits['validation']):
        raise ValueError('Development qrels include missing, unknown or sealed-test queries')
    queries = read_json(paths['query_texts'])
    views = {}
    for method in ('QARF', 'QPAF'):
        views[method] = build_records(read_score_rows(paths['score_cache']), queries, qrels, splits,
                                     ('train', 'validation'),
                                     positive_threshold=base['data']['positive_threshold'],
                                     max_candidates=base['data']['max_candidates'])
        for role, records in views[method].items():
            if any(not any(record.labels) for record in records):
                raise ValueError(f'{role}: a query has no positive candidate')
    parity = compare_views(views, base)
    coverage = {}
    for role, records in views['QARF'].items():
        recall = sum(sum(record.labels)/record.relevant_total for record in records)/len(records)
        if recall < 0.95:
            raise ValueError(f'{role}: development candidate macro recall is below 0.95')
        coverage[role] = {'macro_candidate_recall': recall, 'uncovered_queries': 0,
                          'captured_relevant': sum(sum(record.labels) for record in records),
                          'relevant_total': sum(record.relevant_total for record in records)}
    parity['development_coverage'] = coverage
    historical = prior['real_row_parity'].get('seeds', {}).get(str(parity['seed']))
    if historical:
        observed = parity['methods']['QARF']['train']
        if any(observed[key] != historical[key] for key in ('batches', 'batch_order_sha256')):
            raise ValueError('Real batch order differs from accepted M2.7-003')
    return audit, parity


def _copy(root, ref, output, relative):
    source = _checked(root, ref)
    target = _inside(output, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    if sha(target) != ref['sha256']:
        raise ValueError(f'Input changed during sealing: {ref["path"]}')
    return {'path': relative, 'origin_path': ref['path'], 'sha256': ref['sha256'],
            'size_bytes': target.stat().st_size}


def seal_inputs(root, payload_root, output, config):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Pilot seal is create-once: {output}')
    task, binding, matched, base, prior = prerequisites(root, config)
    environment = _runtime(root)
    output.mkdir(parents=True, exist_ok=False)
    _write(output/'_ATTEMPTED.json', {'task_id': 'M3.1', 'started_utc': datetime.now(timezone.utc).isoformat()})
    try:
        sources = {path: sha(_inside(root, path)) for path in SOURCE_FILES}
        inputs = {}
        for name, ref in binding['inputs'].items():
            suffix = Path(ref['path']).suffix
            inputs[name] = _copy(payload_root, ref, output, f'inputs/{name}{suffix}')
        for role, ref in binding['splits'].items():
            inputs['split_'+role] = _copy(payload_root, ref, output, 'inputs/splits/'+NAMES[role])
        inputs['handover'] = _copy(payload_root, binding['handover'], output, 'inputs/handover.json')
        inputs['shared_base'] = _copy(root, matched['base_config'], output, 'inputs/shared_base.toml')
        inputs['matched_manifest'] = _copy(root, binding['matched_manifest'], output, 'inputs/matched.json')
        audit, parity = _data_check(root, output, inputs, binding, matched, base, prior)
        for path, expected in sources.items():
            if sha(root/path) != expected:
                raise ValueError(f'Source changed during sealing: {path}')
        git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
        report = {'schema_version': 1, 'task_id': 'M3.1', 'status': 'PASS', 'owner': task['owner'],
                  'workbook_task': task, 'policy_id': binding['policy_id'], 'source_run_id': binding['source_run_id'],
                  'row_audit': audit, 'parity': parity, 'training_executed': False,
                  'test_labels_opened': False, 'test_ranking_metrics_computed': False,
                  'pilot_execution_authorized': False, 'independent_human_review': 'PENDING'}
        _write(output/'verification.json', report)
        manifest = {'schema_version': 'qpaf_m31_pilot_seal_v1', 'task_id': 'M3.1',
                    'authority_config': config, 'inputs': inputs, 'source_sha256': sources,
                    'source_commit': git.stdout.strip() if git.returncode == 0 else None,
                    'environment': environment,
                    'verification_sha256': sha(output/'verification.json')}
        _write(output/'manifest.json', manifest)
        _write(output/'_SUCCESS.json', {'manifest_sha256': sha(output/'manifest.json'),
                                       'verification_sha256': manifest['verification_sha256']})
        return report
    except Exception as exc:
        _write(output/'failure.json', {'status': 'FAILED', 'type': type(exc).__name__, 'message': str(exc)})
        raise


def verify_seal(root, output, *, expected_manifest_sha256):
    """Read-only replay; no original payload location, optimizer or test-label parser."""
    root, output = Path(root), Path(output)
    if not isinstance(expected_manifest_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256):
        raise ValueError('An external 64-character manifest SHA-256 pin is required')
    _checked(output, {'path': 'manifest.json', 'sha256': expected_manifest_sha256})
    marker = read_json(output/'_SUCCESS.json')
    if marker['manifest_sha256'] != expected_manifest_sha256:
        raise ValueError('Local marker differs from the external manifest pin')
    _checked(output, {'path': 'manifest.json', 'sha256': marker['manifest_sha256']})
    manifest = read_json(output/'manifest.json')
    if manifest.get('schema_version') != 'qpaf_m31_pilot_seal_v1':
        raise ValueError('Unsupported pilot seal schema')
    if manifest['verification_sha256'] != marker['verification_sha256']:
        raise ValueError('Pilot seal verification hash differs')
    _checked(output, {'path': 'verification.json', 'sha256': marker['verification_sha256']})
    report = read_json(output/'verification.json')
    task, binding, matched, base, prior = prerequisites(root, manifest['authority_config'])
    if set(manifest['source_sha256']) != set(SOURCE_FILES):
        raise ValueError('Pilot source inventory differs')
    for path, expected in manifest['source_sha256'].items():
        _checked(root, {'path': path, 'sha256': expected})
    environment = _runtime(root)
    if any(environment[name] != manifest['environment'][name] for name in ('torch', 'numpy', 'pandas', 'pyarrow')):
        raise ValueError('Numerical runtime differs from the sealed environment')
    expected_inputs = {**binding['inputs'], **{'split_'+k:v for k,v in binding['splits'].items()},
                       'handover': binding['handover'], 'shared_base': matched['base_config'],
                       'matched_manifest': binding['matched_manifest']}
    if set(expected_inputs) != set(manifest['inputs']):
        raise ValueError('Pilot input inventory differs')
    for name, ref in expected_inputs.items():
        if manifest['inputs'][name]['sha256'] != ref['sha256']:
            raise ValueError(f'{name}: seal differs from the accepted input hash')
    audit, parity = _data_check(root, output, manifest['inputs'], binding, matched, base, prior)
    if (audit != report['row_audit'] or parity != report['parity'] or task != report['workbook_task']
            or report.get('status') != 'PASS' or report.get('training_executed') is not False
            or report.get('test_labels_opened') is not False):
        raise ValueError('Pilot input parity replay differs from the sealed evidence')
    return report
