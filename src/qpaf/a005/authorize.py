"""Light-mode authorization writer for A005 Stages 2-4 (course project; no amendment per decision).

Writes the keys each stage's `check_authorization` reads: status, source pins, cache pins and,
for Stage 4, the run identity and the Stage 3 record pin. Create-once; never overwrites.
"""
from datetime import datetime, timezone
from pathlib import Path

from qpaf.m43.freeze import sha, write_json

from . import stage2, stage3, stage4


def write_authorization(root, cache, stage, approval_text, *, granularity=None, seed=None):
    root, cache = Path(root), Path(cache)
    if not isinstance(approval_text, str) or not approval_text.strip():
        raise ValueError('approval_text must be non-empty')
    if stage == 2:
        path, sources = root/stage2.AUTHORIZATION, stage2.SOURCES
    elif stage == 3:
        path, sources = root/stage3.AUTHORIZATION, stage3.SOURCES
    elif stage == 4:
        if granularity not in stage4.GRANULARITIES or seed not in stage4.SEEDS:
            raise ValueError('Stage 4 needs granularity in query|page and a frozen seed')
        path, sources = stage4.run_dir(root, granularity, seed)/'authorization.json', stage4.SOURCES
    else:
        raise ValueError(f'unknown stage: {stage}')
    if path.exists():
        raise ValueError(f'authorization already exists: {path.relative_to(root).as_posix()}')
    record = {'schema_version': 1, 'amendment': 'QPAF-M1.5-A005', 'stage': stage, 'status': 'APPROVED',
              'owner': 'Tấn Phát', 'approval_text': approval_text, 'mode': 'course_project_light',
              'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'source_files_sha256': {relative: sha(root/relative) for relative in sources},
              'cache_sha256': {name: sha(cache/name) for name in stage2.CACHE_FILES}}
    if stage == 4:
        record.update(granularity=granularity, seed=seed, stage3_sha256=sha(root/stage4.STAGE3))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, record)
    return path
