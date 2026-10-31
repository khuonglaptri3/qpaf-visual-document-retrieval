"""F5: score the (query, page OCR) pairs of scripts/lab_rerank.py with a pinned cross-encoder on a Modal GPU.

    MODAL_PROFILE=<profile> modal run scripts/modal_lab_rerank.py --pairs <x_pairs.json> --out <x_scores.json> [--limit N]

Runs on the local side with only the standard library; the output carries the raw logits in pair order plus the
model revision, runtime and SHA-256 of the pairs file. No labels are sent.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import modal

MODEL = 'BAAI/bge-reranker-v2-m3'
REVISION = '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'
MAX_LENGTH = 1024
BATCH = 32
CHUNK = 1000
GPU = ['L4', 'A10', 'T4']  # preference order; L4 alone queued 24 min on the first smoke run
PACKAGES = ('torch==2.11.0', 'transformers==4.53.3', 'huggingface_hub>=0.30,<1.0', 'numpy==2.2.6')
MODEL_DIR = '/model'


def download():
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL, revision=REVISION, local_dir=MODEL_DIR,
                      allow_patterns=['config.json', 'model.safetensors', 'sentencepiece.bpe.model',
                                      'special_tokens_map.json', 'tokenizer.json', 'tokenizer_config.json'])


image = (modal.Image.debian_slim(python_version='3.13').pip_install(*PACKAGES)
         .run_function(download))
app = modal.App('qpaf-lab-f5-rerank')


@app.cls(gpu=GPU, image=image, timeout=1800, max_containers=4)
class Reranker:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, torch_dtype=torch.float16).cuda().eval()

    @modal.method()
    def score(self, pairs):
        """Logits for [query, passage] pairs, in input order; batches are length-sorted to cut padding."""
        order = sorted(range(len(pairs)), key=lambda i: len(pairs[i][1]))
        out = [0.]*len(pairs)
        with self.torch.no_grad():
            for start in range(0, len(order), BATCH):
                chosen = order[start:start+BATCH]
                inputs = self.tokenizer([pairs[i] for i in chosen], padding=True, truncation=True,
                                        max_length=MAX_LENGTH, return_tensors='pt').to('cuda')
                logits = self.model(**inputs, return_dict=True).logits.view(-1).float().cpu().tolist()
                for i, value in zip(chosen, logits):
                    out[i] = value
        return {'scores': out, 'torch': self.torch.__version__, 'device': self.torch.cuda.get_device_name()}


@app.local_entrypoint()
def main(pairs: str, out: str, limit: int = 0):
    raw = Path(pairs).read_bytes()
    data = json.loads(raw)
    items = data['pairs'][:limit] if limit else data['pairs']
    texts = [[data['queries'][q], data['pages'][p]] for q, p in items]
    chunks = [texts[i:i+CHUNK] for i in range(0, len(texts), CHUNK)]
    started = time.perf_counter()
    results = list(Reranker().score.map(chunks))
    scores = [s for r in results for s in r['scores']]
    if len(scores) != len(items) or not all(s == s and abs(s) != float('inf') for s in scores):
        raise SystemExit('reranker returned a wrong count or a non-finite score')
    manifest = {'model': MODEL, 'revision': REVISION, 'max_length': MAX_LENGTH, 'dtype': 'float16', 'gpu': GPU,
                'devices': sorted({r['device'] for r in results}), 'torch': results[0]['torch'],
                'packages': list(PACKAGES), 'pairs': len(items), 'limit': limit,
                'seconds': round(time.perf_counter()-started, 1),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    body = {'pairs_sha256': hashlib.sha256(raw).hexdigest(), 'manifest': manifest, 'scores': scores}
    Path(out).write_text(json.dumps(body, indent=1)+'\n', encoding='utf-8')
    print(json.dumps(manifest, indent=1))
