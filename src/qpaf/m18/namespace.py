"""Artifact namespace management and Run ID validation conforming to M1.7."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Union

RUN_ID_REGEX = re.compile(r"^RUN-([A-Za-z0-9_-]+)-(\d{8}T\d{6}Z)-A(\d{2})$")


def validate_experiment_id(experiment_id: str) -> None:
    if not isinstance(experiment_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', experiment_id):
        raise ValueError('Experiment ID must be 1-64 ASCII letters/digits/underscore/hyphen')


def format_canonical_run_id(
    experiment_id: str,
    timestamp_utc: datetime,
    attempt_num: int = 1,
) -> str:
    """Construct canonical Run ID: RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>."""
    validate_experiment_id(experiment_id)
    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError('Run timestamp must be timezone-aware')
    if type(attempt_num) is not int or not 1 <= attempt_num <= 99:
        raise ValueError('Run attempt must be an integer between 1 and 99')
    ts_str = timestamp_utc.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{experiment_id}-{ts_str}-A{int(attempt_num):02d}"


def parse_canonical_run_id(run_id: str) -> Dict[str, Any]:
    """Parse and validate canonical Run ID against M1.7 specification."""
    match = RUN_ID_REGEX.fullmatch(run_id) if isinstance(run_id, str) else None
    if not match:
        raise ValueError(
            f"Invalid canonical Run ID format: '{run_id}'. "
            f"Expected pattern: RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>"
        )
    validate_experiment_id(match.group(1))
    datetime.strptime(match.group(2), '%Y%m%dT%H%M%SZ')
    if int(match.group(3)) < 1:
        raise ValueError('Run attempt must be between 1 and 99')
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
    validate_experiment_id(experiment_id)
    if parse_canonical_run_id(run_id)['experiment_id'] != experiment_id:
        raise ValueError('Run ID does not match experiment ID')
    target_path = Path(base_dir) / "artifacts" / experiment_id / run_id
    if not target_path.resolve().is_relative_to(Path(base_dir).resolve()):
        raise ValueError('Run namespace escapes base directory')

    if target_path.exists():
        raise FileExistsError(
            f"Run namespace already exists at '{target_path}'. "
            f"Overwriting run namespaces violates M1.7/M1.8 create-once invariant."
        )

    target_path.mkdir(parents=True, exist_ok=False)
    (target_path / "logs").mkdir(parents=True, exist_ok=True)
    (target_path / "outputs").mkdir(parents=True, exist_ok=True)

    return target_path


def validate_run_contract(run_id, config):
    parsed = parse_canonical_run_id(run_id)
    if parsed['experiment_id'] != config['execution']['experiment_id']:
        raise ValueError('Run ID does not match configured experiment ID')
    retry_of = config['execution'].get('retry_of', '')
    if parsed['attempt_num'] == 1:
        if retry_of:
            raise ValueError('First run attempt cannot have retry_of')
    else:
        prior = parse_canonical_run_id(retry_of)
        if (prior['experiment_id'] != parsed['experiment_id'] or
                prior['attempt_num'] != parsed['attempt_num'] - 1 or
                prior['timestamp_utc'] > parsed['timestamp_utc']):
            raise ValueError('retry_of must identify the previous experiment attempt at an earlier UTC timestamp')
    return parsed


def ensure_run_metadata(root, run_id, config, source):
    """Create immutable run identity once; matching stage retries may reuse it.

    StageRun remains responsible for distinct failed/completed stage attempts and
    their logs, config, environment and hashes. A new run must never adopt old stages.
    """
    from qpaf.m11.artifacts import cache_config_hash, environment, object_hash
    parsed = validate_run_contract(run_id, config)
    root = Path(root)
    if root.name != run_id or root.is_symlink():
        raise ValueError('Run metadata path must match Run ID and cannot be a symlink')
    identity = {'run_id': run_id, 'experiment_id': parsed['experiment_id'],
                'timestamp_utc': parsed['timestamp_utc'], 'attempt_num': parsed['attempt_num'],
                'retry_of': config['execution'].get('retry_of', ''),
                'cache_config_sha256': cache_config_hash(config), 'source_digest': source.get('digest')}
    path = root/'run_metadata.json'
    if path.exists():
        recorded = json.loads(path.read_text(encoding='utf-8'))
        if recorded.get('identity') != identity or recorded.get('metadata_sha256') != object_hash(recorded.get('metadata')):
            raise ValueError('Existing run metadata has different config/source/identity or corrupt metadata')
        if recorded['metadata'].get('identity') != identity:
            raise ValueError('Run metadata identity mismatch')
        return root
    if root.exists() and any(p.name not in ('logs', 'outputs') or not p.is_dir() or any(p.iterdir()) for p in root.iterdir()):
        raise FileExistsError('Existing run without metadata cannot be adopted; use a new Run ID')
    metadata = {'identity': identity, 'config': config, 'source': source,
                'command': source.get('command', []), 'environment': environment()}
    root.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'identity': identity, 'metadata': metadata, 'metadata_sha256': object_hash(metadata)},
                  stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return root
