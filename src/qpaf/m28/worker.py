"""One real GPU worker: pinned OCR -> durable full-corpus neural scores."""
import gc
import logging
from pathlib import Path
import random
import time

import numpy as np

from qpaf.m11.artifacts import digest, file_manifest, object_hash, read_json, utc, write_json
from qpaf.m11.retrieval import bm25_scores
from qpaf.m22.checks import compare, compare_multivectors, maxsim_reference
from qpaf.m22.telemetry import Telemetry, failure_record
from .preflight import validate_pages
from .runtime import load_array, save_array, load_vectors, save_vectors, require_cuda, bm25_probe


def _identity(config, source, inputs):
    return {'config_sha256': object_hash(config), 'source_sha256': source['digest'],
            'input_sha256': object_hash(inputs)}


def _array(path, identity, produce, commit):
    if path.exists() or path.with_suffix('.json').exists():
        return load_array(path, identity)
    values = produce()
    save_array(path, values, identity)
    commit()
    return values


def _vectors(path, identity, produce, commit):
    if path.exists() or path.with_suffix('.json').exists():
        return load_vectors(path, identity)
    values = produce()
    save_vectors(path, values, identity)
    commit()
    return values


def _dense(config, queries, pages, out, identity, cache, commit, progress, telemetry):
    import torch
    from sentence_transformers import SentenceTransformer
    c = config['retrievers']['dense']
    with telemetry.phase('dense_load_model'):
        model = SentenceTransformer(c['model_id'], revision=c['revision'], device='cuda',
                                    cache_folder=str(cache), trust_remote_code=False)
        model.max_seq_length = c['max_seq_length']
        model.float().eval().requires_grad_(False)
    if next(model.parameters()).device.type != 'cuda':
        raise RuntimeError('Dense model did not load on CUDA')

    def encode(texts, batch=c['batch_size']):
        with torch.inference_mode():
            return model.encode(texts, batch_size=batch, normalize_embeddings=True,
                                convert_to_numpy=True, show_progress_bar=False).astype(np.float32)

    with telemetry.phase('dense_encode_queries'):
        q = _array(out/'query_embeddings.npy', {**identity, 'kind': 'dense_queries'},
                   lambda: encode([c['query_prefix']+x for x in queries]), commit)
    chunks, page_norms = [], []
    size = config['execution']['dense_shard_size']
    for start in range(0, len(pages), size):
        stop = min(start+size, len(pages))
        ident = {**identity, 'kind': 'dense_pages', 'start': start, 'stop': stop}
        with telemetry.phase('dense_encode_pages'):
            p = _array(out/f'page_embeddings-{start:08d}.npy', ident,
                       lambda: encode([c['page_prefix']+r['text'] for r in pages[start:stop]]), commit)
            page_norms.extend(np.linalg.norm(p, axis=1).tolist())
        score_id = {**ident, 'kind': 'dense_scores'}
        def score():
            with torch.inference_mode():
                return (torch.from_numpy(q).cuda() @ torch.from_numpy(p).cuda().T).cpu().numpy().astype(np.float64)
        with telemetry.phase('dense_score_cuda'):
            chunks.append(_array(out/f'scores-{start:08d}.npy', score_id, score, commit))
        progress('dense', stop, len(pages))
    scores = np.concatenate(chunks, axis=1)
    if not (out/'parity.json').exists():
        with telemetry.phase('dense_reference_probe'):
            qref, pref = encode(queries[:4], 1), encode([r['text'] for r in pages[:16]], 1)
            ref = (torch.from_numpy(qref).cuda() @ torch.from_numpy(pref).cuda().T).cpu().numpy()
            checks = {'batch_reference': compare(scores[:4, :16], ref,
                       config['parity']['dense_atol'], config['parity']['dense_rtol']),
                      'unit_query_norm': compare(np.linalg.norm(q, axis=1), np.ones(len(q)), 1e-5),
                      'unit_page_norm': compare(page_norms, np.ones(len(page_norms)), 1e-5),
                      'query_embedding_reference': compare(q[:4], qref, config['parity']['dense_atol'], config['parity']['dense_rtol']),
                      'page_embedding_reference': compare(load_array(out/'page_embeddings-00000000.npy',
                          {**identity, 'kind': 'dense_pages', 'start': 0,
                           'stop': min(size, len(pages))})[:16], pref,
                          config['parity']['dense_atol'], config['parity']['dense_rtol'])}
            if not all(v['passed'] for v in checks.values()):
                raise ValueError(f'Dense GPU parity failed: {checks}')
            write_json(out/'parity.json', checks)
    save_or_check(out/'scores.npy', scores, {**identity, 'kind': 'dense_full'}, commit)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return {'shape': list(scores.shape), 'parity': read_json(out/'parity.json'), 'frozen_weights': True}


def save_or_check(path, array, identity, commit):
    if path.exists():
        if not np.array_equal(load_array(path, identity), array):
            raise ValueError('Completed score matrix differs from verified shards')
    else:
        save_array(path, array, identity)
        commit()


def _visual(config, queries, pages, ocr, out, identity, cache, commit, progress, telemetry):
    import torch
    from PIL import Image
    from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    c = config['retrievers']['visual']
    with telemetry.phase('visual_load_model'):
        model = ColQwen2_5.from_pretrained(c['base_model_id'], revision=c['base_revision'],
            torch_dtype=torch.float32, device_map='cuda', cache_dir=str(cache),
            attn_implementation=c['attention'])
        model = PeftModel.from_pretrained(model, c['model_id'], revision=c['revision'],
                                         cache_dir=str(cache), is_trainable=False).eval()
        model.requires_grad_(False)
        snapshot = snapshot_download(c['processor_id'], revision=c['processor_revision'],
                                     cache_dir=str(cache), local_files_only=True)
        processor = ColQwen2_5_Processor.from_pretrained(snapshot, local_files_only=True,
                                                       use_fast=c['processor_use_fast'])
        processor.query_prefix = c['query_prefix']
        processor.image_processor.max_pixels = c['max_pixels']
        processor.image_processor.min_pixels = c['min_pixels']
        processor.image_processor.size.update(longest_edge=c['max_pixels'], shortest_edge=c['min_pixels'])
    if model.device.type != 'cuda':
        raise RuntimeError('Visual model did not load on CUDA')

    def encode_queries(texts, batch_size=c['query_batch_size']):
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = processor.process_queries(texts[start:start+batch_size]).to(model.device)
                if batch['input_ids'].shape[1] > c['max_query_tokens']:
                    raise ValueError('Visual query exceeds calibrated token cap')
                vectors.extend(v.cpu() for v in model(**batch))
        return vectors

    def encode_pages(rows, batch_size=c['batch_size']):
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(rows), batch_size):
                images = []
                try:
                    for row in rows[start:start+batch_size]:
                        image = ocr/row['artifacts']['image']['path']
                        if image.stat().st_size != row['artifacts']['image']['size_bytes'] or digest(image) != row['image_sha256']:
                            raise ValueError('M2.6 image changed: '+row['page_id'])
                        with Image.open(image) as original:
                            images.append(original.convert('RGB'))
                    batch = processor.process_images(images).to(model.device)
                    vectors.extend(v.cpu() for v in model(**batch))
                finally:
                    for image in images:
                        image.close()
        return vectors

    with telemetry.phase('visual_encode_queries'):
        q = _vectors(out/'embeddings'/'queries.pt', {**identity, 'kind': 'visual_queries'},
                     lambda: encode_queries(queries), commit)
    chunks = []
    size = config['execution']['visual_shard_size']
    for start in range(0, len(pages), size):
        stop = min(start+size, len(pages))
        ident = {**identity, 'kind': 'visual_pages', 'start': start, 'stop': stop}
        with telemetry.phase('visual_encode_pages'):
            p = _vectors(out/'embeddings'/f'pages-{start:08d}.pt', ident,
                         lambda: encode_pages(pages[start:stop]), commit)
        def score():
            with torch.inference_mode():
                return processor.score_multi_vector(q, p, batch_size=c['score_batch_size'],
                    device='cuda').float().cpu().numpy().astype(np.float64)
        with telemetry.phase('visual_score_cuda'):
            values = _array(out/f'scores-{start:08d}.npy', {**ident, 'kind': 'visual_scores'}, score, commit)
        chunks.append(values)
        if start == 0 and not (out/'parity.json').exists():
            with telemetry.phase('visual_reference_probe'):
                qref, pref = encode_queries(queries[:4], 1), encode_pages(pages[:16], 1)
                ref = processor.score_multi_vector(qref, pref, batch_size=1, device='cuda').float().cpu().numpy()
                limits = config['parity']
                checks = {'batch_reference': compare(values[:4, :16], ref, limits['visual_atol'], limits['visual_rtol']),
                    'query_embedding_reference': compare_multivectors(q[:4], qref, limits['visual_embedding_atol'], limits['visual_embedding_rtol']),
                    'page_embedding_reference': compare_multivectors(p[:16], pref, limits['visual_embedding_atol'], limits['visual_embedding_rtol']),
                    'independent_maxsim': compare(values[:4, :16], maxsim_reference(q[:4], p[:16]), limits['visual_atol'], limits['visual_rtol'])}
                if not all(v['passed'] for v in checks.values()):
                    raise ValueError(f'Visual GPU parity failed: {checks}')
                write_json(out/'parity.json', checks)
                commit()
        progress('visual', stop, len(pages))
    scores = np.concatenate(chunks, axis=1)
    save_or_check(out/'scores.npy', scores, {**identity, 'kind': 'visual_full'}, commit)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return {'shape': list(scores.shape), 'parity': read_json(out/'parity.json'), 'frozen_weights': True}


def execute(config, run_id, source, inputs, query_texts, resume=False):
    import modal
    import torch
    import qpaf
    from qpaf.m22.worker import prefetch
    gpu = require_cuda(torch)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_num_threads(config['execution']['cpu'])
    random.seed(2026)
    np.random.seed(2026)
    torch.manual_seed(2026)
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    run = Path(config['modal']['mount_path'])/'runs'/run_id
    existed = run.exists()
    if existed and not resume:
        raise FileExistsError('Run already exists; explicit same-identity resume is required')
    run.mkdir(parents=True, exist_ok=resume)
    identity = _identity(config, source, inputs)
    for name, obj in [('identity.json', identity), ('resolved_config.json', config),
                      ('source.json', source), ('input_manifest.json', inputs), ('queries.json', query_texts)]:
        path = run/name
        if path.exists():
            if read_json(path) != obj:
                raise ValueError('Resume source/config/input identity mismatch: '+name)
        elif existed:
            raise ValueError('Incomplete run identity: '+name)
        else:
            write_json(path, obj)
    attempts = run/'attempts'
    attempts.mkdir(exist_ok=True)
    attempt = attempts/(utc().replace(':', '').replace('.', '')+'.json')
    write_json(attempt, {'started_utc': utc(), 'resume': resume, 'status': 'RUNNING', 'gpu': gpu})
    volume.commit()
    started, telemetry = time.perf_counter(), Telemetry()
    results = {}

    def progress(stage, completed, total):
        value = {'status': 'RUNNING', 'stage': stage, 'completed': completed, 'total': total,
                 'wall_seconds': time.perf_counter()-started, 'utc': utc(), 'gpu': gpu}
        write_json(run/'progress.json', value)
        volume.commit()
        print(f'M2.8 {stage} {completed}/{total}; {value["wall_seconds"]:.1f}s', flush=True)
        if value['wall_seconds'] > config['execution']['timeout_seconds']-120:
            raise TimeoutError('M2.8 wall cap reached; verified shards retained for explicit resume')

    try:
        with telemetry.phase('full_run'):
            package = Path(qpaf.__file__).parent
            for row in source['files']:
                if row['path'].startswith('src/qpaf/') and digest(package/row['path'][len('src/qpaf/'):]) != row['sha256']:
                    raise ValueError('Deployed source hash mismatch: '+row['path'])
            if object_hash(query_texts) != inputs['query_texts_sha256'] or sorted(query_texts) != inputs['query_ids']:
                raise ValueError('Query text payload differs from frozen preflight')
            ocr = Path(config['ocr']['remote_output'])
            if digest(ocr/'handover.json') != config['ocr']['handover_sha256']:
                raise ValueError('Remote M2.6 handover hash mismatch')
            handover = read_json(ocr/'handover.json')
            if handover != inputs['m26_handover'] or digest(ocr/'resolved_pages.json') != handover['resolved_pages_sha256']:
                raise ValueError('Remote OCR text differs from local verified preflight')
            pages = sorted(read_json(ocr/'resolved_pages.json'), key=lambda r: r['page_id'])
            checks = validate_pages(pages, handover)
            if checks['preprocessing_identity_sha256'] != handover['preprocessing_identity_sha256']:
                raise ValueError('Remote OCR preprocessing identity mismatch')
            texts = [query_texts[q] for q in inputs['query_ids']]
            write_json(run/'environment.json', {'gpu': gpu, 'runtime': __import__('qpaf.m22.worker', fromlist=['runtime_info']).runtime_info(),
                       'image_id': __import__('os').environ.get('MODAL_IMAGE_ID'), 'uses_real_data': True,
                       'inference_device': 'cuda', 'score_device': 'cuda', 'training_executed': False})
            for stage in ('bm25', 'dense', 'visual'):
                out = run/stage
                out.mkdir(exist_ok=True)
                if (out/'summary.json').exists():
                    result = read_json(out/'summary.json')
                    if result['status'] != 'PASS' or result['identity'] != identity:
                        raise ValueError('Completed stage identity/status mismatch')
                    load_array(out/'scores.npy', {**identity, 'kind': stage+'_full'}, (len(texts), len(pages)))
                    results[stage] = result
                    progress(stage, len(pages), len(pages))
                    continue
                progress(stage, 0, len(pages))
                if stage == 'bm25':
                    with telemetry.phase('bm25_score'):
                        scores = bm25_scores(
                            texts, [p['text'] for p in pages], config['retrievers']['bm25']['k1'], config['retrievers']['bm25']['b'])
                    save_or_check(out/'scores.npy', scores, {**identity, 'kind': 'bm25_full'}, volume.commit)
                    c = config['retrievers']['bm25']
                    parity = compare(scores[:4, :16], bm25_probe(texts[:4], [p['text'] for p in pages],
                                     c['k1'], c['b']), config['parity']['bm25_atol'])
                    if not parity['passed']:
                        raise ValueError(f'BM25 full-corpus reference parity failed: {parity}')
                    write_json(out/'parity.json', {'independent_reference': parity})
                    result = {'shape': list(scores.shape), 'frozen_weights': True,
                              'parity': {'independent_reference': parity}}
                else:
                    cache = Path(config['modal']['model_mount_path'])/'model_cache'
                    prefetch(stage, {**config['retrievers']}, cache, telemetry, out)
                    if stage == 'dense':
                        result = _dense(config, texts, pages, out, identity, cache, volume.commit, progress, telemetry)
                    else:
                        result = _visual(config, texts, pages, ocr, out, identity, cache, volume.commit, progress, telemetry)
                results[stage] = {'status': 'PASS', 'identity': identity, **result}
                write_json(out/'summary.json', results[stage])
                volume.commit()
            status = 'COMPLETE'
    except Exception as exc:
        status = 'FAIL'
        write_json(run/'failure.json', failure_record(exc))
        print(f'M2.8 failed: {type(exc).__name__}: {exc}', flush=True)
    resources = {'phases': telemetry.phases, 'peak_rss_mb': telemetry.peak_rss_mb,
                 'peak_cuda_allocated_mb': max((p['peak_cuda_allocated_mb'] for p in telemetry.phases), default=0.),
                 'peak_cuda_reserved_mb': max((p['peak_cuda_reserved_mb'] for p in telemetry.phases), default=0.)}
    write_json(run/'resources.json', resources)
    summary = {'status': status, 'task_id': 'M2.8', 'run_id': run_id, 'completed_utc': utc(),
               'wall_seconds': time.perf_counter()-started, 'gpu': gpu, 'stages': results,
               'query_count': len(inputs['query_ids']), 'page_count': len(inputs['page_ids']),
               'real_query_page_pairs_per_channel': len(inputs['query_ids'])*len(inputs['page_ids']),
               'training_executed': False, 'uses_qrels': False, 'identity': identity}
    write_json(run/'summary.json', summary)
    write_json(attempt, {**read_json(attempt), 'status': status, 'completed_utc': utc()})
    portable = [r for r in file_manifest(run) if not r['path'].startswith('attempts/')
                and not '/embeddings/' in r['path'] and not '/page_embeddings-' in r['path']
                and r['path'] != 'portable_manifest.json']
    # Portable bundle retains all raw score shards and model-file hashes; large
    # embedding payloads stay checksummed in the durable cloud Volume.
    write_json(run/'portable_manifest.json', {'status': status, 'files': portable,
               'embedding_files': [r for r in file_manifest(run) if '/embeddings/' in r['path'] or '/page_embeddings-' in r['path']]})
    volume.commit()
    return summary


def build_app(config, repo_root):
    import modal
    root = Path(repo_root)
    image = (modal.Image.debian_slim(python_version='3.11')
        .apt_install('tesseract-ocr', 'tesseract-ocr-eng', 'libglib2.0-0', 'libgl1', 'git')
        .pip_install_from_requirements(str(root/config['execution']['requirements_file']))
        .env({'TOKENIZERS_PARALLELISM': 'false', 'HF_HUB_DISABLE_TELEMETRY': '1'})
        .add_local_python_source('qpaf'))
    output = modal.Volume.from_name(config['modal']['volume_name'], create_if_missing=True)
    volumes = {config['modal']['mount_path']: output,
        config['ocr']['mount_path']: modal.Volume.from_name(config['ocr']['volume_name']),
        config['modal']['model_mount_path']: modal.Volume.from_name(config['modal']['model_volume_name'])}
    app = modal.App(config['modal']['app_name'])
    worker = app.function(image=image, gpu=config['execution']['gpu'], cpu=config['execution']['cpu'],
        memory=config['execution']['memory_mib'], timeout=config['execution']['timeout_seconds'],
        retries=0, max_containers=1, volumes=volumes)(execute)
    return app, worker
