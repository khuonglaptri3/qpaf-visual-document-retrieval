"""A005 Stage 1 calibration C2: OCR and GPU encode/score timing on a label-free ViMDoc page sample.

Reads only the archive and the A007 v2 canonical pages. It never opens qrels or
the query table; the eight query strings below are synthetic and only time the
encoders. Output goes to a create-once directory per Modal call.

    modal run a005_c2_calibration_modal.py --pages-sha256 <sha> --sample-size 128
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import modal

APP_NAME = 'qpaf-a005-c2-calibration'
ROOT = Path(__file__).resolve().parent
VOLUME_ROOT = Path('/vol')
ARCHIVE = 'datasets/vimdoc/25657f1fe0358f49147148ca89e231291ba42788/ViMDoc_pages.tar.gz'
PAGES = 'audits/vimdoc/vimdoc_identity_v2/canonical_pages.jsonl'
OUTPUT = 'a005/c2'
SAMPLE_SALT = 'a005-c2:20260820:'
SYNTHETIC_QUERIES = [
    'What was the total revenue reported in the annual financial statement?',
    'Which table lists the population of each province?',
    'How many participants were enrolled in the clinical study?',
    'What is the deadline for submitting the application form?',
    'Which chart shows the trend of exports over five years?',
    'Who is the chairman of the board of directors?',
    'What safety instructions are given for operating the machine?',
    'What percentage of respondents agreed with the policy?',
]

volume = modal.Volume.from_name('qpaf-artifacts', create_if_missing=False)
hf_secret = modal.Secret.from_name('huggingface-secret', required_keys=['HF_TOKEN'])
app = modal.App(APP_NAME)
ocr_image = (modal.Image.debian_slim(python_version='3.11')
             .apt_install('tesseract-ocr=5.3.0-2', 'tesseract-ocr-eng=1:4.1.0-2')
             .pip_install('pillow==11.3.0', 'pytesseract==0.3.13'))
gpu_image = (modal.Image.debian_slim(python_version='3.11').apt_install('poppler-utils')
             .pip_install_from_requirements(str(ROOT/'requirements-lock.txt'), extra_options='--require-hashes')
             .add_local_file(str(ROOT/'scripts/colqwen25_retriever.py'), '/root/scripts/colqwen25_retriever.py')
             .add_local_file(str(ROOT/'scripts/bge_m3_dense_retriever.py'), '/root/scripts/bge_m3_dense_retriever.py')
             .add_local_file(str(ROOT/'configs/vimdoc_m3_local_v1.json'), '/root/configs/vimdoc_m3_local_v1.json'))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def select_sample(rows, size):
    """Label-free: the `size` pages with the smallest SHA-256 of salt + page ID."""
    return sorted(rows, key=lambda row: sha256((SAMPLE_SALT+row['page_id']).encode('utf-8')))[:size]


def normalize(text):
    if '\x00' in text:
        raise ValueError('OCR text contains NUL')
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


@app.function(image=ocr_image, cpu=4, memory=8192, timeout=1800, volumes={str(VOLUME_ROOT): volume}, retries=0)
def c2_ocr(pages_sha256: str, sample_size: int) -> dict:
    import subprocess
    import tarfile
    from concurrent.futures import ProcessPoolExecutor
    data = (VOLUME_ROOT/PAGES).read_bytes()
    if sha256(data) != pages_sha256:
        raise ValueError('v2 canonical pages differ from the pinned hash')
    sample = select_sample([json.loads(line) for line in data.decode('utf-8').splitlines()], sample_size)
    wanted = {row['canonical_asset_path']: row for row in sample}
    call_id = modal.current_function_call_id()
    out = VOLUME_ROOT/OUTPUT/call_id
    (out/'images').mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    images = {}
    with tarfile.open(VOLUME_ROOT/ARCHIVE, 'r|gz') as archive:
        for member in archive:
            row = wanted.get(member.name)
            if row is None:
                continue
            payload = archive.extractfile(member).read()
            if sha256(payload) != row['asset_sha256']:
                raise ValueError(f'asset hash mismatch: {member.name}')
            images[row['page_id']] = payload
            (out/'images'/row['page_id']).write_bytes(payload)
            if len(images) == len(wanted):
                break
    extract_seconds = time.perf_counter()-started
    if len(images) != len(wanted):
        raise ValueError(f'only {len(images)} of {len(wanted)} sample assets found')
    order = sorted(images, key=lambda p: p.encode('utf-8'))
    sequential, rows = [], []
    for page_id in order:
        t0 = time.perf_counter()
        text = normalize(_ocr(images[page_id]))
        sequential.append(time.perf_counter()-t0)
        encoded = text.encode('utf-8')
        rows.append({'page_id': page_id, 'status': 'SUCCESS' if text.strip() else 'SUCCESS_EMPTY',
                     'text': text, 'text_sha256': sha256(encoded), 'character_count': len(text)})
    t0 = time.perf_counter()
    with ProcessPoolExecutor(4) as pool:
        parallel_texts = list(pool.map(_ocr, [images[p] for p in order]))
    parallel_seconds = time.perf_counter()-t0
    mismatched = sum(normalize(a) != r['text'] for a, r in zip(parallel_texts, rows))
    with (out/'ocr.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')
    version = subprocess.run(['tesseract', '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    report = {'call_id': call_id, 'output_dir': f'{OUTPUT}/{call_id}', 'pages': len(rows),
              'png': sum(p.lower().endswith('.png') for p in order), 'jpg': sum(p.lower().endswith('.jpg') for p in order),
              'extract_seconds': extract_seconds, 'ocr_sequential_seconds': sum(sequential),
              'ocr_seconds_per_page_sequential': sum(sequential)/len(rows),
              'ocr_parallel4_seconds': parallel_seconds, 'ocr_seconds_per_page_parallel4': parallel_seconds/len(rows),
              'parallel_text_mismatches': mismatched, 'empty_pages': sum(r['status'] == 'SUCCESS_EMPTY' for r in rows),
              'tesseract_version': version, 'ocr_jsonl_sha256': sha256((out/'ocr.jsonl').read_bytes())}
    _write_new(out/'ocr_timing.json', report)
    volume.commit()
    return report


def _ocr(payload):
    import io
    from PIL import Image
    import pytesseract
    image = Image.open(io.BytesIO(payload))
    image.load()
    return pytesseract.image_to_string(image.convert('RGB'), lang='eng', config='--oem 3 --psm 3')


@app.function(image=gpu_image, gpu='L4', cpu=4, memory=32768, timeout=1800, secrets=[hf_secret],
              volumes={str(VOLUME_ROOT): volume}, retries=0)
def c2_gpu(output_dir: str) -> dict:
    import io
    import sys
    import torch
    from huggingface_hub import snapshot_download
    from PIL import Image
    sys.path.insert(0, '/root')
    from scripts.bge_m3_dense_retriever import BGEM3DenseRetriever
    from scripts.colqwen25_retriever import ColQwen25Retriever
    volume.reload()
    out = VOLUME_ROOT/output_dir
    rows = [json.loads(line) for line in (out/'ocr.jsonl').read_text(encoding='utf-8').splitlines()]
    images = []
    for row in rows:
        image = Image.open(io.BytesIO((out/'images'/row['page_id']).read_bytes()))
        image.load()
        images.append(image.convert('RGB'))
    models = json.loads(Path('/root/configs/vimdoc_m3_local_v1.json').read_text(encoding='utf-8'))['retrievers']
    report = {'pages': len(rows), 'gpu': torch.cuda.get_device_name(0)}
    visual = models['visual']
    t0 = time.perf_counter()
    colqwen = ColQwen25Retriever(base_model_id=visual['base_id'], base_revision=visual['base_revision'],
                                 adapter_model_id=visual['id'], adapter_revision=visual['revision'])
    report['colqwen_load_seconds'] = time.perf_counter()-t0
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    passages = colqwen.forward_passages(images, batch_size=2)
    torch.cuda.synchronize()
    report['colqwen_passage_seconds'] = time.perf_counter()-t0
    report['colqwen_seconds_per_page'] = report['colqwen_passage_seconds']/len(rows)
    report['colqwen_tokens_per_page_mean'] = sum(p.shape[0] for p in passages)/len(passages)
    queries = colqwen.forward_queries(SYNTHETIC_QUERIES, batch_size=8)
    t0 = time.perf_counter()
    cpu_scores = colqwen.get_scores(queries, passages)
    report['maxsim_cpu_seconds'] = time.perf_counter()-t0
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    gpu_scores = colqwen.processor.score(queries, passages, batch_size=128, device='cuda').cpu()
    torch.cuda.synchronize()
    report['maxsim_gpu_seconds'] = time.perf_counter()-t0
    pairs = len(queries)*len(passages)
    report.update({'maxsim_pairs': pairs, 'maxsim_cpu_pairs_per_second': pairs/report['maxsim_cpu_seconds'],
                   'maxsim_gpu_pairs_per_second': pairs/report['maxsim_gpu_seconds'],
                   'maxsim_gpu_cpu_max_abs_difference': (gpu_scores.float()-cpu_scores.float()).abs().max().item(),
                   'maxsim_gpu_cpu_ranking_disagreements': int(
                       (gpu_scores.argsort(dim=1, descending=True) != cpu_scores.argsort(dim=1, descending=True))
                       .any(dim=1).sum())})
    del colqwen
    torch.cuda.empty_cache()
    dense = models['dense']
    t0 = time.perf_counter()
    bge = BGEM3DenseRetriever(snapshot_download(dense['id'], revision=dense['revision']))
    report['bge_load_seconds'] = time.perf_counter()-t0
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    bge.forward_passages([row['text'] for row in rows], batch_size=8)
    torch.cuda.synchronize()
    report['bge_passage_seconds'] = time.perf_counter()-t0
    report['bge_seconds_per_page'] = report['bge_passage_seconds']/len(rows)
    report['peak_cuda_allocated_gib'] = torch.cuda.max_memory_allocated()/2**30
    _write_new(out/'gpu_timing.json', report)
    volume.commit()
    return report


@app.local_entrypoint()
def main(pages_sha256: str, sample_size: int = 128):
    ocr = c2_ocr.remote(pages_sha256, sample_size)
    print(json.dumps(ocr, indent=2))
    print(json.dumps(c2_gpu.remote(ocr['output_dir']), indent=2))
