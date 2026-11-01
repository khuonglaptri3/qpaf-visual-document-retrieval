"""F5/F7: score the (query, page OCR) pairs of scripts/lab_rerank.py with a pinned reranker on a Modal GPU.

    MODAL_PROFILE=<profile> QPAF_RERANKER=<key> modal run scripts/modal_lab_rerank.py --pairs <x_pairs.json> --out <x_scores.json> [--limit N]

<key> is one of MODELS (default bge-v2-m3, the F5 model). The key is baked into the image environment so the
module re-imported inside the container picks the same model. Runs on the local side with only the standard
library; the output carries one score per pair in pair order (bge: logit; Qwen3: log-odds of "yes"), plus the
model revision, runtime and SHA-256 of the pairs file. No labels are sent.
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


def download():
    from huggingface_hub import snapshot_download
    snapshot_download(SPEC['repo'], revision=SPEC['revision'], local_dir=MODEL_DIR, allow_patterns=SPEC['files'])


image = (modal.Image.debian_slim(python_version='3.13').pip_install(*PACKAGES)
         .env({'QPAF_RERANKER': KEY}).run_function(download))
app = modal.App(f'qpaf-lab-rerank-{KEY}')


@app.cls(gpu=SPEC['gpu'], image=image, timeout=1800, max_containers=4)
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
    def score(self, pairs):
        """One score per [query, passage] pair, in input order; batches are length-sorted to cut padding."""
        order = sorted(range(len(pairs)), key=lambda i: len(pairs[i][1]))
        out = [0.]*len(pairs)
        with self.torch.no_grad():
            for start in range(0, len(order), SPEC['batch']):
                chosen = order[start:start+SPEC['batch']]
                for i, value in zip(chosen, self.batch_scores([pairs[i] for i in chosen])):
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
    manifest = {'key': KEY, 'model': SPEC['repo'], 'revision': SPEC['revision'], 'max_length': MAX_LENGTH,
                'dtype': SPEC['dtype'], 'gpu': SPEC['gpu'], 'devices': sorted({r['device'] for r in results}),
                'torch': results[0]['torch'], 'packages': list(PACKAGES), 'pairs': len(items), 'limit': limit,
                'instruction': QWEN_INSTRUCTION if SPEC['kind'] == 'qwen3' else None,
                'seconds': round(time.perf_counter()-started, 1),
                'finished_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    body = {'pairs_sha256': hashlib.sha256(raw).hexdigest(), 'manifest': manifest, 'scores': scores}
    Path(out).write_text(json.dumps(body, indent=1)+'\n', encoding='utf-8')
    print(json.dumps(manifest, indent=1))
