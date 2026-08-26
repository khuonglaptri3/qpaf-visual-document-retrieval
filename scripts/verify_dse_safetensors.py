from __future__ import annotations

import hashlib
import json
import os
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_dse_safetensors(
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
    cache_root = Path("/tmp/qpaf_dse_verification")
    os.environ["HF_HOME"] = str(cache_root)
    os.environ["HF_HUB_CACHE"] = str(cache_root / "hub")
    dse = environment["models"]["dse"]
    protocol = {
        "original_id": dse["id"],
        "original_revision": dse["revision"],
        "safetensors_id": dse["safetensors_id"],
        "safetensors_revision": dse["safetensors_revision"],
        "comparison": "all_keys_shape_dtype_torch_equal",
        "core_files": CORE_FILES,
    }
    protocol_sha256 = hashlib.sha256(
        json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    output_dir = volume_root / "dse_safetensors_verification" / protocol_sha256
    output_dir.mkdir(parents=True, exist_ok=True)

    original_dir = Path(snapshot_download(repo_id=dse["id"], revision=dse["revision"]))
    mirror_dir = Path(
        snapshot_download(
            repo_id=dse["safetensors_id"], revision=dse["safetensors_revision"]
        )
    )
    original_weights = original_dir / "pytorch_model.bin"
    mirror_weights = mirror_dir / "model.safetensors"
    original_state = torch.load(
        original_weights,
        map_location="cpu",
        weights_only=True,
        mmap=True,
    )
    mirror_state = load_file(mirror_weights, device="cpu")

    original_keys = set(original_state)
    mirror_keys = set(mirror_state)
    missing_keys = sorted(original_keys - mirror_keys)
    unexpected_keys = sorted(mirror_keys - original_keys)
    mismatches: list[dict[str, Any]] = []
    matched = 0
    for key in sorted(original_keys & mirror_keys):
        original_tensor = original_state[key]
        mirror_tensor = mirror_state[key]
        if (
            original_tensor.shape != mirror_tensor.shape
            or original_tensor.dtype != mirror_tensor.dtype
            or not torch.equal(original_tensor, mirror_tensor)
        ):
            if len(mismatches) < 20:
                mismatches.append(
                    {
                        "key": key,
                        "original_shape": list(original_tensor.shape),
                        "mirror_shape": list(mirror_tensor.shape),
                        "original_dtype": str(original_tensor.dtype),
                        "mirror_dtype": str(mirror_tensor.dtype),
                    }
                )
        else:
            matched += 1

    core_files = {}
    for name in CORE_FILES:
        original_hash = _sha256(original_dir / name)
        mirror_hash = _sha256(mirror_dir / name)
        core_files[name] = {
            "original_sha256": original_hash,
            "mirror_sha256": mirror_hash,
            "equal": original_hash == mirror_hash,
        }
    passed = (
        not missing_keys
        and not unexpected_keys
        and not mismatches
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
            "safetensors_sha256": _sha256(mirror_weights),
            "original_keys": len(original_keys),
            "safetensors_keys": len(mirror_keys),
            "exactly_matched_keys": matched,
            "missing_keys": missing_keys[:20],
            "unexpected_keys": unexpected_keys[:20],
            "mismatches": mismatches,
        },
        "core_files": core_files,
        "elapsed_seconds": time.perf_counter() - started_at,
    }
    manifest_path = output_dir / "dse_safetensors_verification.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    commit()
    if not passed:
        raise RuntimeError("DSE safetensors mirror is not bitwise equivalent")
    return {
        "status": "PASS",
        "manifest_path": str(manifest_path),
        "elapsed_seconds": manifest["elapsed_seconds"],
        "exactly_matched_keys": matched,
    }
