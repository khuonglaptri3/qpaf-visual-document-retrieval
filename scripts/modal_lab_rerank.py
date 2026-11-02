"""F5/F7/F9: score the (query, page OCR) pairs of scripts/lab_rerank.py with a pinned reranker on a Modal GPU.

    $env:MODAL_PROFILE='<profile>'; $env:QPAF_RERANKER='<key>'; modal run --detach scripts/modal_lab_rerank.py --pairs <x_pairs.json>
    $env:MODAL_PROFILE='<profile>'; $env:QPAF_RERANKER='<key>'; modal run scripts/modal_lab_rerank.py --pairs <x_pairs.json> --stage collect --out <x_scores.json>

<key> is one of MODELS (default bge-v2-m3, the F5 model). The key is baked into the image environment so the
module re-imported inside the container picks the same model. `submit` (the default) spawns one call per chunk
of pairs not yet on the `qpaf-lab-rerank` Volume and returns; with --detach the app finishes those calls even
after the local client exits. Each call writes its chunk to the Volume, so rerunning `submit` only resends missing
chunks. `collect` uses no GPU: it reads the chunks back and writes one score per pair in pair order (bge: logit;
Qwen3: log-odds of "yes"), plus the model revision, runtime and SHA-256 of the pairs file. No labels are sent.

The buiphat251399 workspace allows 10 GPUs at once: each app uses up to max_containers=4, so run at most two
GPU apps (this script or scripts/modal_lab_visual_rerank.py) at the same time.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import modal

QWEN_INSTRUCTION = 'Given a question, retrieve the document page that contains the answer'
MODELS = {
    'bge-v2-m3': {'repo': 'BAAI/bge-reranker-v2-m3', 'revision': '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e',
                  'kind': 'cross-encoder', 'dtype': 'float16', 'batch': 32,
                  'gpu': ['L4', 'A10', 'T4'],  # preference order; L4 alone queued 24 min on the first smoke run
                  'files': ['config.json', 'model.safetensors', 'sentencepiece.bpe.model', 'special_tokens_map.json',
                            'tokenizer.json', 'tokenizer_config.json']},
    'qwen3-0.6b': {'repo': 'Qwen/Qwen3-Reranker-0.6B', 'revision': 'e61197ed45024b0ed8a2d74b80b4d909f1255473',
                   'kind': 'qwen3', 'dtype': 'bfloat16', 'batch': 16, 'gpu': ['L4', 'A10', 'L40S'],
                   'files': ['*.json', '*.safetensors', 'merges.txt']},
    'qwen3-4b': {'repo': 'Qwen/Qwen3-Reranker-4B', 'revision': '22e683669bc0f0bd69640a1354a6d0aebcfeede5',
                 'kind': 'qwen3', 'dtype': 'bfloat16', 'batch': 8, 'gpu': ['L4', 'A10', 'L40S'],
                 'files': ['*.json', '*.safetensors', 'merges.txt']},
}
KEY = os.environ.get('QPAF_RERANKER', 'bge-v2-m3')
SPEC = MODELS[KEY]
MAX_LENGTH = 1024
CHUNK = 1000
PACKAGES = ('torch==2.11.0', 'transformers==4.53.3', 'huggingface_hub>=0.30,<1.0', 'numpy==2.2.6')
MODEL_DIR = '/model'
OUT = '/out'
volume = modal.Volume.from_name('qpaf-lab-rerank', create_if_missing=True)


def download():
    from huggingface_hub import snapshot_download
    snapshot_download(SPEC['repo'], revision=SPEC['revision'], local_dir=MODEL_DIR, allow_patterns=SPEC['files'])


image = (modal.Image.debian_slim(python_version='3.13').pip_install(*PACKAGES)
         .env({'QPAF_RERANKER': KEY}).run_function(download))
app = modal.App(f'qpaf-lab-rerank-{KEY}')


@app.cls(gpu=SPEC['gpu'], image=image, timeout=1800, max_containers=4, volumes={OUT: volume})
class Reranker:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        dtype = getattr(torch, SPEC['dtype'])
        if SPEC['kind'] == 'qwen3':
            # Prompt and yes/no read-out follow the Qwen3-Reranker model card (Transformers usage).
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, padding_side='left')
            self.model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, torch_dtype=dtype).cuda().eval()
            self.prefix = self.tokenizer.encode(
                '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the '
                'Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n',
                add_special_tokens=False)
            self.suffix = self.tokenizer.encode('<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n',
                                                add_special_tokens=False)
            self.yes, self.no = (self.tokenizer.convert_tokens_to_ids(t) for t in ('yes', 'no'))
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR, torch_dtype=dtype).cuda().eval()

    def batch_scores(self, batch):
        if SPEC['kind'] == 'qwen3':
            texts = [f'<Instruct>: {QWEN_INSTRUCTION}\n<Query>: {q}\n<Document>: {d}' for q, d in batch]
            encoded = self.tokenizer(texts, padding=False, truncation='longest_first', return_attention_mask=False,
                                     max_length=MAX_LENGTH-len(self.prefix)-len(self.suffix))
            encoded['input_ids'] = [self.prefix+ids+self.suffix for ids in encoded['input_ids']]
            inputs = self.tokenizer.pad(encoded, padding=True, return_tensors='pt').to('cuda')
            last = self.model(**inputs).logits[:, -1, :].float()
            return (last[:, self.yes]-last[:, self.no]).cpu().tolist()  # log-odds of "yes"
        inputs = self.tokenizer(batch, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors='pt').to('cuda')
        return self.model(**inputs, return_dict=True).logits.view(-1).float().cpu().tolist()

    @modal.method()
    def score(self, run, index, pairs):
        """Write one score per [query, passage] pair, in input order, to <run>/<index>.json on the Volume.

        Batches are length-sorted to cut padding; a chunk already on the Volume is left as it is.
        """
        target = Path(OUT)/run/f'{index:05d}.json'
        volume.reload()
        if target.exists():
            return
        started = time.perf_counter()
        order = sorted(range(len(pairs)), key=lambda i: len(pairs[i][1]))
        out = [0.]*len(pairs)
        with self.torch.no_grad():
            for start in range(0, len(order), SPEC['batch']):
                chosen = order[start:start+SPEC['batch']]
                for i, value in zip(chosen, self.batch_scores([pairs[i] for i in chosen])):
                    out[i] = value
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'scores': out, 'torch': self.torch.__version__,
                                      'device': self.torch.cuda.get_device_name(),
                                      'seconds': round(time.perf_counter()-started, 1)}))
        volume.commit()


def finished_chunks(run):
    """Chunk index -> Volume path of every chunk already written for this run."""
    prefix = f'{run}/'
    paths = [entry.path.lstrip('/') for entry in volume.listdir('/', recursive=True)]
    return {int(Path(p).stem): p for p in paths if p.startswith(prefix) and p.endswith('.json')}


@app.local_entrypoint()
def main(pairs: str, stage: str = 'submit', out: str = '', limit: int = 0):
    raw = Path(pairs).read_bytes()
    data = json.loads(raw)
    items = data['pairs'][:limit] if limit else data['pairs']
    texts = [[data['queries'][q], data['pages'][p]] for q, p in items]
    chunks = [texts[i:i+CHUNK] for i in range(0, len(texts), CHUNK)]
    digest = hashlib.sha256(raw).hexdigest()
    run = f'{KEY}/{digest[:16]}-limit{limit}'
    done = finished_chunks(run)
    if stage == 'submit':
        missing = [i for i in range(len(chunks)) if i not in done]
        if missing:
            Reranker().score.spawn_map([run]*len(missing), missing, [chunks[i] for i in missing])
        print(f'{run}: {len(chunks)} chunks, {len(done)} already on the Volume, {len(missing)} submitted. '
              'Without --detach the app stops when this command returns.')
        return
    if stage != 'collect':
        raise SystemExit("stage must be 'submit' or 'collect'")
    if not out:
        raise SystemExit('collect needs --out')
    if len(done) != len(chunks):
        raise SystemExit(f'{run}: {len(chunks)-len(done)} of {len(chunks)} chunks not on the Volume yet')
    results = [json.loads(b''.join(volume.read_file(done[i]))) for i in range(len(chunks))]
    scores = [s for r in results for s in r['scores']]
    if len(scores) != len(items) or not all(s == s and abs(s) != float('inf') for s in scores):
        raise SystemExit('reranker returned a wrong count or a non-finite score')
    manifest = {'key': KEY, 'model': SPEC['repo'], 'revision': SPEC['revision'], 'max_length': MAX_LENGTH,
                'dtype': SPEC['dtype'], 'gpu': SPEC['gpu'], 'devices': sorted({r['device'] for r in results}),
                'torch': results[0]['torch'], 'packages': list(PACKAGES), 'pairs': len(items), 'limit': limit,
                'instruction': QWEN_INSTRUCTION if SPEC['kind'] == 'qwen3' else None,
                'volume_run': run, 'gpu_seconds': round(sum(r['seconds'] for r in results), 1),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    body = {'pairs_sha256': digest, 'manifest': manifest, 'scores': scores}
    Path(out).write_text(json.dumps(body, indent=1)+'\n', encoding='utf-8')
    print(json.dumps(manifest, indent=1))
