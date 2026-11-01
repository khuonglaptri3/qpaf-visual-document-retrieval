"""F8: score the (query, page IMAGE) pairs of scripts/lab_rerank.py with a pinned multimodal reranker on Modal.

    MODAL_PROFILE=<profile> modal run scripts/modal_lab_visual_rerank.py --pairs <x_pairs.json> --stage prepare
    MODAL_PROFILE=<profile> modal run scripts/modal_lab_visual_rerank.py --pairs <x_pairs.json> --stage score --out <x_scores_mono.json> [--limit N]

prepare puts exactly the pages of the pairs file on the Modal volume VOLUME, from the public sources the repo
already pins: ViMDoc images from kaistdata/ViMDoc ViMDoc_pages.tar.gz (streamed; the archive SHA-256 must match
configs/vimdoc_archive_content_audit_v1.json), ViDoSeek pages rendered from Qiuchen-Wang/ViDoSeek PDFs at
RENDER_DPI. score writes one log-odds of "True" per pair, in pair order, in the scripts/modal_lab_rerank.py
format, so scripts/lab_rerank.py screen/gate read it unchanged. Only query text and page IDs leave this machine.

The buiphat251399 workspace allows 10 GPUs at once; the scorer uses up to max_containers=4, so keep at most two
GPU apps (this one or scripts/modal_lab_rerank.py) running together. prepare is CPU-only.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import modal

VOLUME = 'qpaf-lab-pages'
MOUNT = '/pages'
VIMDOC = {'repo': 'kaistdata/ViMDoc', 'revision': '25657f1fe0358f49147148ca89e231291ba42788',
          'file': 'ViMDoc_pages.tar.gz', 'sha256': 'de569c8d4d499b8fac84d4d03a0ddb59054e30351dcb7b1e6da3d1945d2d2c71'}
VIDOSEEK = {'repo': 'Qiuchen-Wang/ViDoSeek', 'revision': 'e91a92ba5f38690696c7e66be5c5474b54c6e791',
            'file': 'vidoseek_pdf_document.zip'}
RENDER_DPI = 150
BASE = {'repo': 'Qwen/Qwen2-VL-2B-Instruct', 'revision': '895c3a49bc3fa70a340399125c650a463535e71c'}
ADAPTER = {'repo': 'lightonai/MonoQwen2-VL-v0.1', 'revision': '7f91c3a5d7ddbfe33fe0f70f75121c1225ad8af5'}
PROMPT = ('Assert the relevance of the previous image document to the following query, '
          'answer True or False. The query is: {query}')  # verbatim from the MonoQwen2-VL model card
MAX_PIXELS = 1024*28*28
BATCH = 8
CHUNK = 400
GPU = ['L4', 'A10', 'L40S']  # bfloat16; no T4
DATA_PACKAGES = ('huggingface_hub>=0.30,<1.0', 'requests>=2.32,<3', 'pillow>=11,<12', 'pypdfium2>=4.30,<5')
GPU_PACKAGES = ('torch==2.11.0', 'transformers==4.53.3', 'peft>=0.15,<0.18', 'numpy==2.2.6')

volume = modal.Volume.from_name(VOLUME, create_if_missing=True)
data_image = modal.Image.debian_slim(python_version='3.13').pip_install(*DATA_PACKAGES)


def download_models():
    from huggingface_hub import snapshot_download
    snapshot_download(BASE['repo'], revision=BASE['revision'], local_dir='/models/base',
                      allow_patterns=['*.json', '*.safetensors', 'merges.txt'])
    snapshot_download(ADAPTER['repo'], revision=ADAPTER['revision'], local_dir='/models/adapter',
                      allow_patterns=['adapter_config.json', 'adapter_model.safetensors'])


gpu_image = data_image.pip_install(*GPU_PACKAGES).run_function(download_models)
app = modal.App('qpaf-lab-f8-visual-rerank')


def versions(*names):
    from importlib.metadata import version
    return {name: version(name) for name in names}


@app.function(image=data_image, volumes={MOUNT: volume}, cpu=2, memory=8192, timeout=3*3600)
def prepare_vimdoc(needed):
    """Stream the tarball once, hash it end to end, keep only pages/<page_id> members that are needed."""
    import requests
    import tarfile
    from huggingface_hub import hf_hub_url

    class Hashing:
        def __init__(self, raw):
            self.raw, self.digest, self.bytes = raw, hashlib.sha256(), 0

        def read(self, size=-1):
            block = self.raw.read(size)
            self.digest.update(block)
            self.bytes += len(block)
            return block

    wanted, out = set(needed), Path(MOUNT)/'vimdoc'
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}
    url = hf_hub_url(VIMDOC['repo'], VIMDOC['file'], repo_type='dataset', revision=VIMDOC['revision'])
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        stream = Hashing(response.raw)
        with tarfile.open(fileobj=stream, mode='r|gz') as tar:
            for member in tar:
                name = member.name.split('/')[-1]
                if member.isfile() and name in wanted:
                    if name in hashes:
                        raise RuntimeError(f'two archive members named {name}')
                    data = tar.extractfile(member).read()
                    (out/name).write_bytes(data)
                    hashes[name] = hashlib.sha256(data).hexdigest()
        while stream.read(1 << 20):  # trailing bytes after the tar end marker still count toward the hash
            pass
    archive = stream.digest.hexdigest()
    if archive != VIMDOC['sha256']:
        raise RuntimeError(f'archive SHA-256 {archive} differs from the pinned {VIMDOC["sha256"]}')
    missing = sorted(wanted-set(hashes))
    if missing:
        raise RuntimeError(f'{len(missing)} needed pages missing from the archive, e.g. {missing[:3]}')
    manifest = {'dataset': 'vimdoc', 'source': VIMDOC, 'archive_bytes': stream.bytes, 'pages': len(hashes),
                'page_sha256': hashes, 'versions': versions('requests'),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (out/'_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    volume.commit()
    return {k: v for k, v in manifest.items() if k != 'page_sha256'}


@app.function(image=data_image, volumes={MOUNT: volume}, cpu=4, memory=8192, timeout=2*3600)
def prepare_vidoseek(needed):
    """Render <stem>_page_NNNN as page NNNN (1-based) of <stem>.pdf at RENDER_DPI, PNG."""
    import zipfile
    import pypdfium2
    from huggingface_hub import hf_hub_download
    out = Path(MOUNT)/'vidoseek'
    out.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(VIDOSEEK['repo'], VIDOSEEK['file'], repo_type='dataset', revision=VIDOSEEK['revision'])
    zip_sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    by_doc = {}
    for page_id in needed:
        stem, number = page_id.rsplit('_page_', 1)
        by_doc.setdefault(stem, []).append((page_id, int(number)))
    hashes = {}
    with zipfile.ZipFile(path) as archive:
        members = {Path(m).stem: m for m in archive.namelist() if m.lower().endswith('.pdf')}
        for stem, pages in by_doc.items():
            if stem not in members:
                raise RuntimeError(f'no PDF for {stem}')
            pdf = pypdfium2.PdfDocument(archive.read(members[stem]))
            for page_id, number in pages:
                image = pdf[number-1].render(scale=RENDER_DPI/72).to_pil().convert('RGB')
                target = out/f'{page_id}.png'
                image.save(target, format='PNG')
                hashes[page_id] = hashlib.sha256(target.read_bytes()).hexdigest()
            pdf.close()
    manifest = {'dataset': 'vidoseek', 'source': VIDOSEEK, 'zip_sha256': zip_sha, 'render_dpi': RENDER_DPI,
                'pages': len(hashes), 'page_sha256': hashes, 'versions': versions('pypdfium2', 'pillow'),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (out/'_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    volume.commit()
    return {k: v for k, v in manifest.items() if k != 'page_sha256'}


@app.cls(gpu=GPU, image=gpu_image, volumes={MOUNT: volume}, timeout=1800, max_containers=4)
class VisualReranker:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained('/models/base', max_pixels=MAX_PIXELS)
        self.processor.tokenizer.padding_side = 'left'  # the last position is the answer token for every row
        model = Qwen2VLForConditionalGeneration.from_pretrained('/models/base', torch_dtype=torch.bfloat16)
        model.load_adapter('/models/adapter')
        self.model = model.cuda().eval()
        self.true_id, self.false_id = (self.processor.tokenizer.convert_tokens_to_ids(t) for t in ('True', 'False'))

    @modal.method()
    def score(self, dataset, pairs):
        """Log-odds of "True" for [query, page_id] pairs, in input order."""
        from PIL import Image
        suffix = '' if dataset == 'vimdoc' else '.png'  # ViMDoc page IDs already carry the file extension
        out = []
        with self.torch.no_grad():
            for start in range(0, len(pairs), BATCH):
                batch = pairs[start:start+BATCH]
                images = [Image.open(Path(MOUNT)/dataset/f'{page_id}{suffix}').convert('RGB') for _, page_id in batch]
                texts = [self.processor.apply_chat_template(
                    [{'role': 'user', 'content': [{'type': 'image'}, {'type': 'text', 'text': PROMPT.format(query=q)}]}],
                    tokenize=False, add_generation_prompt=True) for q, _ in batch]
                inputs = self.processor(text=texts, images=images, padding=True, return_tensors='pt').to('cuda')
                last = self.model(**inputs).logits[:, -1, :].float()
                out += (last[:, self.true_id]-last[:, self.false_id]).cpu().tolist()
        return {'scores': out, 'torch': self.torch.__version__, 'device': self.torch.cuda.get_device_name(),
                'versions': versions('transformers', 'peft')}


@app.local_entrypoint()
def main(pairs: str, stage: str, out: str = '', limit: int = 0):
    raw = Path(pairs).read_bytes()
    data = json.loads(raw)
    dataset = data['dataset']
    if stage == 'prepare':
        prepare = prepare_vimdoc if dataset == 'vimdoc' else prepare_vidoseek
        print(json.dumps(prepare.remote(sorted(data['pages'])), indent=1))
        return
    items = data['pairs'][:limit] if limit else data['pairs']
    queries = [[data['queries'][q], p] for q, p in items]
    chunks = [queries[i:i+CHUNK] for i in range(0, len(queries), CHUNK)]
    started = time.perf_counter()
    results = list(VisualReranker().score.starmap([(dataset, chunk) for chunk in chunks]))
    scores = [s for r in results for s in r['scores']]
    if len(scores) != len(items) or not all(s == s and abs(s) != float('inf') for s in scores):
        raise SystemExit('reranker returned a wrong count or a non-finite score')
    manifest = {'key': 'monoqwen2-vl', 'model': ADAPTER['repo'], 'revision': ADAPTER['revision'], 'base': BASE,
                'prompt': PROMPT, 'max_pixels': MAX_PIXELS, 'dtype': 'bfloat16', 'gpu': GPU,
                'devices': sorted({r['device'] for r in results}), 'torch': results[0]['torch'],
                'versions': results[0]['versions'], 'pages_volume': VOLUME, 'pairs': len(items), 'limit': limit,
                'seconds': round(time.perf_counter()-started, 1),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    body = {'pairs_sha256': hashlib.sha256(raw).hexdigest(), 'manifest': manifest, 'scores': scores}
    Path(out).write_text(json.dumps(body, indent=1)+'\n', encoding='utf-8')
    print(json.dumps(manifest, indent=1))
