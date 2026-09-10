"""Separate CPU-only Modal app for a future approved ViMDoc content audit."""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME = "qpaf-vimdoc-archive-audit-v1"
PROJECT_ROOT = Path(__file__).resolve().parent
REMOTE_ROOT = Path("/root")
VOLUME_ROOT = Path("/vol")
CONFIG_PATH = PROJECT_ROOT / "configs/vimdoc_archive_content_audit_v1.json"
IDENTITY_SPEC_PATH = PROJECT_ROOT / "configs/vimdoc_ocr_page_identity_v1.json"
RUNNER_PATH = PROJECT_ROOT / "scripts/run_vimdoc_archive_content_audit.py"
VALIDATOR_PATH = PROJECT_ROOT / "scripts/validate_vimdoc_ocr_page_identity.py"

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
resources = config["resources"]
app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .add_local_file(str(CONFIG_PATH), remote_path=f"{REMOTE_ROOT}/configs/{CONFIG_PATH.name}", copy=True)
    .add_local_file(str(IDENTITY_SPEC_PATH), remote_path=f"{REMOTE_ROOT}/configs/{IDENTITY_SPEC_PATH.name}", copy=True)
    .add_local_file(str(RUNNER_PATH), remote_path=f"{REMOTE_ROOT}/scripts/{RUNNER_PATH.name}", copy=True)
    .add_local_file(str(VALIDATOR_PATH), remote_path=f"{REMOTE_ROOT}/scripts/{VALIDATOR_PATH.name}", copy=True)
)
volume = modal.Volume.from_name(config["modal"]["volume_name"], create_if_missing=False)


@app.function(
    image=image,
    cpu=resources["cpu_physical_cores"],
    memory=resources["memory_mb"],
    timeout=resources["timeout_seconds"],
    retries=resources["retries"],
    volumes={str(VOLUME_ROOT): volume},
)
def audit_vimdoc_archive(config_sha256: str, actor: str, source_commit: str) -> str:
    from scripts.run_vimdoc_archive_content_audit import run_audit

    function_call_id = modal.current_function_call_id()
    if not function_call_id:
        raise RuntimeError("Modal did not expose a Function call ID")
    result = run_audit(
        REMOTE_ROOT,
        VOLUME_ROOT,
        REMOTE_ROOT / "configs/vimdoc_archive_content_audit_v1.json",
        config_sha256,
        actor,
        source_commit,
        function_call_id,
        volume.commit,
    )
    return json.dumps(result, sort_keys=True)
