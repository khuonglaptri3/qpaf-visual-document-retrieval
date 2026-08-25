from __future__ import annotations

import hashlib
import importlib.metadata
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
MATERIALIZE_FUNCTION_NAME = "materialize-dataset"
REQUESTED_GPU = "L4"
MINIMUM_GPU_MEMORY_GB = 23.5
VOLUME_NAME = "qpaf-artifacts"
VOLUME_MOUNT = Path("/vol")
HF_SECRET_NAME = "huggingface-secret"
FUNCTION_TIMEOUT_SECONDS = 600
MATERIALIZE_TIMEOUT_SECONDS = 14_400
PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_LOCK_PATH = PROJECT_ROOT / "requirements-lock.txt"
DATASETS_CONFIG_PATH = PROJECT_ROOT / "configs" / "datasets.yaml"
MATERIALIZER_PATH = PROJECT_ROOT / "scripts" / "materialize_datasets.py"
REQUIREMENTS_LOCK_SHA256 = hashlib.sha256(REQUIREMENTS_LOCK_PATH.read_bytes()).hexdigest()
DATASETS_CONFIG_SHA256 = hashlib.sha256(DATASETS_CONFIG_PATH.read_bytes()).hexdigest()
MATERIALIZER_SHA256 = hashlib.sha256(MATERIALIZER_PATH.read_bytes()).hexdigest()


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
    "requirements_lock": REQUIREMENTS_LOCK_PATH.name,
    "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
    "datasets_config_sha256": DATASETS_CONFIG_SHA256,
    "materializer_sha256": MATERIALIZER_SHA256,
}
IMAGE_DEFINITION_SHA256 = hashlib.sha256(
    json.dumps(IMAGE_DEFINITION, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

image = modal.Image.debian_slim(python_version=IMAGE_DEFINITION["python"]).pip_install_from_requirements(
    str(REQUIREMENTS_LOCK_PATH),
    extra_options="--require-hashes",
).add_local_file(
    str(REQUIREMENTS_LOCK_PATH),
    remote_path="/root/requirements-lock.txt",
    copy=True,
).add_local_file(
    str(DATASETS_CONFIG_PATH),
    remote_path="/root/configs/datasets.yaml",
    copy=True,
).add_local_file(
    str(MATERIALIZER_PATH),
    remote_path="/root/scripts/materialize_datasets.py",
    copy=True,
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
        "requirements_lock_sha256": REQUIREMENTS_LOCK_SHA256,
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
        "packages": {
            name: importlib.metadata.version(name)
            for name in [
                "colpali-engine",
                "datasets",
                "torch",
                "torchvision",
                "transformers",
                "vidore-benchmark",
            ]
        },
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


@app.function(
    name=MATERIALIZE_FUNCTION_NAME,
    image=image,
    timeout=MATERIALIZE_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def materialize_dataset(dataset_key: str = "vidoseek") -> str:
    """Materialize one pinned dataset into the Modal Volume without requesting a GPU."""
    import yaml

    from scripts.materialize_datasets import materialize_dataset as materialize

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is unavailable in the Modal Secret")

    config = yaml.safe_load(DATASETS_CONFIG_PATH.read_text(encoding="utf-8"))
    result = materialize(
        config,
        dataset_key,
        token=token,
        function_call_id=function_call_id,
        source_commit=SOURCE_COMMIT,
        image_definition_sha256=IMAGE_DEFINITION_SHA256,
    )
    volume.commit()
    return json.dumps(result, indent=2, sort_keys=True) + "\n"
