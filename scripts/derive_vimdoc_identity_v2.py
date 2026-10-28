"""Derive ViMDoc v2 canonical pages (one page per asset) from the C1-verified asset inventory.

Local and read-only on its input: no archive, OCR, qrels or query access. The
inventory bytes must match the C1 audit hash before any row is used.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

INVENTORY_SHA256 = 'fabee762b46b6aa3fd3402c784e2b5cf4b88148eac73d58245ab68c7c39ab1ad'
EXPECTED = {'pages': 76347, 'stems': 70080, 'stems_with_two_assets': 6267, 'documents': 1247}
EXTENSIONS = ('.jpg', '.jpeg', '.png')


def utf8_key(value):
    return value.encode('utf-8')


def page_row(asset):
    """v2 identity: the basename is the page ID; the stem gives document and page number."""
    path = asset['asset_path']
    if not path.startswith('pages/') or '/' in path[len('pages/'):]:
        raise ValueError(f'unexpected asset layout: {path!r}')
    name = path[len('pages/'):]
    stem, dot, extension = name.rpartition('.')
    if not dot or '.' + extension.lower() not in EXTENSIONS:
        raise ValueError(f'unexpected extension: {path!r}')
    document_id, sep, number = stem.rpartition('_')
    if not sep or not document_id or not number.isascii() or not number.isdecimal():
        raise ValueError(f'malformed page stem: {path!r}')
    if (stem, document_id, int(number)) != (asset['page_id'], asset['document_id'], asset['page_number']):
        raise ValueError(f'v2 identity disagrees with the C1 inventory: {path!r}')
    return {'page_id': name, 'page_stem': stem, 'document_id': document_id, 'page_number': int(number),
            'canonical_asset_path': path, 'asset_sha256': asset['asset_sha256'], 'asset_bytes': asset['asset_bytes']}


def derive(assets):
    pages = sorted((page_row(asset) for asset in assets), key=lambda row: utf8_key(row['page_id']))
    if len({row['page_id'] for row in pages}) != len(pages):
        raise ValueError('duplicate v2 page IDs')
    by_stem = defaultdict(list)
    for row in pages:
        by_stem[row['page_stem']].append(row['page_id'])
    for row in pages:
        row['stem_sibling_page_ids'] = [p for p in by_stem[row['page_stem']] if p != row['page_id']]
    counts = {'pages': len(pages), 'stems': len(by_stem),
              'stems_with_two_assets': sum(len(v) == 2 for v in by_stem.values()),
              'documents': len({row['document_id'] for row in pages})}
    if any(len(v) > 2 for v in by_stem.values()):
        raise ValueError('a stem has more than two assets')
    return pages, counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new create-once JSONL')
    args = parser.parse_args(argv)
    data = args.inventory.read_bytes()
    if hashlib.sha256(data).hexdigest() != INVENTORY_SHA256:
        raise ValueError('inventory bytes differ from the C1 audit hash')
    pages, counts = derive(json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip())
    if counts != EXPECTED:
        raise ValueError(f'v2 counts differ: {counts} != {EXPECTED}')
    payload = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                      for row in pages).encode('utf-8')
    with args.output.open('xb') as stream:
        stream.write(payload)
    print(json.dumps({**counts, 'canonical_pages_sha256': hashlib.sha256(payload).hexdigest(),
                      'bytes': len(payload), 'inventory_sha256': INVENTORY_SHA256}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f'v2 derivation refused: {exc}', file=sys.stderr)
        raise SystemExit(2)
