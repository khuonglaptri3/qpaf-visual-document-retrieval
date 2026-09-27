"""Immutable stage attempts, hashes, logs and source/environment provenance."""
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from .config import relative_path


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    for attempt in range(5):
        try:
            os.replace(temp, path)
            return
        except PermissionError as exc:
            # Windows may briefly deny replacement in a synced workspace.
            # Keep the old file intact and surface persistent access errors.
            if getattr(exc, 'winerror', None) != 5 or attempt == 4:
                raise
            time.sleep(0.1 * 2**attempt)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_csv(path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        if not rows:
            raise ValueError('An empty table needs explicit columns')
        fields = list(rows[0])
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_manifest(root, exclude=()):
    return [{'path': path.relative_to(root).as_posix(), 'size_bytes': path.stat().st_size,
             'sha256': digest(path)}
            for path in sorted(Path(root).rglob('*')) if path.is_file()
            and path.relative_to(root).as_posix() not in exclude]


def verify_manifest(root, records):
    root = Path(root).resolve()
    seen = set()
    for row in records:
        rel = relative_path(row['path'])
        path = root.joinpath(*rel.parts).resolve()
        if not path.is_relative_to(root) or row['path'] in seen:
            raise ValueError('Unsafe or duplicate artifact path')
        seen.add(row['path'])
        if not path.is_file() or path.stat().st_size != int(row['size_bytes']) or digest(path) != row['sha256']:
            raise ValueError(f'Artifact checksum mismatch: {row["path"]}')


def source_provenance(root, requirement_path=None):
    root = Path(root).resolve()
    files = sorted(set(list((root/'src').rglob('*.py')) + list((root/'scripts').glob('*.py'))
                       + list((root/'requirements').glob('*')) + [root/'pyproject.toml']))
    records = [{'path': path.relative_to(root).as_posix(), 'sha256': digest(path)}
               for path in files if path.is_file()]
    if requirement_path is not None:
        requirement_path = Path(requirement_path)
        if not requirement_path.is_absolute():
            requirement_path = root/requirement_path
        records.append({'path': 'selected_image_requirements', 'sha256': digest(requirement_path)})

    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], text=True,
                                capture_output=True, encoding='utf-8', errors='replace')
        return result.stdout.strip() if result.returncode == 0 else None

    return {'digest': object_hash(records), 'files': records, 'git_commit': git('rev-parse', 'HEAD'),
            'git_status': git('status', '--porcelain'), 'command': [sys.executable, *sys.argv]}


def environment():
    return {'python': sys.version, 'platform': platform.platform(),
            'packages': {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()
                         if dist.metadata.get('Name')}}


def completed_stage(root, stage, config, inputs, source):
    pointer = Path(root)/stage/'complete.json'
    if not pointer.exists():
        return None
    info = read_json(pointer)
    attempt = relative_path(info['attempt'])
    path = pointer.parent.joinpath(*attempt.parts)
    if not path.resolve().is_relative_to(pointer.parent.resolve()):
        raise ValueError('Unsafe attempt path')
    if digest(path/'receipt.json') != info['receipt_sha256']:
        raise ValueError('Stage receipt checksum mismatch')
    receipt = read_json(path/'receipt.json')
    expected = (cache_config_hash(config), inputs, source.get('digest'))
    actual = (receipt['cache_config_sha256'], receipt['inputs'], receipt['source_digest'])
    if actual != expected:
        raise ValueError(f'{stage}: existing run has different config/input/source; use a new run ID')
    verify_manifest(path, receipt['outputs'])
    return path


def cache_config_hash(config):
    # Local download location cannot change scientific inputs or cloud caches.
    return object_hash({key: value for key, value in config.items() if key != 'output'})


class StageRun:
    """A failed attempt is retained; a subsequent attempt gets a fresh directory."""
    def __init__(self, root, stage, config, inputs, source):
        relative_path(stage)
        self.root = Path(root)/stage
        self.config, self.inputs, self.source = config, inputs, source
        self.path = self.root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])

    def __enter__(self):
        if (self.root/'complete.json').exists():
            raise FileExistsError('Completed stage is immutable')
        self.path.mkdir(parents=True, exist_ok=False)
        self.started = utc()
        self.logger = logging.getLogger('qpaf.m11.'+uuid.uuid4().hex)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.handler = logging.FileHandler(self.path/'run.log', encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger.addHandler(self.handler)
        self.console = logging.StreamHandler(sys.stdout)
        self.console.setFormatter(self.handler.formatter)
        self.logger.addHandler(self.console)
        write_json(self.path/'resolved_config.json', self.config)
        write_json(self.path/'status.json', {'status': 'running', 'started_utc': self.started})
        write_json(self.path/'provenance.json', {'source': self.source, 'config_sha256': object_hash(self.config),
                   'inputs': self.inputs, 'started_utc': self.started, 'environment': environment()})
        self.logger.info('stage started: %s', self.root.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        success = exc_type is None
        if success:
            self.logger.info('stage completed')
        else:
            self.logger.error('stage failed', exc_info=(exc_type, exc, tb))
        self.handler.close()
        self.logger.removeHandler(self.handler)
        self.console.close()
        self.logger.removeHandler(self.console)
        write_json(self.path/'status.json', {'status': 'completed' if success else 'failed',
                   'started_utc': self.started, 'finished_utc': utc(),
                   'error': None if success else f'{exc_type.__name__}: {exc}'})
        if success:
            records = file_manifest(self.path, exclude=('hashes.csv', 'receipt.json'))
            write_csv(self.path/'hashes.csv', records)
            records.append({'path': 'hashes.csv', 'size_bytes': (self.path/'hashes.csv').stat().st_size,
                            'sha256': digest(self.path/'hashes.csv')})
            write_json(self.path/'receipt.json', {'config_sha256': object_hash(self.config),
                       'cache_config_sha256': cache_config_hash(self.config),
                       'inputs': self.inputs, 'source_digest': self.source.get('digest'), 'outputs': records})
            if (self.root/'complete.json').exists():
                raise FileExistsError('Concurrent completion; refusing to replace stage receipt')
            write_json(self.root/'complete.json', {'attempt': self.path.name,
                       'receipt_sha256': digest(self.path/'receipt.json')})
        return False
