"""Modal resources are constructed from the chosen config, never at import time."""
from pathlib import Path


def _execute_remote(stage, config, run_id, source):
    import modal
    from .pipeline import execute_stage
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    workspace = Path(config['modal']['mount_path'])/config['modal']['workspace']
    try:
        result = execute_stage(stage, config, workspace, run_id, source)
        return str(result.relative_to(Path(config['modal']['mount_path'])))
    finally:
        # Persist failed-attempt logs as well as successful stage receipts.
        volume.commit()


def cpu_stage(stage, config, run_id, source):
    return _execute_remote(stage, config, run_id, source)


def gpu_stage(stage, config, run_id, source):
    return _execute_remote(stage, config, run_id, source)


def collect_evidence(config, run_id, source):
    import modal
    from .pipeline import run_directory
    from .evidence import pack_evidence
    volume = modal.Volume.from_name(config['modal']['volume_name'])
    volume.reload()
    workspace = Path(config['modal']['mount_path'])/config['modal']['workspace']
    return pack_evidence(run_directory(workspace, run_id), config, source)


def build_app(config, repo_root):
    import modal
    from .config import validate
    validate(config)
    runtime = config['modal']
    requirement_path = Path(runtime['requirements_file'])
    if not requirement_path.is_absolute():
        requirement_path = Path(repo_root)/requirement_path
    if not requirement_path.is_file():
        raise ValueError(f'Requirements file does not exist: {requirement_path}')
    image = (modal.Image.debian_slim(python_version=runtime['python_version'])
             .apt_install(*runtime['apt_packages'])
             .pip_install_from_requirements(str(requirement_path))
             .add_local_python_source('qpaf'))
    volume = modal.Volume.from_name(runtime['volume_name'], create_if_missing=True)
    app = modal.App(runtime['app_name'])
    options = {'image': image, 'cpu': runtime['cpu'], 'memory': runtime['memory_mb'],
               'timeout': runtime['timeout'], 'volumes': {runtime['mount_path']: volume},
               'secrets': [modal.Secret.from_name(name) for name in runtime['secret_names']],
               'max_containers': 1}
    cpu = app.function(**options)(cpu_stage)
    gpu = app.function(gpu=runtime['gpu'], **options)(gpu_stage)
    collect = app.function(**options)(collect_evidence)
    return app, cpu, gpu, collect
