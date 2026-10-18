"""Atomic checkpoints bound to config hash, method and feature schema."""
import os
from pathlib import Path
import uuid

from qpaf.m11.artifacts import digest, object_hash
from qpaf.m12.features import FEATURE_NAMES

FORMAT = 'qpaf-m24-checkpoint-v1'


class CheckpointError(ValueError):
    """Checkpoint is missing, corrupt or belongs to a different run contract."""


def save_checkpoint(path, *, config, method, epoch, model, optimizer, generator, history, best):
    import torch
    path = Path(path)
    payload = {'format': FORMAT, 'config_sha256': object_hash(config), 'method': method,
               'feature_names': list(FEATURE_NAMES), 'epoch': epoch,
               'model_state': model.state_dict(), 'optimizer_state': optimizer.state_dict(),
               'generator_state': generator.get_state(), 'history': history, 'best': best}
    temp = path.with_name(f'{path.name}.{uuid.uuid4().hex}.tmp')
    torch.save(payload, temp)
    os.replace(temp, path)
    return digest(path)


def load_checkpoint(path, *, config, method, expected_sha256=None):
    import torch
    path = Path(path)
    if not path.is_file():
        raise CheckpointError(f'Checkpoint not found: {path}')
    if expected_sha256 is not None and digest(path) != expected_sha256:
        raise CheckpointError('Checkpoint checksum mismatch')
    try:
        payload = torch.load(path, map_location='cpu', weights_only=True)
    except Exception as exc:  # torch raises several unpickling error types
        raise CheckpointError(f'Unreadable checkpoint: {exc}') from exc
    if not isinstance(payload, dict) or payload.get('format') != FORMAT:
        raise CheckpointError('Unknown checkpoint format')
    if payload['config_sha256'] != object_hash(config):
        raise CheckpointError('Checkpoint was trained with a different config')
    if payload['method'] != method or payload['feature_names'] != list(FEATURE_NAMES):
        raise CheckpointError('Checkpoint method or feature schema mismatch')
    return payload
