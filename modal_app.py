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
SCORE_INPUT_PROBE_FUNCTION_NAME = "score-input-probe"
SCORE_EXTRACTION_SMOKE_FUNCTION_NAME = "score-extraction-smoke"
SCORE_EXTRACTION_FUNCTION_NAME = "extract-scores"
VERIFY_DSE_FUNCTION_NAME = "verify-dse-safetensors"
REQUESTED_GPU = "L4"
SCORE_EXTRACTION_GPU = "A100-40GB"
SCORE_EXTRACTION_CPU = 4.0
SCORE_EXTRACTION_MEMORY_MB = 32_768
MINIMUM_GPU_MEMORY_GB = 23.5
VOLUME_NAME = "qpaf-artifacts"
VOLUME_MOUNT = Path("/vol")
HF_SECRET_NAME = "huggingface-secret"
FUNCTION_TIMEOUT_SECONDS = 600
MATERIALIZE_TIMEOUT_SECONDS = 14_400
SCORE_EXTRACTION_SMOKE_TIMEOUT_SECONDS = 3_600
SCORE_EXTRACTION_TIMEOUT_SECONDS = 14_400
PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_LOCK_PATH = PROJECT_ROOT / "requirements-lock.txt"
DATASETS_CONFIG_PATH = PROJECT_ROOT / "configs" / "datasets.yaml"
ENVIRONMENT_CONFIG_PATH = PROJECT_ROOT / "configs" / "environment.yaml"
MATERIALIZER_PATH = PROJECT_ROOT / "scripts" / "materialize_datasets.py"
SCORE_INPUT_PROBE_PATH = PROJECT_ROOT / "scripts" / "probe_score_inputs.py"
COLQWEN25_ADAPTER_PATH = PROJECT_ROOT / "scripts" / "colqwen25_retriever.py"
SCORE_EXTRACTOR_PATH = PROJECT_ROOT / "scripts" / "extract_vidore_baseline.py"
BGE_M3_ADAPTER_PATH = PROJECT_ROOT / "scripts" / "bge_m3_dense_retriever.py"
DSE_QWEN2_ADAPTER_PATH = PROJECT_ROOT / "scripts" / "dse_qwen2_retriever.py"
VERIFY_DSE_PATH = PROJECT_ROOT / "scripts" / "verify_dse_safetensors.py"
REQUIREMENTS_LOCK_SHA256 = hashlib.sha256(REQUIREMENTS_LOCK_PATH.read_bytes()).hexdigest()
DATASETS_CONFIG_SHA256 = hashlib.sha256(DATASETS_CONFIG_PATH.read_bytes()).hexdigest()
ENVIRONMENT_CONFIG_SHA256 = hashlib.sha256(ENVIRONMENT_CONFIG_PATH.read_bytes()).hexdigest()
MATERIALIZER_SHA256 = hashlib.sha256(MATERIALIZER_PATH.read_bytes()).hexdigest()
SCORE_INPUT_PROBE_SHA256 = hashlib.sha256(SCORE_INPUT_PROBE_PATH.read_bytes()).hexdigest()
COLQWEN25_ADAPTER_SHA256 = hashlib.sha256(COLQWEN25_ADAPTER_PATH.read_bytes()).hexdigest()
SCORE_EXTRACTOR_SHA256 = hashlib.sha256(SCORE_EXTRACTOR_PATH.read_bytes()).hexdigest()
BGE_M3_ADAPTER_SHA256 = hashlib.sha256(BGE_M3_ADAPTER_PATH.read_bytes()).hexdigest()
DSE_QWEN2_ADAPTER_SHA256 = hashlib.sha256(DSE_QWEN2_ADAPTER_PATH.read_bytes()).hexdigest()
VERIFY_DSE_SHA256 = hashlib.sha256(VERIFY_DSE_PATH.read_bytes()).hexdigest()


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
    "environment_config_sha256": ENVIRONMENT_CONFIG_SHA256,
    "materializer_sha256": MATERIALIZER_SHA256,
    "score_input_probe_sha256": SCORE_INPUT_PROBE_SHA256,
    "colqwen25_adapter_sha256": COLQWEN25_ADAPTER_SHA256,
    "score_extractor_sha256": SCORE_EXTRACTOR_SHA256,
    "bge_m3_adapter_sha256": BGE_M3_ADAPTER_SHA256,
    "dse_qwen2_adapter_sha256": DSE_QWEN2_ADAPTER_SHA256,
    "verify_dse_sha256": VERIFY_DSE_SHA256,
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
    str(ENVIRONMENT_CONFIG_PATH),
    remote_path="/root/configs/environment.yaml",
    copy=True,
).add_local_file(
    str(MATERIALIZER_PATH),
    remote_path="/root/scripts/materialize_datasets.py",
    copy=True,
).add_local_file(
    str(SCORE_INPUT_PROBE_PATH),
    remote_path="/root/scripts/probe_score_inputs.py",
    copy=True,
).add_local_file(
    str(COLQWEN25_ADAPTER_PATH),
    remote_path="/root/scripts/colqwen25_retriever.py",
    copy=True,
).add_local_file(
    str(SCORE_EXTRACTOR_PATH),
    remote_path="/root/scripts/extract_vidore_baseline.py",
    copy=True,
).add_local_file(
    str(BGE_M3_ADAPTER_PATH),
    remote_path="/root/scripts/bge_m3_dense_retriever.py",
    copy=True,
).add_local_file(
    str(DSE_QWEN2_ADAPTER_PATH),
    remote_path="/root/scripts/dse_qwen2_retriever.py",
    copy=True,
).add_local_file(
    str(VERIFY_DSE_PATH),
    remote_path="/root/scripts/verify_dse_safetensors.py",
    copy=True,
)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
hf_secret = modal.Secret.from_name(
    HF_SECRET_NAME,
    required_keys=["HF_TOKEN"],
)
app = modal.App(APP_NAME)


@app.function(
    name=VERIFY_DSE_FUNCTION_NAME,
    image=image,
    cpu=SCORE_EXTRACTION_CPU,
    memory=SCORE_EXTRACTION_MEMORY_MB,
    timeout=3_600,
    secrets=[hf_secret],
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def verify_dse_safetensors() -> str:
    """Verify a safetensors conversion against every pinned original DSE tensor."""
    import yaml

    from scripts.verify_dse_safetensors import verify_dse_safetensors as verify

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")
    result = verify(
        environment=yaml.safe_load(ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8")),
        volume_root=VOLUME_MOUNT,
        source_commit=SOURCE_COMMIT,
        image_definition_sha256=IMAGE_DEFINITION_SHA256,
        function_call_id=function_call_id,
        commit=volume.commit,
    )
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


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


@app.function(
    name=SCORE_INPUT_PROBE_FUNCTION_NAME,
    image=image,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def probe_score_inputs(dataset_key: str = "vidore_v3_finance_en") -> str:
    """Inspect frozen score inputs without a GPU, model loading, or extraction."""
    import yaml

    from scripts.probe_score_inputs import probe_score_inputs as probe

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")
    config = yaml.safe_load(DATASETS_CONFIG_PATH.read_text(encoding="utf-8"))
    environment = yaml.safe_load(ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    result = {
        **probe(config, dataset_key, environment),
        "app_name": APP_NAME,
        "function_name": SCORE_INPUT_PROBE_FUNCTION_NAME,
        "function_call_id": function_call_id,
        "image_definition_sha256": IMAGE_DEFINITION_SHA256,
        "source_commit": SOURCE_COMMIT,
    }
    probe_dir = VOLUME_MOUNT / "score_extraction" / "preflight"
    probe_dir.mkdir(parents=True, exist_ok=True)
    destination = probe_dir / f"{dataset_key}.json"
    temporary = destination.with_suffix(".json.tmp")
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(destination)
    volume.commit()
    return serialized


@app.function(
    name=SCORE_EXTRACTION_SMOKE_FUNCTION_NAME,
    image=image,
    gpu=SCORE_EXTRACTION_GPU,
    timeout=SCORE_EXTRACTION_SMOKE_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def score_extraction_smoke(dataset_key: str = "vidore_v3_finance_en") -> str:
    """Score one label-free query/page pair with the pinned ColQwen2.5 adapter."""
    import io
    import math

    import pyarrow.parquet as pq
    import torch
    import yaml
    from PIL import Image

    from scripts.colqwen25_retriever import ColQwen25Retriever

    if dataset_key != "vidore_v3_finance_en":
        raise ValueError("Only the preflight-approved ViDoRe V3 adapter may run this smoke")
    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")

    dataset_config = yaml.safe_load(DATASETS_CONFIG_PATH.read_text(encoding="utf-8"))
    environment = yaml.safe_load(ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    dataset = next(item for item in dataset_config["datasets"] if item["key"] == dataset_key)
    root = Path(dataset["local_dir"])
    model = environment["models"]["colqwen25"]

    os.environ["HF_HOME"] = str(VOLUME_MOUNT / "hf_cache")
    os.environ["HF_HUB_CACHE"] = str(VOLUME_MOUNT / "hf_cache" / "hub")
    query_table = pq.read_table(
        root / "queries" / "test-00000-of-00001.parquet",
        columns=["query_id", "query", "language"],
    ).to_pandas()
    query_row = query_table.loc[query_table["language"].eq("english")].sort_values(
        "query_id", kind="stable"
    ).iloc[0]
    corpus_file = root / "corpus" / "test-00000-of-00003.parquet"
    corpus_row = pq.ParquetFile(corpus_file).read_row_group(
        0, columns=["corpus_id", "image"]
    ).slice(0, 1).to_pylist()[0]
    image = Image.open(io.BytesIO(corpus_row["image"]["bytes"])).convert("RGB")

    gpu = _gpu_metadata(torch)
    torch.cuda.reset_peak_memory_stats()
    retriever = ColQwen25Retriever(
        base_model_id=model["base_id"],
        base_revision=model["base_revision"],
        adapter_model_id=model["id"],
        adapter_revision=model["revision"],
        device="cuda",
        num_workers=0,
    )
    query_embeddings = retriever.forward_queries([str(query_row["query"])], batch_size=1)
    passage_embeddings = retriever.forward_passages([image], batch_size=1)
    score = float(retriever.get_scores(query_embeddings, passage_embeddings, batch_size=1)[0, 0])
    if not math.isfinite(score):
        raise RuntimeError("ColQwen2.5 smoke produced a non-finite score")

    result = {
        "schema_version": 1,
        "status": "PASS",
        "app_name": APP_NAME,
        "function_name": SCORE_EXTRACTION_SMOKE_FUNCTION_NAME,
        "function_call_id": function_call_id,
        "source_commit": SOURCE_COMMIT,
        "image_definition_sha256": IMAGE_DEFINITION_SHA256,
        "dataset_key": dataset_key,
        "dataset_revision": dataset["revision"],
        "model_id": model["id"],
        "model_revision": model["revision"],
        "base_model_id": model["base_id"],
        "base_model_revision": model["base_revision"],
        "query_id": str(query_row["query_id"]),
        "page_id": str(corpus_row["corpus_id"]),
        "query_embedding_shape": list(query_embeddings[0].shape),
        "passage_embedding_shape": list(passage_embeddings[0].shape),
        "score_finite": True,
        "max_memory_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "score_extraction_started": False,
        **gpu,
    }
    destination = VOLUME_MOUNT / "score_extraction" / "smoke" / f"{function_call_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(destination)
    volume.commit()
    return serialized


@app.function(
    name=SCORE_EXTRACTION_FUNCTION_NAME,
    image=image,
    gpu=SCORE_EXTRACTION_GPU,
    cpu=SCORE_EXTRACTION_CPU,
    memory=SCORE_EXTRACTION_MEMORY_MB,
    timeout=SCORE_EXTRACTION_TIMEOUT_SECONDS,
    secrets=[hf_secret],
    volumes={str(VOLUME_MOUNT): volume},
    env={"QPAF_SOURCE_COMMIT": SOURCE_COMMIT},
)
def extract_scores(
    query_limit: int = 0,
    page_limit: int = 0,
    calibration: bool = False,
) -> str:
    """Extract the approved frozen ViDoRe baseline scores with resumable stage caches."""
    import torch
    import yaml

    from scripts.extract_vidore_baseline import run_extraction

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")
    if calibration and (query_limit <= 0 or page_limit <= 0):
        raise ValueError("Calibration requires positive query_limit and page_limit")
    if not calibration and (query_limit != 0 or page_limit != 0):
        raise ValueError("Full extraction does not accept query/page limits")
    result = run_extraction(
        dataset_config=yaml.safe_load(DATASETS_CONFIG_PATH.read_text(encoding="utf-8")),
        environment=yaml.safe_load(ENVIRONMENT_CONFIG_PATH.read_text(encoding="utf-8")),
        volume_root=VOLUME_MOUNT,
        source_commit=SOURCE_COMMIT,
        image_definition_sha256=IMAGE_DEFINITION_SHA256,
        extractor_sha256=SCORE_EXTRACTOR_SHA256,
        dse_adapter_sha256=DSE_QWEN2_ADAPTER_SHA256,
        function_call_id=function_call_id,
        gpu_metadata=_gpu_metadata(torch),
        commit=volume.commit,
        query_limit=query_limit,
        page_limit=page_limit,
        calibration=calibration,
    )
    return json.dumps(result, indent=2, sort_keys=True) + "\n"
