"""Artifact namespace management and Run ID validation conforming to M1.7."""
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, Union

RUN_ID_REGEX = re.compile(r"^RUN-([A-Za-z0-9_-]+)-(\d{8}T\d{6}Z)-A(\d{2})$")


def format_canonical_run_id(
    experiment_id: str,
    timestamp_utc: datetime,
    attempt_num: int = 1,
) -> str:
    """Construct canonical Run ID: RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>."""
    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=timezone.utc)
    ts_str = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{experiment_id}-{ts_str}-A{int(attempt_num):02d}"


def parse_canonical_run_id(run_id: str) -> Dict[str, Any]:
    """Parse and validate canonical Run ID against M1.7 specification."""
    match = RUN_ID_REGEX.match(run_id)
    if not match:
        raise ValueError(
            f"Invalid canonical Run ID format: '{run_id}'. "
            f"Expected pattern: RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>"
        )

    return {
        "run_id": run_id,
        "experiment_id": match.group(1),
        "timestamp_utc": match.group(2),
        "attempt_num": int(match.group(3)),
    }


def create_run_namespace(
    base_dir: Union[str, Path],
    experiment_id: str,
    run_id: str,
) -> Path:
    """Create a create-once run directory under artifacts/<experiment_id>/<run_id>/.

    Raises:
        FileExistsError: If the target run directory already exists (enforcing create-once).
    """
    parse_canonical_run_id(run_id)  # Validate schema
    target_path = Path(base_dir) / "artifacts" / experiment_id / run_id

    if target_path.exists():
        raise FileExistsError(
            f"Run namespace already exists at '{target_path}'. "
            f"Overwriting run namespaces violates M1.7/M1.8 create-once invariant."
        )

    target_path.mkdir(parents=True, exist_ok=False)
    (target_path / "logs").mkdir(parents=True, exist_ok=True)
    (target_path / "outputs").mkdir(parents=True, exist_ok=True)

    return target_path
