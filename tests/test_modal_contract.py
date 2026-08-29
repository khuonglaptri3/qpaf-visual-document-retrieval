from __future__ import annotations

import hashlib
from pathlib import Path

import modal_app
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_modal_image_uses_the_frozen_linux_lock() -> None:
    expected_lock_hash = hashlib.sha256((ROOT / "requirements-lock.txt").read_bytes()).hexdigest()
    assert modal_app.REQUESTED_GPU == "L4"
    assert modal_app.REQUIREMENTS_LOCK_SHA256 == expected_lock_hash
    assert modal_app.IMAGE_DEFINITION["requirements_lock_sha256"] == expected_lock_hash
    assert modal_app.IMAGE_DEFINITION["python"] == "3.11"


def test_modal_runtime_receives_the_lock_used_for_its_image() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    assert ".add_local_file(" in source
    assert 'remote_path="/root/requirements-lock.txt"' in source
    assert "copy=True" in source


def test_dataset_materializer_is_cpu_only_and_volume_backed() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def materialize_dataset", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    assert "gpu=" not in decorator
    assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
    assert "secrets=[hf_secret]" in decorator
    assert 'remote_path="/root/configs/datasets.yaml"' in source
    assert 'remote_path="/root/scripts/materialize_datasets.py"' in source
    assert modal_app.MATERIALIZE_TIMEOUT_SECONDS == 14_400
    assert modal_app.IMAGE_DEFINITION["datasets_config_sha256"] == hashlib.sha256(
        (ROOT / "configs" / "datasets.yaml").read_bytes()
    ).hexdigest()


def test_score_input_probe_is_read_only_cpu_and_volume_backed() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def probe_score_inputs", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    body = source.split("def probe_score_inputs", maxsplit=1)[1]
    assert "gpu=" not in decorator
    assert "secrets=" not in decorator
    assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
    assert "volume.commit()" in body
    assert 'remote_path="/root/scripts/probe_score_inputs.py"' in source
    assert 'remote_path="/root/configs/environment.yaml"' in source
    assert modal_app.IMAGE_DEFINITION["score_input_probe_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "probe_score_inputs.py").read_bytes()
    ).hexdigest()
    assert modal_app.IMAGE_DEFINITION["colqwen25_adapter_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "colqwen25_retriever.py").read_bytes()
    ).hexdigest()
    assert modal_app.IMAGE_DEFINITION["environment_config_sha256"] == hashlib.sha256(
        (ROOT / "configs" / "environment.yaml").read_bytes()
    ).hexdigest()


def test_vidoseek_expanded_coverage_audit_is_cpu_only_and_volume_backed() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def audit_vidoseek_expanded_coverage", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    body = source.split("def audit_vidoseek_expanded_coverage", maxsplit=1)[1].split(
        "@app.function", maxsplit=1
    )[0]
    assert "gpu=" not in decorator
    assert "secrets=" not in decorator
    assert "cpu=COVERAGE_AUDIT_CPU" in decorator
    assert "memory=COVERAGE_AUDIT_MEMORY_MB" in decorator
    assert "timeout=FUNCTION_TIMEOUT_SECONDS" in decorator
    assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
    assert "volume.commit()" in body
    assert modal_app.COVERAGE_AUDIT_CPU == 2.0
    assert modal_app.COVERAGE_AUDIT_MEMORY_MB == 4_096
    assert 'remote_path="/root/scripts/audit_vidoseek_coverage.py"' in source
    assert modal_app.IMAGE_DEFINITION["vidoseek_coverage_audit_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "audit_vidoseek_coverage.py").read_bytes()
    ).hexdigest()


def test_score_extraction_smoke_uses_reserved_gpu_without_qrels() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def score_extraction_smoke", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    body = source.split("def score_extraction_smoke", maxsplit=1)[1]
    assert "gpu=SCORE_EXTRACTION_GPU" in decorator
    assert "secrets=[hf_secret]" in decorator
    assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
    assert modal_app.SCORE_EXTRACTION_GPU == "A100-40GB"
    assert modal_app.SCORE_EXTRACTION_SMOKE_TIMEOUT_SECONDS == 3_600
    assert "qrels" not in body.lower()
    assert '"score_extraction_started": False' in body


def test_full_score_extractor_is_a100_resumable_and_bounded() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def extract_scores", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    body = source.split("def extract_scores", maxsplit=1)[1]
    assert "gpu=SCORE_EXTRACTION_GPU" in decorator
    assert "cpu=SCORE_EXTRACTION_CPU" in decorator
    assert "memory=SCORE_EXTRACTION_MEMORY_MB" in decorator
    assert "timeout=SCORE_EXTRACTION_TIMEOUT_SECONDS" in decorator
    assert modal_app.SCORE_EXTRACTION_TIMEOUT_SECONDS == 14_400
    assert modal_app.SCORE_EXTRACTION_CPU == 4.0
    assert modal_app.SCORE_EXTRACTION_MEMORY_MB == 32_768
    assert "commit=volume.commit" in body
    assert 'remote_path="/root/scripts/extract_vidore_baseline.py"' in source
    assert modal_app.IMAGE_DEFINITION["score_extractor_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "extract_vidore_baseline.py").read_bytes()
    ).hexdigest()
    assert modal_app.IMAGE_DEFINITION["bge_m3_adapter_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "bge_m3_dense_retriever.py").read_bytes()
    ).hexdigest()
    assert 'remote_path="/root/scripts/dse_qwen2_retriever.py"' in source
    assert modal_app.IMAGE_DEFINITION["dse_qwen2_adapter_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "dse_qwen2_retriever.py").read_bytes()
    ).hexdigest()
    assert 'remote_path="/root/scripts/verify_dse_safetensors.py"' in source


def test_vidoseek_calibration_and_full_extraction_use_approved_l4() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    modal_config = yaml.safe_load((ROOT / "configs" / "modal.yaml").read_text(encoding="utf-8"))
    calibration_decorator = source.split("def calibrate_vidoseek_scores", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    calibration_body = source.split("def calibrate_vidoseek_scores", maxsplit=1)[1].split(
        "@app.function", maxsplit=1
    )[0]
    full_decorator = source.split("def extract_vidoseek_scores", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    full_body = source.split("def extract_vidoseek_scores", maxsplit=1)[1]
    helper_body = source.split("def _run_vidoseek_extraction", maxsplit=1)[1].split(
        "@app.function", maxsplit=1
    )[0]

    assert modal_app.VIDOSEEK_CALIBRATION_GPU == "L4"
    assert modal_app.VIDOSEEK_SCORE_EXTRACTION_GPU == "L4"
    assert modal_app.VIDOSEEK_SCORE_EXTRACTION_TIMEOUT_SECONDS == 86_400
    assert modal_app.SCORE_EXTRACTION_GPU == "A100-40GB"
    assert modal_config["vidoseek_calibration_gpu"] == "L4"
    assert modal_config["vidoseek_score_extraction_gpu"] == "L4"
    assert modal_config["vidoseek_score_extraction_timeout_seconds"] == 86_400
    assert modal_config["score_extraction_gpu"] == "A100-40GB"
    assert "gpu=VIDOSEEK_CALIBRATION_GPU" in calibration_decorator
    assert "gpu=VIDOSEEK_SCORE_EXTRACTION_GPU" in full_decorator
    for decorator in [calibration_decorator, full_decorator]:
        assert "cpu=SCORE_EXTRACTION_CPU" in decorator
        assert "memory=SCORE_EXTRACTION_MEMORY_MB" in decorator
        assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
        assert "secrets=[hf_secret]" in decorator
    assert "timeout=SCORE_EXTRACTION_TIMEOUT_SECONDS" in calibration_decorator
    assert "timeout=VIDOSEEK_SCORE_EXTRACTION_TIMEOUT_SECONDS" in full_decorator
    assert "Calibration requires positive query_limit and page_limit" in calibration_body
    assert "calibration=True" in calibration_body
    assert "calibration=False" in full_body
    assert 'dataset_key="vidoseek"' in helper_body
    assert "vidoseek_adapter_sha256=VIDOSEEK_ADAPTER_SHA256" in helper_body
    assert modal_app.SYSTEM_PACKAGES == ("poppler-utils",)
    assert modal_app.IMAGE_DEFINITION["system_packages"] == ["poppler-utils"]
    assert modal_app.IMAGE_DEFINITION["vidoseek_adapter_sha256"] == hashlib.sha256(
        (ROOT / "scripts" / "vidoseek_dataset.py").read_bytes()
    ).hexdigest()
    assert 'remote_path="/root/scripts/vidoseek_dataset.py"' in source


def test_dse_safetensors_conversion_is_cpu_only_and_volume_backed() -> None:
    source = (ROOT / "modal_app.py").read_text(encoding="utf-8")
    decorator = source.split("def convert_and_verify_dse_safetensors", maxsplit=1)[0].rsplit(
        "@app.function", maxsplit=1
    )[1]
    assert "gpu=" not in decorator
    assert "cpu=SCORE_EXTRACTION_CPU" in decorator
    assert "memory=SCORE_EXTRACTION_MEMORY_MB" in decorator
    assert "volumes={str(VOLUME_MOUNT): volume}" in decorator
