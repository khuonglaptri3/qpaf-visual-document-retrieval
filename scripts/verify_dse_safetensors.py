from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable


CORE_FILES = (
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)
EXPECTED_KEYS = 730
EXPECTED_DTYPE = "torch.bfloat16"
TIED_KEY_GROUPS = (("model.embed_tokens.weight", "lm_head.weight"),)
CONVERSION_ROOT = "dse_safetensors"
WEIGHTS_FILE = "model.safetensors"
MANIFEST_FILE = "conversion_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def converted_snapshot_path(volume_root: Path, dse: dict[str, Any]) -> Path:
    return volume_root / CONVERSION_ROOT / dse["revision"]


def _tensor_bitwise_equal(left: Any, right: Any) -> bool:
    import torch

    if left.shape != right.shape or left.dtype != right.dtype:
        return False
    left_bytes = left.detach().cpu().contiguous().view(torch.uint8)
    right_bytes = right.detach().cpu().contiguous().view(torch.uint8)
    return bool(torch.equal(left_bytes, right_bytes))


def _state_comparison(
    original_state: dict[str, Any], converted_state: dict[str, Any]
) -> dict[str, Any]:
    original_keys = set(original_state)
    converted_keys = set(converted_state)
    missing_keys = sorted(original_keys - converted_keys)
    unexpected_keys = sorted(converted_keys - original_keys)
    mismatches: list[dict[str, Any]] = []
    matched = 0
    for key in sorted(original_keys & converted_keys):
        original_tensor = original_state[key]
        converted_tensor = converted_state[key]
        if (
            original_tensor.shape != converted_tensor.shape
            or original_tensor.dtype != converted_tensor.dtype
            or not _tensor_bitwise_equal(original_tensor, converted_tensor)
        ):
            if len(mismatches) < 20:
                mismatches.append(
                    {
                        "key": key,
                        "original_shape": list(original_tensor.shape),
                        "converted_shape": list(converted_tensor.shape),
                        "original_dtype": str(original_tensor.dtype),
                        "converted_dtype": str(converted_tensor.dtype),
                    }
                )
        else:
            matched += 1
    return {
        "original_keys": len(original_keys),
        "safetensors_keys": len(converted_keys),
        "exactly_matched_keys": matched,
        "missing_keys": missing_keys[:20],
        "unexpected_keys": unexpected_keys[:20],
        "mismatches": mismatches,
    }


def _tied_weights_equal(state: dict[str, Any]) -> bool:
    return all(
        all(key in state for key in group)
        and all(_tensor_bitwise_equal(state[group[0]], state[key]) for key in group[1:])
        for group in TIED_KEY_GROUPS
    )


def write_safetensors_preserving_keys(
    original_state: dict[str, Any], destination: Path
) -> None:
    from safetensors.torch import save_file

    # Safetensors cannot represent shared storage. Clone every value so tied
    # parameters remain present as separate, bitwise-identical checkpoint keys;
    # Transformers restores the runtime tie from config.json when loading.
    converted = {
        key: tensor.detach().cpu().contiguous().clone()
        for key, tensor in original_state.items()
    }
    save_file(converted, destination, metadata={"format": "pt"})


def load_verified_conversion_manifest(
    volume_root: Path, dse: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    snapshot_dir = converted_snapshot_path(volume_root, dse)
    manifest_path = snapshot_dir / MANIFEST_FILE
    if not manifest_path.is_file():
        raise RuntimeError("Verified pinned-original DSE safetensors conversion is unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    weights = manifest.get("weights", {})
    protocol = manifest.get("protocol", {})
    if not (
        manifest.get("status") == "PASS"
        and protocol.get("original_id") == dse["id"]
        and protocol.get("original_revision") == dse["revision"]
        and weights.get("original_keys") == EXPECTED_KEYS
        and weights.get("safetensors_keys") == EXPECTED_KEYS
        and weights.get("exactly_matched_keys") == EXPECTED_KEYS
        and weights.get("original_dtypes") == {EXPECTED_DTYPE: EXPECTED_KEYS}
        and weights.get("tied_weights_equal") is True
    ):
        raise RuntimeError("Pinned-original DSE safetensors conversion manifest failed validation")
    return snapshot_dir, manifest


def stage_verified_dse_snapshot(
    volume_root: Path, dse: dict[str, Any], runtime_root: Path
) -> tuple[Path, dict[str, Any]]:
    snapshot_dir, manifest = load_verified_conversion_manifest(volume_root, dse)
    destination = runtime_root / manifest["protocol_sha256"]
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*CORE_FILES, WEIGHTS_FILE):
        source = snapshot_dir / name
        if not source.is_file():
            raise RuntimeError(f"Verified DSE conversion is missing {name}")
        shutil.copy2(source, destination / name)
    expected_hash = manifest["weights"]["safetensors_sha256"]
    if _sha256(destination / WEIGHTS_FILE) != expected_hash:
        raise RuntimeError("Staged DSE safetensors hash mismatch")
    return destination, manifest


def convert_and_verify_dse_safetensors(
    environment: dict[str, Any],
    volume_root: Path,
    source_commit: str,
    image_definition_sha256: str,
    function_call_id: str,
    commit: Callable[[], None],
) -> dict[str, Any]:
    import torch
    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file

    started_at = time.perf_counter()
    cache_root = Path("/tmp/qpaf_dse_conversion")
    os.environ["HF_HOME"] = str(cache_root)
    os.environ["HF_HUB_CACHE"] = str(cache_root / "hub")
    dse = environment["models"]["dse"]
    protocol = {
        "original_id": dse["id"],
        "original_revision": dse["revision"],
        "conversion": "torch_load_bf16_clone_all_keys_safetensors_save_file",
        "comparison": "all_keys_shape_dtype_bitwise_equal",
        "expected_keys": EXPECTED_KEYS,
        "expected_dtype": EXPECTED_DTYPE,
        "tied_key_groups": TIED_KEY_GROUPS,
        "core_files": CORE_FILES,
    }
    protocol_sha256 = hashlib.sha256(
        json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    output_dir = converted_snapshot_path(volume_root, dse)
    local_output_dir = cache_root / "converted" / protocol_sha256
    local_output_dir.mkdir(parents=True, exist_ok=True)

    original_dir = Path(snapshot_download(repo_id=dse["id"], revision=dse["revision"]))
    original_weights = original_dir / "pytorch_model.bin"
    converted_weights = local_output_dir / WEIGHTS_FILE
    original_state = torch.load(
        original_weights,
        map_location="cpu",
        weights_only=True,
        mmap=True,
    )
    original_dtypes: dict[str, int] = {}
    for tensor in original_state.values():
        dtype = str(tensor.dtype)
        original_dtypes[dtype] = original_dtypes.get(dtype, 0) + 1
    original_tied_equal = _tied_weights_equal(original_state)
    write_safetensors_preserving_keys(original_state, converted_weights)
    converted_state = load_file(converted_weights, device="cpu")
    comparison = _state_comparison(original_state, converted_state)
    converted_tied_equal = _tied_weights_equal(converted_state)

    core_files = {}
    for name in CORE_FILES:
        shutil.copy2(original_dir / name, local_output_dir / name)
        original_hash = _sha256(original_dir / name)
        converted_hash = _sha256(local_output_dir / name)
        core_files[name] = {
            "original_sha256": original_hash,
            "converted_sha256": converted_hash,
            "equal": original_hash == converted_hash,
        }
    passed = (
        comparison["original_keys"] == EXPECTED_KEYS
        and comparison["safetensors_keys"] == EXPECTED_KEYS
        and comparison["exactly_matched_keys"] == EXPECTED_KEYS
        and not comparison["missing_keys"]
        and not comparison["unexpected_keys"]
        and not comparison["mismatches"]
        and original_dtypes == {EXPECTED_DTYPE: EXPECTED_KEYS}
        and original_tied_equal
        and converted_tied_equal
        and all(item["equal"] for item in core_files.values())
    )
    manifest = {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "source_commit": source_commit,
        "image_definition_sha256": image_definition_sha256,
        "function_call_id": function_call_id,
        "protocol_sha256": protocol_sha256,
        "protocol": protocol,
        "weights": {
            "original_sha256": _sha256(original_weights),
            "safetensors_sha256": _sha256(converted_weights),
            "original_dtypes": original_dtypes,
            "tied_weights_equal": original_tied_equal and converted_tied_equal,
            **comparison,
        },
        "core_files": core_files,
        "elapsed_seconds": time.perf_counter() - started_at,
    }
    local_manifest_path = local_output_dir / MANIFEST_FILE
    local_manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in (*CORE_FILES, WEIGHTS_FILE, MANIFEST_FILE):
        shutil.copy2(local_output_dir / name, output_dir / name)
    commit()
    if not passed:
        raise RuntimeError("Pinned-original DSE safetensors conversion failed verification")
    return {
        "status": "PASS",
        "manifest_path": str(output_dir / MANIFEST_FILE),
        "elapsed_seconds": manifest["elapsed_seconds"],
        "exactly_matched_keys": comparison["exactly_matched_keys"],
        "safetensors_sha256": manifest["weights"]["safetensors_sha256"],
        "tied_weights_equal": manifest["weights"]["tied_weights_equal"],
    }
