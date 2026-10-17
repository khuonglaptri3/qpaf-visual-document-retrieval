"""CPU-only paired OCR with pinned language bytes, TSV evidence and bounded jobs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
import csv
import gc
import importlib.metadata
import io
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

from qpaf.m11.artifacts import digest, file_manifest, read_json, utc, write_json
from qpaf.m11.dataset import extract_zip
from qpaf.m22.sample import pack_folder
from .config import validate
from .sample import text_signals, validate_inputs


class MemoryMonitor:
    """Sample Python RSS plus descendant RSS; peaks are not allocator hard limits."""
    def __init__(self):
        self.peak_mib = 0.
        self.stop = threading.Event()

    def sample(self):
        import psutil
        process = psutil.Process()
        memory = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                memory += child.memory_info().rss
            except psutil.Error:
                pass
        self.peak_mib = max(self.peak_mib, memory / 1024 ** 2)

    def __enter__(self):
        self.sample()
        def poll():
            while not self.stop.wait(.02):
                self.sample()
        self.thread = threading.Thread(target=poll, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.sample()


def runtime_identity(config):
    version = subprocess.check_output(['tesseract', '--version'], text=True, stderr=subprocess.STDOUT)
    paths = list(Path('/usr/share/tesseract-ocr').rglob(config['text']['language'] + '.traineddata'))
    if len(paths) != 1 or digest(paths[0]) != config['text']['traineddata_sha256']:
        raise ValueError('OCR traineddata bytes differ from the pinned model')
    if version.splitlines()[0] != 'tesseract ' + config['text']['engine_version']:
        raise ValueError('Tesseract version mismatch')
    packages = {name: importlib.metadata.version(name) for name in ('pypdfium2', 'Pillow', 'psutil')}
    if packages['pypdfium2'] != config['text']['parser_version']:
        raise ValueError('Worker PDF parser mismatch')
    return {'python': sys.version, 'platform': platform.platform(), 'packages': packages,
            'tesseract_version': version, 'traineddata_path': str(paths[0]),
            'traineddata_sha256': digest(paths[0]),
            'system_packages': subprocess.check_output(['dpkg-query', '-W', 'tesseract-ocr', 'tesseract-ocr-eng',
                                                        'libtesseract5', 'liblept5'], text=True),
            'gpu_requested': False, 'cpu_requested': config['modal']['cpu'],
            'omp_thread_limit': os.environ.get('OMP_THREAD_LIMIT'),
            'app_id': os.environ.get('MODAL_APP_ID')}


def parse_tsv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        # OCR tokens can begin with literal double quotes. TSV is not CSV quoted.
        rows = list(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))
    words = [row for row in rows if row.get('level') == '5' and row.get('text', '').strip()]
    confidences, weighted, weight = [], 0., 0
    for word in words:
        confidence = float(word['conf'])
        if math.isfinite(confidence) and 0 <= confidence <= 100:
            confidences.append(confidence)
            length = len(word['text'])
            weighted += confidence * length
            weight += length
    return {'word_count': len(words), 'mean_word_confidence': sum(confidences) / len(confidences) if confidences else None,
            'character_weighted_confidence': weighted / weight if weight else None,
            'low_confidence_word_fraction': sum(v < 60 for v in confidences) / len(confidences) if confidences else None}


def run_ocr(image, destination, dpi, config, remaining_seconds):
    import psutil
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ['tesseract', str(image), str(destination), '-l', config['text']['language'],
               '--oem', str(config['text']['oem']), '--psm', str(config['text']['psm']),
               '--dpi', str(dpi), 'txt', 'tsv']
    started, peak, stop = time.perf_counter(), [0], threading.Event()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=dict(os.environ, OMP_THREAD_LIMIT='1'))
    def poll():
        while not stop.wait(.02):
            try:
                peak[0] = max(peak[0], psutil.Process(process.pid).memory_info().rss)
            except psutil.Error:
                break
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    try:
        _, stderr = process.communicate(timeout=max(.1, min(config['text']['page_timeout_seconds'], remaining_seconds)))
        status, error = ('OK', None) if process.returncode == 0 else ('ERROR', f'tesseract exit {process.returncode}')
    except subprocess.TimeoutExpired:
        process.kill()
        _, stderr = process.communicate()
        status, error = 'TIMEOUT', 'Per-page or remaining wall-time cap exceeded'
    finally:
        stop.set()
        thread.join()
    destination.with_suffix('.stderr.txt').write_bytes(stderr)
    result = {'dpi': dpi, 'status': status, 'seconds': time.perf_counter() - started,
              'peak_tesseract_rss_mib': peak[0] / 1024 ** 2, 'command': command,
              'error': error, 'text': None, 'text_sha256': None}
    if status == 'OK':
        txt, tsv = destination.with_suffix('.txt'), destination.with_suffix('.tsv')
        if not txt.is_file() or not tsv.is_file():
            raise ValueError('Tesseract did not emit the required txt/tsv pair')
        result['text'] = txt.read_text(encoding='utf-8').strip()
        import hashlib
        result['text_sha256'] = hashlib.sha256(result['text'].encode()).hexdigest()
        result.update(parse_tsv(tsv))
        result['signals'] = text_signals(result['text'])
        result['status'] = 'OK' if result['word_count'] else 'NO_TEXT_DETECTED'
        result['human_quality_status'] = 'REVIEW_PENDING'
    return result


def execute(config, run_id, payload, source):
    import modal
    import pypdfium2 as pdfium
    import qpaf
    validate(config)
    if '/' in run_id or '\\' in run_id or not run_id.startswith('RUN-QPAF-M2_3-CAL-001-'):
        raise ValueError('Invalid run ID')
    if len(payload) > config['caps']['input_mib'] * 1024 ** 2:
        raise ValueError('Input payload cap exceeded')
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    root = Path(config['modal']['mount_path']) / 'runs' / run_id
    root.mkdir(parents=True, exist_ok=False)
    output = root / 'output'
    output.mkdir()
    write_json(output / 'status.json', {'status': 'RUNNING', 'started_utc': utc()})
    write_json(output / 'source.json', source)
    write_json(output / 'resolved_config.json', config)
    volume.commit()
    started = time.perf_counter()
    pages, errors, render_seconds = [], [], 0.
    monitor = MemoryMonitor()
    summary = {'status': 'FAIL', 'human_review_status': 'PENDING', 'thresholds_frozen': False}
    try:
        with monitor:
            package = Path(qpaf.__file__).parent
            for row in source['files']:
                if row['path'].startswith('src/qpaf/'):
                    if digest(package / row['path'][len('src/qpaf/'):]) != row['sha256']:
                        raise ValueError('Remote Python source differs from source snapshot')
            identity = runtime_identity(config)
            identity['pdfium'] = str(pdfium.PDFIUM_INFO)
            write_json(output / 'environment.json', identity)
            extract_zip(io.BytesIO(payload), root / 'inputs')
            pages, meta = validate_inputs(root / 'inputs', config)
            write_json(output / 'sample_manifest.json', meta)
            for dpi in config['text']['dpis']:
                (output / f'images{dpi}').mkdir()
            # PDFium rendering stays on this single thread. Only external OCR runs concurrently.
            for page in pages:
                page['ocr'] = {}
                if time.perf_counter() - started > config['caps']['wall_seconds'] - 30:
                    raise TimeoutError('Render phase reached the remaining wall-time budget')
                render_started = time.perf_counter()
                try:
                    with closing(pdfium.PdfDocument(str(root / 'inputs' / page['pdf']))) as document:
                        with closing(document[page['page_number'] - 1]) as pdfpage:
                            for dpi in config['text']['dpis']:
                                width, height = pdfpage.get_size()
                                if math.ceil(width * dpi / 72) * math.ceil(height * dpi / 72) > config['caps']['max_pixels']:
                                    raise ValueError('Rendered image exceeds pixel cap')
                                path = output / f'images{dpi}' / (page['page_id'] + '.png')
                                with closing(pdfpage.render(scale=dpi / 72)) as bitmap:
                                    image = bitmap.to_pil().convert('RGB')
                                try:
                                    image.save(path)
                                    page[f'image{dpi}'] = path.relative_to(output).as_posix()
                                    page[f'image{dpi}_sha256'] = digest(path)
                                    page[f'image{dpi}_size'] = list(image.size)
                                finally:
                                    image.close()
                    page['render_status'] = 'OK'
                except Exception as exc:
                    page['render_status'] = 'ERROR'
                    page['render_error'] = f'{type(exc).__name__}: {exc}'
                    errors.append({'page_id': page['page_id'], 'stage': 'render', 'error': page['render_error']})
                page['render_seconds'] = time.perf_counter() - render_started
                render_seconds += page['render_seconds']
            gc.collect()
            write_json(output / 'rendered_pages.json', pages)
            volume.commit()

            def job(page, dpi):
                elapsed = time.perf_counter() - started
                remaining = config['caps']['wall_seconds'] - elapsed - 20
                if remaining <= 0:
                    return {'dpi': dpi, 'status': 'NOT_RUN', 'error': 'Wall-time budget exhausted', 'text': None}
                image = output / page[f'image{dpi}']
                destination = output / 'ocr' / str(dpi) / page['page_id']
                try:
                    result = run_ocr(image, destination, dpi, config, remaining)
                    result['tsv'] = destination.with_suffix('.tsv').relative_to(output).as_posix()
                    return result
                except Exception as exc:
                    return {'dpi': dpi, 'status': 'ERROR', 'text': None, 'error': f'{type(exc).__name__}: {exc}'}

            with ThreadPoolExecutor(max_workers=config['caps']['workers']) as pool:
                futures = {pool.submit(job, page, dpi): (page, dpi)
                           for page in pages if page['render_status'] == 'OK' for dpi in config['text']['dpis']}
                for count, future in enumerate(as_completed(futures), 1):
                    page, dpi = futures[future]
                    result = future.result()
                    page['ocr'][str(dpi)] = result
                    if result['status'] not in ('OK', 'NO_TEXT_DETECTED'):
                        errors.append({'page_id': page['page_id'], 'stage': f'ocr{dpi}', 'error': result.get('error')})
                    if count % 20 == 0 or count == len(futures):
                        write_json(output / 'progress.json', {'finished_jobs': count, 'total_jobs': len(futures), 'utc': utc()})
                        volume.commit()
                        print(f'M2.3 OCR {count}/{len(futures)}; elapsed {time.perf_counter()-started:.1f}s', flush=True)
            write_json(output / 'pages.json', pages)
            summary.update(status='DATA_READY_REVIEW_PENDING' if not errors else 'DATA_READY_WITH_ERRORS_REVIEW_PENDING',
                           page_count=len(pages), completed_ocr_jobs=sum(len(p['ocr']) for p in pages),
                           reference_required_count=sum(p['reference_required'] for p in pages))
    except Exception as exc:
        import traceback
        errors.append({'stage': 'worker', 'error': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()})
        write_json(output / 'pages.json', pages)
        print(errors[-1], flush=True)
    finally:
        artifact_bytes = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
        resources = {'wall_seconds': time.perf_counter() - started, 'render_seconds': render_seconds,
                     'peak_python_and_children_rss_mib': monitor.peak_mib,
                     'gpu_requested': False, 'workers': config['caps']['workers'], 'artifact_bytes': artifact_bytes,
                     'rss_poll_interval_seconds': .02}
        limits = {'wall': resources['wall_seconds'] <= config['caps']['wall_seconds'],
                  'rss': monitor.peak_mib <= config['caps']['ram_mib'],
                  'artifacts': artifact_bytes <= config['caps']['artifact_mib'] * 1024 ** 2}
        if not all(limits.values()):
            summary['status'] = 'FAIL'
        summary.update(completed_utc=utc(), errors=len(errors), resource_checks=limits)
        write_json(output / 'errors.json', errors)
        write_json(output / 'resources.json', resources)
        write_json(output / 'summary.json', summary)
        write_json(output / 'status.json', {'status': summary['status'], 'completed_utc': utc()})
        write_json(output / 'hashes.json', file_manifest(output, exclude=('hashes.json',)))
        volume.commit()
    return summary


def collect(config, run_id):
    import modal
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    return pack_folder(Path(config['modal']['mount_path']) / 'runs' / run_id / 'output', config['caps']['artifact_mib'])


def build_app(config, root):
    import modal
    validate(config)
    image = (modal.Image.debian_slim(python_version=config['modal']['python_version'])
             .apt_install('tesseract-ocr=' + config['text']['engine_package'],
                          'tesseract-ocr-eng=' + config['text']['language_package'])
             .pip_install_from_requirements(str(Path(root) / config['modal']['requirements_file']))
             .env({'OMP_THREAD_LIMIT': '1', 'OMP_NUM_THREADS': '1'})
             .add_local_python_source('qpaf'))
    volume = modal.Volume.from_name(config['modal']['volume_name'], create_if_missing=True)
    app = modal.App(config['modal']['app_name'])
    options = {'image': image, 'cpu': config['modal']['cpu'], 'memory': config['caps']['ram_mib'],
               'retries': 0, 'max_containers': 1,
               'volumes': {config['modal']['mount_path']: volume}}
    work = app.function(timeout=config['caps']['wall_seconds'] + 30, **options)(execute)
    fetch = app.function(timeout=300, **options)(collect)
    return app, work, fetch
