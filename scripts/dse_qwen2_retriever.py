from __future__ import annotations

import torch
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from transformers.utils.import_utils import is_flash_attn_2_available
from vidore_benchmark.retrievers.base_vision_retriever import BaseVisionRetriever
from vidore_benchmark.retrievers.dse_qwen2_retriever import DSEQwen2Retriever
from vidore_benchmark.utils.torch_utils import get_torch_device


class DSEQwen2DirectRetriever(DSEQwen2Retriever):
    """DSE-Qwen2 loader that places pinned bf16 weights directly on the GPU."""

    def __init__(
        self,
        pretrained_model_name_or_path: str,
        num_image_tokens: int = 1024,
        device: str = "cuda",
    ) -> None:
        BaseVisionRetriever.__init__(self, use_visual_embedding=True)

        from qwen_vl_utils import process_vision_info

        self.device = get_torch_device(device)
        self.processor = AutoProcessor.from_pretrained(
            pretrained_model_name_or_path,
            min_pixels=28 * 28,
            max_pixels=num_image_tokens * 28 * 28,
        )
        self.process_vision_info = process_vision_info
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            pretrained_model_name_or_path,
            attn_implementation=(
                "flash_attention_2" if is_flash_attn_2_available() else None
            ),
            torch_dtype=torch.bfloat16,
            device_map=str(self.device),
            low_cpu_mem_usage=True,
        ).eval()
        self.processor.tokenizer.padding_side = "left"
        self.model.padding_side = "left"
