from __future__ import annotations

from typing import Any

import torch
from PIL import Image
from torch.utils.data import DataLoader
from transformers.utils.import_utils import is_flash_attn_2_available

from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from huggingface_hub import snapshot_download
from peft import PeftModel
from vidore_benchmark.utils.data_utils import ListDataset
from vidore_benchmark.utils.torch_utils import get_torch_device


class ColQwen25Retriever:
    """Minimal ColQwen2.5 adapter missing from vidore-benchmark 5.0.0."""

    def __init__(
        self,
        base_model_id: str,
        base_revision: str,
        adapter_model_id: str,
        adapter_revision: str,
        device: str = "auto",
        num_workers: int = 0,
    ) -> None:
        self.device = get_torch_device(device)
        self.num_workers = num_workers
        base_model = ColQwen2_5.from_pretrained(
            base_model_id,
            revision=base_revision,
            torch_dtype=torch.bfloat16,
            device_map=self.device,
            attn_implementation="flash_attention_2" if is_flash_attn_2_available() else None,
        )
        self.model = PeftModel.from_pretrained(
            base_model,
            adapter_model_id,
            revision=adapter_revision,
        ).eval()
        processor_snapshot = snapshot_download(
            repo_id=adapter_model_id,
            revision=adapter_revision,
            allow_patterns=[
                "*.json",
                "*.jinja",
                "*.txt",
                "*.model",
                "merges.txt",
                "vocab.json",
                "additional_chat_templates/*",
            ],
        )
        self.processor = ColQwen2_5_Processor.from_pretrained(
            processor_snapshot,
            local_files_only=True,
        )

    def _process_images(self, images: list[Image.Image]) -> Any:
        return self.processor.process_images(images=images).to(self.device)

    def _process_queries(self, queries: list[str]) -> Any:
        return self.processor.process_queries(queries=queries).to(self.device)

    def forward_passages(
        self,
        passages: list[Image.Image],
        batch_size: int,
    ) -> list[torch.Tensor]:
        loader = DataLoader(
            ListDataset[Image.Image](passages),
            batch_size=batch_size,
            shuffle=False,
            collate_fn=self._process_images,
            num_workers=self.num_workers,
        )
        embeddings: list[torch.Tensor] = []
        with torch.no_grad():
            for batch in loader:
                embeddings.extend(self.model(**batch).cpu().unbind())
        return embeddings

    def forward_queries(
        self,
        queries: list[str],
        batch_size: int,
    ) -> list[torch.Tensor]:
        loader = DataLoader(
            ListDataset[str](queries),
            batch_size=batch_size,
            shuffle=False,
            collate_fn=self._process_queries,
            num_workers=self.num_workers,
        )
        embeddings: list[torch.Tensor] = []
        with torch.no_grad():
            for batch in loader:
                embeddings.extend(self.model(**batch).cpu().unbind())
        return embeddings

    def get_scores(
        self,
        query_embeddings: list[torch.Tensor],
        passage_embeddings: list[torch.Tensor],
        batch_size: int = 128,
    ) -> torch.Tensor:
        return self.processor.score(
            query_embeddings,
            passage_embeddings,
            batch_size=batch_size,
            device="cpu",
        )
