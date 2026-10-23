"""Create/replay M4.2 preparation evidence; never load real query text or qrels.

Technical PASS means settings, sealed ID inputs and software fixtures verify.
Real-input readiness remains BLOCKED: this command cannot extract, train, fit
real weights, select baselines or open confirmation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qpaf.m42.baselines import ROSTER, fit_static_on_train, document_ndcg_at_10
from qpaf.m42 import baselines as _baseline_api

# The fixtures must run the same source bytes recorded in the target manifest.
EXECUTING_BASELINES_SHA256 = hashlib.sha256(Path(_baseline_api.__file__).read_bytes()).hexdigest()

M41 = 'evidence/revisions/m4.1-001/manifest.json'
M41_SHA256 = '03673b16ef666c6d8756939efebdbcc73ff1c61a5abcff6c743400e5da6c4668'
CONFIG = 'configs/m4.2/freeze.json'
CONFIG_SHA256 = 'b100cb62103e25bab6d7273573d4b568592cd10ba97db4865f7d8ffffde90f64'
RESEARCH = 'docs/03_method/m4.2-baseline-research.md'
POLICIES = tuple('evidence/M1_FINAL/02_protocol/'+name+'.md' for name in (
    'frozen_protocol', 'dataset_split_policy', 'metric_policy', 'statistical_policy',
    'baseline_policy', 'candidate_policy', 'seed_policy', 'run_policy'))
INPUTS = (
    CONFIG, M41,
    'evidence/revisions/m4.1-001/train_ids.txt',
    'evidence/revisions/m4.1-001/validation_ids.txt',
    'evidence/revisions/m4.1-001/confirmation_ids.txt',
    'evidence/revisions/m3.7-001/decision.json',
    'evidence/revisions/m3.7-001/owner_confirmation.json',
    'artifacts/dataset_materialization_vimdoc.json',
    'artifacts/score_input_probe_vimdoc.json',
    'configs/m2.5/freeze.json', 'configs/environment.yaml',
    'configs/vimdoc_m3_local_v1.json',
    'docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx',
    'src/qpaf/m42/__init__.py', 'src/qpaf/m42/baselines.py',
    'scripts/freeze_m42_baselines.py', 'tests/test_m42_baselines.py',
    'tests/test_m42_freeze.py', RESEARCH,
    *POLICIES,
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _fixture():
    # Synthetic, hand-checkable software checks; these are NOT real metrics.
    rows = [dict(query_id='synthetic_train', page_id=page, bm25_score=scores[0],
                 dense_score=scores[1], visual_score=scores[2])
            for page, scores in [('a_0', (10., 0., 0.)), ('b_0', (0., 10., 10.))]]
    fitted = fit_static_on_train(rows, {'synthetic_train': ['b']}, ['synthetic_train'])
    require(fitted['weights'] == (0., 0., 1.) and fitted['grid_candidates'] == 66,
            'synthetic static fit failed')
    require(document_ndcg_at_10(['a_0', 'a_1'], [1., .5], ['a']) == 1.,
            'synthetic document aggregation failed')
    try:
        fit_static_on_train(rows, {'synthetic_train': ['b'], 'validation': ['a']},
                            ['synthetic_train'])
    except ValueError:
        pass
    else:
        raise ValueError('synthetic train-only barrier failed')
    return {'scope': 'synthetic_software_only', 'document_aggregation': 'PASS',
            'train_only_barrier': 'PASS', 'static_grid_points': 66,
            'real_metrics_computed': False}


def build_manifest(root):
    root = Path(root).resolve()
    # A reviewed v1 freeze is exact, including required keys and access flags.
    # Any changed setting needs a versioned, reviewed configuration and pin.
    require(sha(root/CONFIG) == CONFIG_SHA256, 'M4.2 frozen config hash differs')
    require(sha(root/'src/qpaf/m42/baselines.py') == EXECUTING_BASELINES_SHA256,
            'fixture implementation hash differs from inventoried implementation')
    require(sha(root/M41) == M41_SHA256, 'M4.1 manifest hash differs from merged PR #33')
    seal, config = read(root/M41), read(root/CONFIG)
    require(set(seal['evaluation']['policy_sha256']) == set(POLICIES), 'policy inventory differs')
    for name, digest in seal['evaluation']['policy_sha256'].items():
        require(sha(root/name) == digest, f'policy hash drift: {name}')
    for name, key in [('decision.json', 'decision_sha256'),
                       ('owner_confirmation.json', 'owner_confirmation_sha256')]:
        require(sha(root/'evidence/revisions/m3.7-001'/name) == seal['g2'][key],
                f'G2 hash drift: {name}')
    require(sha(root/'artifacts/dataset_materialization_vimdoc.json') ==
            seal['dataset']['historical_receipt_sha256'], 'historical receipt hash drift')
    groups = {}
    for role, count in [('train', 1600), ('validation', 400), ('confirmation', 8904)]:
        path = root/f'evidence/revisions/m4.1-001/{role}_ids.txt'
        spec = seal['split']['files'][path.name]
        require(sha(path) == spec['sha256'], f'{role} split hash drift')
        ids = path.read_text(encoding='utf8').splitlines()
        require(len(ids) == len(set(ids)) == spec['count'] == count and all(ids),
                f'{role} split count/uniqueness differs')
        groups[role] = set(ids)
    require(not (groups['train'] & groups['validation'] or
                 groups['train'] & groups['confirmation'] or
                 groups['validation'] & groups['confirmation']), 'split overlap')
    require(len(set.union(*groups.values())) == 10904, 'split union differs')
    inherited = read(root/'configs/m2.5/freeze.json')
    require(config['task_id'] == 'M4.2' and config['dataset'] == seal['dataset']['id'] and
            config['dataset_revision'] == seal['dataset']['revision'], 'dataset/settings identity differs')
    require(config['evaluation'] == {k: seal['evaluation'][k] for k in config['evaluation']},
            'M4.1 document evaluation differs')
    require(config['required_deployable_baselines'] == list(ROSTER) ==
            inherited['required_deployable_baselines'], 'required baseline roster differs')
    require(config['static_fit']['grid_denominator'] == inherited['static_fit']['grid_denominator'] == 10 and
            config['static_fit']['grid_candidates'] == 66 and
            config['static_fit']['partition'] == 'exact_m41_train_ids_only' and
            config['static_fit']['objective'] == 'mean_train_document_ndcg_at_10' and
            config['static_fit']['real_fitted_weights'] is None, 'static settings differ')
    require(config['rrf']['k'] == inherited['rrf_k'] == 60 and
            config['rrf']['parameter_fitting'] is False and
            config['normalization']['range_epsilon'] == 1e-15 and
            config['shared_candidates']['union_cap'] == 600, 'score settings differ')
    require(all(v is None for v in config['real_inputs'].values()),
            'this preparation cannot assert real input verification')
    require(all(v is False for k, v in config['access'].items() if k != 'owner_acceptance') and
            config['access']['owner_acceptance'] == 'PENDING', 'real execution/acceptance is not part of this package')
    return {
        'schema_version': 1, 'task_id': 'M4.2', 'owner': config['owner'],
        'status': 'PREPARED_SETTINGS_REAL_INPUTS_PENDING', 'settings_check': 'PASS',
        'base_commit': '5bbb2ded966ac53328109358420c9bc9f731eb58',
        'm41_manifest_sha256': M41_SHA256,
        'splits': {'counts': {k: len(v) for k, v in groups.items()}, 'query_overlap': 0,
                   'union_count': 10904},
        'files': [{'path': name, 'sha256': sha(root/name)} for name in INPUTS],
        'software_fixture': _fixture(),
        'real_input_readiness': 'BLOCKED',
        'missing_real_inputs': sorted(config['real_inputs']),
        'real_fitted_weights': None, 'strongest_baseline_selection': None,
        'historical_probe_is_live_verification': False,
        'real_training_or_static_fit_executed': False,
        'confirmation_labels_opened': False, 'm42_accepted': False,
    }


def verification(manifest):
    return {'task_id': 'M4.2', 'status': 'PASS',
            'scope': 'sealed_IDs_settings_hashes_and_synthetic_software_only',
            'files_verified': len(manifest['files']),
            'split_counts': manifest['splits']['counts'],
            'software_fixture': manifest['software_fixture'],
            'real_input_readiness': 'BLOCKED', 'm42_accepted': False,
            'real_metrics_computed': False, 'confirmation_labels_opened': False}


def _json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode('utf8')


def create(root, output):
    root, output = Path(root), Path(output)
    require(not output.exists(), 'output directory already exists')
    manifest = build_manifest(root)
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in [('manifest.json', _json_bytes(manifest)),
                           ('verification.json', _json_bytes(verification(manifest))),
                           ('README.md', (root/RESEARCH).read_bytes())]:
        with (output/name).open('xb') as handle:
            handle.write(payload)


def verify(root, output):
    root, output = Path(root), Path(output)
    manifest = build_manifest(root)
    require((output/'manifest.json').read_bytes() == _json_bytes(manifest),
            'committed M4.2 manifest differs (source/config/inventory drift)')
    result = verification(manifest)
    require((output/'verification.json').read_bytes() == _json_bytes(result),
            'committed verification differs')
    require((output/'README.md').read_bytes() == (root/RESEARCH).read_bytes(), 'research README differs')
    require(sorted(p.name for p in output.iterdir()) == ['README.md', 'manifest.json', 'verification.json'],
            'unexpected/missing revision artifact')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.root, args.output_dir)
        else:
            create(args.root, args.output_dir)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'M4.2 refused: {exc}\n')
    print('M4.2 preparation verification: PASS; real-input readiness: BLOCKED; confirmation closed')


if __name__ == '__main__':
    main()
