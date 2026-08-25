from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import modal


APP_NAME = "qpaf-research"
FUNCTION_NAME = "environment-probe"
REQUESTED_GPU = "L4"
MINIMUM_GPU_MEMORY_GB = 23.5
VOLUME_NAME = "qpaf-artifacts"
VOLUME_MOUNT = Path("/vol")
HF_SECRET_NAME = "huggingface-secret"
FUNCTION_TIMEOUT_SECONDS = 600


def _resolve_source_commit() -> str:
    configured = os.environ.get("QPAF_SOURCE_COMMIT")
    if configured:
        return configured
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()


SOURCE_COMMIT = _resolve_source_commit()
IMAGE_DEFINITION: dict[str, Any] = {
    "base": "modal.Image.debian_slim",
    "python": "3.11",
    "pip": ["torch==2.11.0"],
}
IMAGE_DEFINITION_SHA256 = hashlib.sha256(
    json.dumps(IMAGE_DEFINITION, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

image = modal.Image.debian_slim(python_version=IMAGE_DEFINITION["python"]).pip_install(
    *IMAGE_DEFINITION["pip"]
)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
hf_secret = modal.Secret.from_name(
    HF_SECRET_NAME,
    required_keys=["HF_TOKEN"],
)
app = modal.App(APP_NAME)


def _gpu_metadata(torch_module: Any) -> dict[str, Any]:
    if not torch_module.cuda.is_available():
        raise RuntimeError("Modal environment probe requires CUDA")

    device_index = torch_module.cuda.current_device()
    properties = torch_module.cuda.get_device_properties(device_index)
    total_bytes = int(properties.total_memory)
    total_gb = total_bytes / 1_000_000_000
    total_gib = total_bytes / (1024**3)
    if total_gb < MINIMUM_GPU_MEMORY_GB:
        raise RuntimeError(
            f"Allocated GPU has only {total_gb:.2f} GB; "
            f"{MINIMUM_GPU_MEMORY_GB:.1f} GB required"
        )

    driver_version = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=driver_version",
            "--format=csv,noheader",
            f"--id={device_index}",
        ],
        text=True,
    ).strip()
    return {
        "actual_gpu": properties.name,
        "actual_gpu_vram_bytes": total_bytes,
        "actual_gpu_vram_gb": round(total_gb, 3),
        "actual_gpu_vram_gib": round(total_gib, 3),
        "cuda_available": True,
        "cuda_runtime": torch_module.version.cuda,
        "cudnn": torch_module.backends.cudnn.version(),
        "driver": driver_version,
    }


@app.function(
    name=FUNCTION_NAME,
    image=image,
    gpu=REQUESTED_GPU,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def environment_probe() -> str:
    """Capture Modal runtime metadata without loading models or training."""
    import torch

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")

    result: dict[str, Any] = {
        "app_name": APP_NAME,
        "function_name": FUNCTION_NAME,
        "function_call_id": function_call_id,
        "modal_task_id": os.environ.get("MODAL_TASK_ID"),
        "image_definition": IMAGE_DEFINITION,
        "image_definition_sha256": IMAGE_DEFINITION_SHA256,
        "requested_gpu": REQUESTED_GPU,
        "function_timeout_seconds": FUNCTION_TIMEOUT_SECONDS,
        "volume_name": VOLUME_NAME,
        "volume_mount": str(VOLUME_MOUNT),
        "hf_secret_name": HF_SECRET_NAME,
        "hf_token_available": bool(os.environ.get("HF_TOKEN")),
        "source_commit": SOURCE_COMMIT,
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "modal": modal.__version__,
        **_gpu_metadata(torch),
    }

    probe_dir = VOLUME_MOUNT / "environment" / "probes"
    probe_dir.mkdir(parents=True, exist_ok=True)
    destination = probe_dir / f"{function_call_id}.json"
    temporary = destination.with_suffix(".json.tmp")
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(destination)
    volume.commit()
    return serialized
