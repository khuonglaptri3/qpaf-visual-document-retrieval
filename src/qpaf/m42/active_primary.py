"""Complete A002 active-primary baseline inputs/settings; keep confirmation sealed."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np

from qpaf.m24.dataset import CHANNELS, SCORE_COLUMNS, build_records, read_score_rows
from qpaf.m24.evaluator import evaluate
from qpaf.m25.baselines import ROSTER, fit_static_on_train, predictions
from qpaf.m25.leakage import verify_frozen_splits

ROOT = Path(__file__).resolve().parents[3]
CONFIG = 'configs/m4.2/active_primary.json'
CONFIG_SHA256 = 'aa262486195e7242c3beb69cf0f4bc73191dbcafb7297ffebb7451ee8faba17f'
SOURCE_FILES = (CONFIG, 'src/qpaf/m42/active_primary.py', 'scripts/run_m42_active_primary.py',
                'tests/test_m42_active_primary.py', 'src/qpaf/m25/baselines.py',
                'src/qpaf/m25/leakage.py', 'src/qpaf/m24/dataset.py',
                'src/qpaf/m24/evaluator.py', 'src/qpaf/m24/config.py')
EXECUTING_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'), object_pairs_hook=_unique)


def write_json(path, data):
    with Path(path).open('x', encoding='utf8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def inside(root, relative):
    root, relative = Path(root).resolve(), Path(relative)
    path = (root/relative).resolve()
    require(not relative.is_absolute() and path.is_relative_to(root), 'Path escapes artifact root')
    return path


def audit_tables(raw, normalized, candidates, top_lists, expansion, query_ids, *, top_k=200, cap=600):
    """Replay label-free common rows, accepted expansion, ranks and normalization."""
    require(isinstance(query_ids, (list, tuple)) and query_ids and
            len(set(query_ids)) == len(query_ids), 'Invalid or duplicate frozen query IDs')
    require(raw.column_names == list(SCORE_COLUMNS) == normalized.column_names,
            'Only the exact five label-free score columns are allowed')
    require(candidates.column_names == ['query_id', 'page_id'], 'Candidate schema differs')
    keys = raw.select(['query_id', 'page_id'])
    require(keys.equals(candidates) and keys.equals(normalized.select(keys.column_names)),
            'Candidate/raw/normalized keys or order differ')
    frame, norm = raw.to_pandas(), normalized.to_pandas()
    require(len(frame) > 0 and not frame[['query_id','page_id']].duplicated().any(), 'Duplicate/empty rows')
    require(set(frame.query_id) == set(query_ids) and
            all(isinstance(p,str) and p for p in frame.page_id), 'Missing/orphan query or invalid page')
    values, supplied = frame[list(CHANNELS)].to_numpy(), norm[list(CHANNELS)].to_numpy()
    require(values.dtype == np.dtype('float64') and supplied.dtype == np.dtype('float64') and
            np.isfinite(values).all() and np.isfinite(supplied).all(), 'Require finite float64 scores')
    max_difference, max_count = 0., 0
    for indices in frame.groupby('query_id', sort=False).indices.values():
        require(0 < len(indices) <= cap, 'Candidate cap exceeded')
        pages = frame.page_id.iloc[indices].tolist()
        require(pages == sorted(pages), 'Candidate page order differs')
        scores = values[indices]
        low, span = scores.min(axis=0), np.ptp(scores, axis=0)
        require(np.isfinite(span).all(), 'Score normalization overflow')
        require(not np.any((span > 0) & (span <= 1e-15)),
                'Near-zero range requires review: frozen M2.5 and cache semantics differ')
        expected = np.divide(scores-low, span, out=np.zeros_like(scores), where=span > 1e-15)
        max_difference = max(max_difference, float(np.abs(expected-supplied[indices]).max()))
        max_count = max(max_count, len(indices))
    require(max_difference <= 1e-12, 'Cached normalization differs from common union replay')
    top = top_lists.to_pandas()
    require(top_lists.column_names == ['query_id','page_id','channel','rank','raw_score'],
            'Top-list schema differs')
    require(set(top.query_id) == set(query_ids) and set(top.channel) == {'bm25','dense','visual'},
            'Top-list query/channel roster differs')
    require(len(top) == len(query_ids)*3*top_k and np.isfinite(top.raw_score).all(),
            'Incomplete/nonfinite top lists')
    require(top['rank'].dtype.kind in 'iu','Top-list ranks must be integers')
    require(not top[['query_id','channel','page_id']].duplicated().any(), 'Duplicate top-list page')
    for _, group in top.groupby(['query_id','channel'], sort=False):
        ranked = group.sort_values('rank')
        require(ranked['rank'].tolist() == list(range(1,top_k+1)), 'Top-list ranks differ')
        ordered = group.sort_values(['raw_score','page_id'], ascending=[False,True])
        require(ranked.page_id.tolist() == ordered.page_id.tolist(), 'Top-list score/tie order differs')
    for channel, column in zip(('bm25','dense','visual'),CHANNELS):
        channel_rows = top[top.channel==channel]
        joined = channel_rows.merge(frame[['query_id','page_id',column]],
                                    on=['query_id','page_id'],validate='one_to_one')
        require(len(joined)==len(channel_rows) and
                np.allclose(joined.raw_score,joined[column],rtol=0,atol=1e-12),
                'Top-list raw score differs from common rescored cache')
    extra = expansion.select(['query_id','page_id']).to_pandas()
    require(set(extra.query_id) <= set(query_ids) and not extra.duplicated().any(),
            'Invalid expansion keys')
    base = top[['query_id','page_id']].drop_duplicates()
    require(base.merge(extra, on=['query_id','page_id']).empty, 'Expansion repeats base candidates')
    union = np.concatenate((base.to_numpy(), extra.to_numpy()), axis=0)
    require(set(map(tuple,union)) == set(map(tuple,frame[['query_id','page_id']].to_numpy())),
            'Candidates differ from accepted top-list plus expansion union')
    return {'status':'PASS','query_count':len(query_ids),'candidate_rows':len(frame),
            'max_candidates_per_query':max_count,'expanded_rows':len(extra),
            'normalization_max_abs_difference':max_difference,'label_access':False}


def fit_train_records(records, train_ids):
    require(isinstance(train_ids,(list,tuple)) and train_ids and
            all(isinstance(q,str) and q for q in train_ids) and len(set(train_ids))==len(train_ids),
            'Exact ordered frozen train IDs required')
    require([r.query_id for r in records] == list(train_ids), 'Fit records must be exact TRAIN IDs/order')
    return fit_static_on_train(records, list(train_ids), denominator=10)


def baseline_contracts(shared_sha256, weights, checkpoint_sha256):
    methods = {}
    for index, method in enumerate(ROSTER):
        entry = {'shared_inputs_sha256':shared_sha256, 'evaluation_unit':'page',
                 'evaluator':'qpaf.m24.evaluator.evaluate', 'rank_tie_break':'page_id_ascending'}
        if index < 3: entry['channel'] = CHANNELS[index]
        elif method == 'uniform_combsum': entry['weights'] = [1/3]*3
        elif method == 'rrf_k60':
            entry.update(rank_constant=60, rank_start=1, rank_scope='common_rescored_union', fitting=False)
        elif method == 'train_fitted_static': entry.update(weights=list(weights), fitting='train_only')
        else: entry.update(checkpoint_sha256=checkpoint_sha256,seed=20260820,gate_granularity='query')
        methods[method] = entry
    return methods


def reserve_attempt(output, authorization):
    output = Path(output)
    require(not output.exists(), 'Attempt output already exists; automatic retry/overwrite is forbidden')
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'_ATTEMPTED.json',authorization)


def prepare_context(root):
    import pyarrow.parquet as pq
    root = Path(root).resolve()
    require(root==ROOT.resolve(),'M4.2 must run from the executing checkout')
    require(sha(root/CONFIG)==CONFIG_SHA256, 'Frozen active-primary config hash differs')
    require(sha(root/'src/qpaf/m42/active_primary.py')==EXECUTING_SOURCE_SHA256,
            'Executing implementation differs from inventoried source')
    config = read(root/CONFIG)
    for ref in config['references'].values():
        require(sha(inside(root,ref['path']))==ref['sha256'], f'Source/input hash drift: {ref["path"]}')
    source_manifest = read(root/config['references']['m31_manifest']['path'])
    freeze = read(root/config['references']['m25_freeze']['path'])
    split_check = verify_frozen_splits(root,freeze)
    splits = split_check['roles']
    refs = {key:{'path':ref['origin_path'],'sha256':ref['sha256']}
            for key,ref in source_manifest['inputs'].items()}
    candidate_freeze = read(root/refs['candidate_freeze']['path'])
    parent = Path(refs['candidate_freeze']['path']).parent
    for name, ref in candidate_freeze['artifacts'].items():
        refs['artifact_'+Path(name).stem] = {'path':(parent/name).as_posix(),'sha256':ref['sha256']}
    refs['qarf_checkpoint'] = config['references']['qarf_checkpoint']
    for ref in refs.values():
        require(sha(inside(root,ref['path']))==ref['sha256'], f'Payload hash drift: {ref["path"]}')
    handover = read(root/refs['handover']['path'])
    require(handover['status']=='PASS' and handover['evaluation_unit']=='page' and
            handover['policy_id']=='qpaf_m28_top_document_expansion_v1' and
            handover['score_cache_sha256']==refs['score_cache']['sha256'], 'Accepted M3 handover differs')
    g2 = read(root/config['references']['g2_decision']['path'])
    require(g2['decision']=='GO' and g2['m4_branch']=='continue_qpaf','Confirmed G2 branch differs')
    qarf_review = read(root/config['references']['qarf_acceptance']['path'])
    require(qarf_review['decision']=='ACCEPTED','Matched learned QARF has no accepted review')
    table = lambda key: pq.read_table(root/refs[key]['path'])
    audit = audit_tables(table('score_cache'),table('artifact_normalized_scores'),
                         table('candidate_set'),table('artifact_channel_top_lists'),
                         table('artifact_candidate_expansion_log'),
                         [q for role in ('train','validation','test') for q in splits[role]])
    require(audit['candidate_rows']==handover['candidate_count'],'Candidate row count differs')
    return config, refs, splits, audit


def _train_records(input_root, refs, splits):
    qrels = read(input_root/refs['qrels_development']['path'])
    require(set(qrels)==set(splits['train'])|set(splits['validation']),
            'Development qrels must contain train/validation only; test labels forbidden')
    # Fit receives no validation labels or records, even though the source dev
    # qrels file is role-audited as in the accepted M3.1 bundle.
    train_qrels = {q:qrels[q] for q in splits['train']}
    records = build_records(read_score_rows(input_root/refs['score_cache']['path']),
                            read(input_root/refs['query_texts']['path']), train_qrels, splits, ('train',))['train']
    require(all(any(r.labels) for r in records),'Train query lacks positive candidates')
    recall = sum(sum(r.labels)/r.relevant_total for r in records)/len(records)
    require(recall>=.95,'Train candidate coverage below frozen gate')
    return records, {'query_count':len(records),'candidate_rows':sum(len(r.page_ids) for r in records),
                     'macro_relevant_page_recall':recall,'uncovered_queries':0}


def execute(root, output, authorization, expected_authorization_sha256):
    root, output, authorization = Path(root).resolve(),Path(output).resolve(),Path(authorization)
    require(sha(authorization)==expected_authorization_sha256,'Authorization hash differs')
    approval = read(authorization)
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    require(approval['source_commit']==commit and approval['task_id']=='M4.2' and
            approval['invocations']==1 and approval['retries']==0 and
            output==inside(root,approval['output_directory']), 'Authorization scope/commit/output differs')
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True),
            'Result-bearing execution requires a clean tracked source commit')
    config, refs, splits, audit = prepare_context(root)
    require(approval['config_sha256']==sha(root/CONFIG),'Authorization config differs')
    reserve_attempt(output,approval)
    start = time.monotonic()
    try:
        # Seal identical payloads under one portable common-input namespace.
        copied, by_source = {}, {}
        for key,ref in refs.items():
            if key=='qrels_test_sealed':
                continue  # Its bytes are hashed above, never parsed or included in fitting.
            source = ref['path']
            if source not in by_source:
                # Short portable paths avoid duplicating historical run IDs.
                name = ('inputs/splits/'+Path(source).name if key.startswith('split_') else
                        'inputs/learned_qarf/best.pt' if key=='qarf_checkpoint' else
                        'inputs/'+Path(source).name)
                target = inside(output,name)
                target.parent.mkdir(parents=True,exist_ok=True)
                with (root/source).open('rb') as incoming,target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming,outgoing)
                require(sha(target)==ref['sha256'],'Input changed while sealing')
                by_source[source] = name
            copied[key] = {'path':by_source[source],'sha256':ref['sha256']}
        records, coverage = _train_records(output,copied,splits)
        print(f'M4.2: fitting frozen 66-point grid on {len(records)} TRAIN queries',flush=True)
        fitted = fit_train_records(records,splits['train'])
        require(time.monotonic()-start <= approval['timeout_seconds'],'CPU wall-time cap exceeded')
        shared = {'dataset':config['dataset'],'evaluation_unit':'page','inputs':copied,
                  'split_counts':{r:len(ids) for r,ids in splits.items()},
                  'sealed_test_qrels_sha256':refs['qrels_test_sealed']['sha256']}
        write_json(output/'shared_inputs.json',shared)
        write_json(output/'train_fit.json',fitted)
        write_json(output/'baseline_contracts.json',baseline_contracts(
            sha(output/'shared_inputs.json'),fitted['weights'],refs['qarf_checkpoint']['sha256']))
        write_json(output/'input_audit.json',{'common_inputs':audit,'train_coverage':coverage})
        write_json(output/'access.json',{'fit_query_count':len(records),'fit_partition':'train_only',
            'development_qrels_deserialized_for_role_audit':True,'validation_metrics_computed':False,
            'test_labels_deserialized':False,'vimdoc_confirmation_accessed':False,
            'new_learned_training_executed':False,'strongest_baseline_selection':'PENDING_M4.4'})
        files = [{'path':p.relative_to(output).as_posix(),'sha256':sha(p),'size_bytes':p.stat().st_size}
                 for p in sorted(output.rglob('*')) if p.is_file()]
        manifest = {'schema_version':1,'task_id':'M4.2','scope':config['scope'],
            'status':'PASS_ACTIVE_PRIMARY_INPUTS_AND_SETTINGS','source_commit':commit,
            'source_hashes':{name:sha(root/name) for name in SOURCE_FILES},'files':files,
            'authority_hashes':{key:ref for key,ref in config['references'].items()
                                if key!='qarf_checkpoint'},
            'dataset':config['dataset'],'evaluation_unit':'page','owner':'Khương',
            'owner_acceptance':'PENDING_USER_REVIEW','experiment_class':'calibration',
            'evidence_class':'engineering_evidence','fitted_weights':list(fitted['weights']),
            'train_ndcg_at_10':fitted['train_ndcg_at_10'],'grid_candidates':fitted['candidates'],
            'train_coverage':coverage,'common_inputs_audit':audit,
            'completed_utc':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds':time.monotonic()-start,
            'vimdoc_confirmation_baseline_package':'PENDING_SEPARATE_EXECUTION',
            'upstream_pending_signoffs_preserved':['M3.1 historical independent human review',
                                                    'A003 historical independent-review field']}
        write_json(output/'manifest.json',manifest)
        write_json(output/'_SUCCESS.json',{'manifest_sha256':sha(output/'manifest.json'),
                                         'status':manifest['status']})
        return manifest
    except Exception as exc:
        write_json(output/'_FAILED.json',{'status':'FAILED','error':str(exc),'automatic_retry':False})
        raise


def verify_files(output, expected_manifest_sha256):
    output = Path(output)
    require(sha(output/'manifest.json')==expected_manifest_sha256,'Manifest external pin differs')
    manifest = read(output/'manifest.json')
    for ref in manifest['files']:
        require(sha(inside(output,ref['path']))==ref['sha256'],f'Artifact hash drift: {ref["path"]}')
    return manifest


def verify(root, output, expected_manifest_sha256, *, replay_fit=False):
    root, output = Path(root),Path(output)
    require(root.resolve()==ROOT.resolve(),'M4.2 must replay from the executing checkout')
    manifest = verify_files(output,expected_manifest_sha256)
    require(read(output/'_SUCCESS.json')['manifest_sha256']==expected_manifest_sha256,'Success pin differs')
    require(set(manifest['source_hashes'])==set(SOURCE_FILES),'Source inventory differs')
    for name,digest in manifest['source_hashes'].items():
        require(sha(inside(root,name))==digest,f'Executing source/config hash drift: {name}')
    for ref in manifest['authority_hashes'].values():
        require(sha(inside(root,ref['path']))==ref['sha256'],f'Authority hash drift: {ref["path"]}')
    shared, fitted = read(output/'shared_inputs.json'),read(output/'train_fit.json')
    splits = {}
    for role,key in [('train','split_train'),('validation','split_validation'),('test','split_test')]:
        splits[role] = (output/shared['inputs'][key]['path']).read_text(encoding='utf8').splitlines()
    records, coverage = _train_records(output,shared['inputs'],splits)
    metric = evaluate(predictions(records,'train_fitted_static',weights=fitted['weights']),records)[0]['ndcg_at_10']
    require(abs(metric-fitted['train_ndcg_at_10'])<=1e-12 and coverage==manifest['train_coverage'],
            'Selected train objective/coverage does not replay')
    expected = baseline_contracts(sha(output/'shared_inputs.json'),fitted['weights'],
                                  shared['inputs']['qarf_checkpoint']['sha256'])
    require(read(output/'baseline_contracts.json')==expected,'Seven baseline common-input contracts differ')
    if replay_fit:
        replayed = fit_train_records(records,splits['train'])
        require(json.dumps(replayed,sort_keys=True)==json.dumps(fitted,sort_keys=True),'Full static fit replay differs')
    return {'status':'PASS','scope':manifest['scope'],'train_queries':len(records),
            'train_ndcg_at_10':metric,'weights':fitted['weights'],'full_fit_replayed':replay_fit,
            'test_labels_deserialized':False,'vimdoc_confirmation_accessed':False}
