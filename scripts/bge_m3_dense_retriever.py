from __future__ import annotations

import math
from typing import Sequence

import torch
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer


class BGEM3DenseRetriever:
    """Pinned BGE-M3 dense branch compatible with Transformers 4.53.3."""

    def __init__(self, model_path: str, device: str = "cuda") -> None:
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModel.from_pretrained(
            model_path,
            local_files_only=True,
            torch_dtype=torch.float16,
        ).to(self.device).eval()

    def _encode(
        self,
        texts: Sequence[str],
        batch_size: int,
        max_length: int,
        label: str,
    ) -> torch.Tensor:
        embeddings = []
        for start in tqdm(
            range(0, len(texts), batch_size),
            total=math.ceil(len(texts) / batch_size),
            desc=label,
            leave=False,
        ):
            inputs = self.tokenizer(
                list(texts[start : start + batch_size]),
                max_length=max_length,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                dense = self.model(**inputs).last_hidden_state[:, 0]
                dense = torch.nn.functional.normalize(dense, p=2, dim=-1)
            embeddings.append(dense.float().cpu())
        return torch.cat(embeddings, dim=0)

    def forward_queries(self, queries: Sequence[str], batch_size: int) -> torch.Tensor:
        return self._encode(queries, batch_size, max_length=512, label="BGE-M3 queries")

    def forward_passages(self, passages: Sequence[str], batch_size: int) -> torch.Tensor:
        return self._encode(passages, batch_size, max_length=8192, label="BGE-M3 passages")

    @staticmethod
    def get_scores(query_embeddings: torch.Tensor, passage_embeddings: torch.Tensor) -> torch.Tensor:
        return torch.einsum("bd,cd->bc", query_embeddings, passage_embeddings)
