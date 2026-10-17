"""Create-once Modal stages with durable logs, resource checks and score evidence."""
import gc
import hashlib
import importlib.metadata
import io
import logging
from pathlib import Path
import platform
import random
import signal
import sys
import threading
import time

from qpaf.m11.artifacts import (digest, environment, file_manifest, object_hash,
                                read_json, utc, write_json)
from qpaf.m11.dataset import extract_zip
from qpaf.m11.retrieval import (bm25_scores, dense_scores, visual_scores,
                                save_score_cache, load_score_cache)
from qpaf.m18.ocr_policy import evaluate_page_text
from qpaf.m18.namespace import parse_canonical_run_id
from .checks import bm25_reference, compare, compare_multivectors, maxsim_reference, rankings
from .config import validate
from .sample import pack_folder, validate_inputs
from .telemetry import Telemetry, failure_record


def root_for(config, run_id):
    validate(config)
    if parse_canonical_run_id(run_id)['experiment_id'] != config['experiment_id']:
        raise ValueError('Run ID/experiment mismatch')
    return Path(config['modal']['mount_path'])/'runs'/run_id


def runtime_info():
    import torch
    result = environment()
    result['cuda_available'] = torch.cuda.is_available()
    if torch.cuda.is_available():
        result['gpu'] = {'name': torch.cuda.get_device_name(), 'cuda': torch.version.cuda,
                         'total_memory_mb': torch.cuda.get_device_properties(0).total_memory/1024**2}
    result['platform'] = platform.platform()
    return result


def initialize(config, run_id, payload, source):
    import modal
    validate(config)
    if len(payload) > config['caps']['input_mb']*1024**2:
        raise ValueError('Input payload cap exceeded')
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    root = root_for(config, run_id)
    root.mkdir(parents=True, exist_ok=False)
    try:
        write_json(root/'resolved_config.json', config)
        write_json(root/'source.json', source)
        import qpaf
        package_root = Path(qpaf.__file__).parent
        for row in source['files']:
            if row['path'].startswith('src/qpaf/'):
                if digest(package_root/row['path'][len('src/qpaf/'):]) != row['sha256']:
                    raise ValueError('Deployed package differs from recorded source')
        write_json(root/'initialization.json', {'started_utc': utc(), 'payload_sha256': hashlib.sha256(payload).hexdigest()})
        extract_zip(io.BytesIO(payload), root/'inputs')
        validate_inputs(root/'inputs', config)
        return {'status': 'PASS', 'input_bytes': len(payload)}
    except Exception as exc:
        write_json(root/'initialization_failure.json', failure_record(exc))
        raise
    finally:
        volume.commit()


def resolve_text(config, root, output):
    import math
    import pytesseract
    from PIL import Image
    queries, pages, meta = validate_inputs(root/'inputs', config)
    policy = config['text']
    engine = str(pytesseract.get_tesseract_version())
    if engine != policy['ocr_engine_version']:
        raise ValueError(f'OCR version {engine} differs from configured version')
    failures = []
    for page in pages:
        decision = evaluate_page_text(page['text'], min_chars=policy['min_native_chars'],
                                      min_printable_ratio=policy['min_printable_ratio'])
        source, confidence = 'native', None
        if decision.route == 'OCR_FALLBACK_TRIGGERED':
            source = 'ocr'
            try:
                with Image.open(root/'inputs'/page['image']) as image:
                    data = pytesseract.image_to_data(image, lang=policy['ocr_language'],
                        timeout=policy['ocr_timeout'], output_type=pytesseract.Output.DICT)
                words = [(str(w).strip(), float(c)) for w, c in zip(data['text'], data['conf']) if str(w).strip()]
                page['text'] = ' '.join(w for w, _ in words)
                if not words:
                    page.update(text_source='ocr', ocr_confidence=0.,
                        extraction_status='NO_TEXT_DETECTED', extraction_reason='ocr_returned_no_words',
                        review_status='M23_REVIEW_PENDING', text_sha256=hashlib.sha256(b'').hexdigest())
                    continue
                confs = [c for _, c in words if math.isfinite(c) and 0 <= c <= 100]
                confidence = sum(confs)/len(confs) if confs else 0.
                decision = evaluate_page_text(page['text'], confidence=confidence,
                    min_chars=policy['min_ocr_chars'], min_printable_ratio=policy['min_printable_ratio'],
                    min_confidence=policy['min_ocr_confidence'])
            except Exception as exc:
                failures.append({'page_id': page['page_id'], **failure_record(exc)})
                page['extraction_status'] = 'EXTRACTION_FAILED'
                continue
        page.update(text_source=source, ocr_confidence=confidence, extraction_status=decision.route,
                    text_sha256=hashlib.sha256(page['text'].encode()).hexdigest())
        if decision.route not in ('NATIVE_TEXT_QUALIFIED', 'OCR_TEXT_QUALIFIED'):
            failures.append({'page_id': page['page_id'], 'status': decision.route, 'reason': decision.reason})
    write_json(output/'pages.json', pages)
    write_json(output/'failures.json', failures)
    write_json(output/'extraction_summary.json', {
        'total_pages': len(pages), 'native_pages': sum(p.get('text_source') == 'native' for p in pages),
        'ocr_pages': sum(p.get('text_source') == 'ocr' for p in pages),
        'no_text_detected_pages': sum(p.get('extraction_status') == 'NO_TEXT_DETECTED' for p in pages),
        'failures': len(failures), 'engine': engine, 'policy': policy})
    if failures:
        raise ValueError('Sample extraction failed; see prepare/failures.json')
    return {'status': 'PASS', 'page_count': len(pages), 'sample_identity_sha256': object_hash(meta),
            'no_text_detected_pages': sum(p.get('extraction_status') == 'NO_TEXT_DETECTED' for p in pages),
            'text_quality_acceptance': 'M23_PENDING'}


def prefetch(channel, config, cache, telemetry, output):
    from huggingface_hub import snapshot_download
    c = config[channel]
    repos = [(c['model_id'], c['revision'])]
    if channel == 'visual':
        repos.insert(0, (c['base_model_id'], c['base_revision']))
    downloaded = []
    with telemetry.phase('download_models'):
        for repo, revision in repos:
            folder = Path(snapshot_download(repo, revision=revision, cache_dir=str(cache),
                allow_patterns=['*.json', '*.txt', '*.model', '*.safetensors', '*.jinja']))
            records = []
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    records.append({'path': path.relative_to(folder).as_posix(),
                                    'size_bytes': path.stat().st_size, 'sha256': digest(path)})
            downloaded.append({'repo_id': repo, 'revision': revision, 'files': records})
    write_json(output/'model_files.json', downloaded)


def run_channel(channel, config, root, output, telemetry, logger):
    import numpy as np
    queries, original_pages, meta = validate_inputs(root/'inputs', config)
    prepared = read_json(root/'prepare'/'summary.json')
    if prepared['status'] != 'PASS':
        raise ValueError('Successful text preparation required')
    pages = read_json(root/'prepare'/'pages.json')
    if [p['page_id'] for p in pages] != meta['page_ids']:
        raise ValueError('Prepared page IDs changed')
    qids, pids = meta['query_ids'], meta['page_ids']
    texts, query_texts = [p['text'] for p in pages], [q['text'] for q in queries]
    write_json(output/'inputs.json', {'query_ids': qids, 'page_ids': pids,
                                    'prepared_pages_sha256': digest(root/'prepare'/'pages.json')})
    parity = config['parity']
    checks = {}
    if channel == 'bm25':
        with telemetry.phase('score'):
            scores = bm25_scores(query_texts, texts, config[channel]['k1'], config[channel]['b'])
        reference = bm25_reference(query_texts, texts, config[channel]['k1'], config[channel]['b'])
        checks['independent_reference'] = compare(scores, reference, parity['bm25_atol'])
        write_json(output/'index.json', {'page_ids': pids, 'texts': texts, 'settings': config[channel]})
    else:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('GPU worker has no CUDA device')
        cache = Path(config['modal']['mount_path'])/'model_cache'
        prefetch(channel, config, cache, telemetry, output)
        if channel == 'dense':
            scores = dense_scores(query_texts, texts, config[channel], output, logger, cache,
                                   observer=telemetry.phase, reference_output=output/'reference')
            reference = np.load(output/'reference'/'scores.npy', allow_pickle=False)
            checks['batch_reference'] = compare(scores, reference, parity['dense_atol'], parity['dense_rtol'])
            embeddings = {}
            for kind in ('query', 'page'):
                a = np.load(output/(kind+'_embeddings.npy'), allow_pickle=False)
                b = np.load(output/'reference'/(kind+'_embeddings.npy'), allow_pickle=False)
                embeddings[kind] = a
                checks[kind+'_embedding_batch_reference'] = compare(a, b, parity['dense_atol'], parity['dense_rtol'])
                checks[kind+'_unit_norm'] = compare(np.linalg.norm(a, axis=1), np.ones(len(a)), 1e-5)
            checks['embedding_score_reload'] = compare(scores, embeddings['query'] @ embeddings['page'].T, 0)
        else:
            scores = visual_scores(query_texts, pages, root/'inputs', config[channel], output, logger, cache,
                                    observer=telemetry.phase, reference_output=output/'reference')
            reference = np.load(output/'reference'/'scores.npy', allow_pickle=False)
            checks['batch_reference'] = compare(scores, reference, parity['visual_atol'], parity['visual_rtol'])
            vectors = {}
            for kind in ('queries', 'pages'):
                def read_vectors(base):
                    paths = [base/'queries.pt'] if kind == 'queries' else sorted(base.glob('pages-*.pt'))
                    return [vector for path in paths for vector in torch.load(path, map_location='cpu', weights_only=True)]
                a, b = read_vectors(output/'embeddings'), read_vectors(output/'reference'/'embeddings')
                vectors[kind] = a
                checks[kind+'_embedding_batch_reference'] = compare_multivectors(a, b,
                    parity['visual_embedding_atol'], parity['visual_embedding_rtol'])
            with telemetry.phase('reference_maxsim'):
                independent = maxsim_reference(vectors['queries'], vectors['pages'])
            checks['independent_maxsim'] = compare(scores, independent, parity['visual_atol'], parity['visual_rtol'])
        gc.collect()
        torch.cuda.empty_cache()
    save_score_cache(output, scores, qids, pids, channel)
    cached = load_score_cache(output, qids, pids, channel)
    checks['cache_reload'] = compare(cached, scores, 0)
    checks['ranking_reload'] = {'passed': rankings(cached, pids) == rankings(scores, pids)}
    write_json(output/'rankings.json', {'query_ids': qids, 'rankings': rankings(cached, pids)})
    write_json(output/'checks.json', checks)
    return {'status': 'PASS' if all(c['passed'] for c in checks.values()) else 'FAIL',
            'channel': channel, 'checks': checks, 'shape': list(scores.shape),
            'score_min': float(scores.min()), 'score_max': float(scores.max()),
            'frozen_weights': True, 'settings': config[channel]}


def execute(stage, config, run_id):
    import modal
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    root = root_for(config, run_id)
    if stage not in ('prepare', 'bm25', 'dense', 'visual'):
        raise ValueError('Unknown calibration stage')
    if read_json(root/'resolved_config.json') != config:
        raise ValueError('Run config mismatch')
    output = root/stage
    output.mkdir(exist_ok=False)
    write_json(output/'status.json', {'status': 'RUNNING', 'started_utc': utc()})
    volume.commit()  # a hard platform timeout still leaves an observable start record
    telemetry, started = Telemetry(), time.perf_counter()
    logger = logging.getLogger('m22.'+stage)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(output/'run.log', encoding='utf-8')
    logger.addHandler(handler)
    use_alarm = threading.current_thread() is threading.main_thread()
    previous_handler = signal.getsignal(signal.SIGALRM) if use_alarm else None

    def timeout(signum, frame):
        raise TimeoutError('M2.2 stage reached configured wall-time cap')

    if use_alarm:
        signal.signal(signal.SIGALRM, timeout)
        signal.alarm(max(1, config['caps']['timeout_seconds']-15))
    try:
        import numpy as np
        import torch
        random.seed(config['seed'])
        np.random.seed(config['seed'])
        torch.manual_seed(config['seed'])
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config['seed'])
        torch.backends.cudnn.benchmark = False
        torch.backends.cuda.matmul.allow_tf32 = False
        write_json(output/'environment.json', runtime_info())
        logger.info('Started %s', stage)
        with telemetry.phase('prepare' if stage == 'prepare' else 'total_channel'):
            result = resolve_text(config, root, output) if stage == 'prepare' else run_channel(stage, config, root, output, telemetry, logger)
    except Exception as exc:
        logger.exception('Calibration stage failed')
        result = failure_record(exc)
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
        resources = {'phases': telemetry.phases, 'elapsed_seconds': time.perf_counter()-started,
                     'peak_rss_mb': telemetry.peak_rss_mb,
                     'peak_cuda_reserved_mb': max((p['peak_cuda_reserved_mb'] for p in telemetry.phases), default=0),
                     'artifact_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
                     'rss_poll_interval_seconds': .02}
        caps = config['caps']
        limits = {'ram': resources['peak_rss_mb'] <= caps['ram_mb'],
                  'vram': resources['peak_cuda_reserved_mb'] <= caps['vram_mb'],
                  'time': resources['elapsed_seconds'] <= caps['timeout_seconds'],
                  'artifact': resources['artifact_bytes'] <= caps['artifact_mb']*1024**2}
        if not all(limits.values()):
            result.update(status='FAIL', resource_limit_exceeded=True)
        result.update(stage=stage, completed_utc=utc(), resources=resources, resource_checks=limits)
        write_json(output/'resources.json', resources)
        write_json(output/'summary.json', result)
        write_json(output/'status.json', {'status': result['status'], 'completed_utc': result['completed_utc']})
        write_json(output/'hashes.json', file_manifest(output, exclude=('hashes.json',)))
        logger.removeHandler(handler)
        handler.close()
        volume.commit()
    return result


def collect(config, run_id):
    import modal
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    return pack_folder(root_for(config, run_id), config['caps']['artifact_mb'])


def cpu_stage(stage, config, run_id):
    return execute(stage, config, run_id)


def gpu_stage(stage, config, run_id):
    return execute(stage, config, run_id)


def build_app(config, repo_root):
    import modal
    validate(config)
    root = Path(repo_root)
    image = (modal.Image.debian_slim(python_version=config['modal']['python_version'])
             .apt_install('tesseract-ocr', 'tesseract-ocr-eng', 'libglib2.0-0', 'libgl1', 'git')
             .pip_install_from_requirements(str(root/config['modal']['requirements_file']))
             .env({'TOKENIZERS_PARALLELISM': 'false', 'HF_HUB_DISABLE_TELEMETRY': '1'})
             .add_local_python_source('qpaf'))
    volume = modal.Volume.from_name(config['modal']['volume_name'], create_if_missing=True)
    app = modal.App(config['modal']['app_name'])
    options = {'image': image, 'cpu': config['modal']['cpu'], 'memory': config['caps']['ram_mb'],
               'timeout': config['caps']['timeout_seconds'], 'retries': 0, 'max_containers': 1,
               'volumes': {config['modal']['mount_path']: volume}}
    init = app.function(**options)(initialize)
    cpu = app.function(**options)(cpu_stage)
    gpu = app.function(gpu=config['modal']['gpu'], **options)(gpu_stage)
    fetch = app.function(**options)(collect)
    return app, init, cpu, gpu, fetch
