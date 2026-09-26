"""Config-first Modal launcher. --dry-run never imports Modal or contacts its API."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from qpaf.m11.artifacts import source_provenance
from qpaf.m11.config import load_config
from qpaf.m11.dataset import extract_zip
from qpaf.m11.evidence import verify_evidence
from qpaf.m11.pipeline import STAGES, run_directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--set', action='append', default=[], metavar='SECTION.KEY=VALUE')
    parser.add_argument('--run-id', help='Reuse the same ID/config/source to resume completed stages')
    parser.add_argument('--stage', choices=['all', *STAGES, 'fetch'], default='all')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check-sdk', action='store_true', help='Construct Modal app without API calls or GPU execution')
    args = parser.parse_args(argv)
    config = load_config(args.config, args.set)
    if args.stage != 'all' and not args.run_id:
        parser.error('--run-id is required when selecting a stage or fetching evidence')
    run_id = args.run_id or (datetime.now(timezone.utc).strftime('m11-%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    run_directory(Path('.'), run_id) # validate before cloud work
    source = source_provenance(ROOT, config['modal']['requirements_file'])
    stages = list(STAGES) if args.stage == 'all' else [args.stage]
    if args.dry_run:
        print(json.dumps({'run_id': run_id, 'stages': stages, 'config': config, 'source': source}, indent=2))
        return 0
    from qpaf.m11.modal_app import build_app
    app, cpu, gpu, collect = build_app(config, ROOT)
    if args.check_sdk:
        print(json.dumps({'status': 'app_constructed_without_remote_execution', 'app': config['modal']['app_name'],
                          'gpu': config['modal']['gpu'], 'volume': config['modal']['volume_name']}))
        return 0
    local_root = Path(config['output']['local_dir'])
    if not local_root.is_absolute():
        local_root = ROOT/local_root
    destination = local_root/run_id
    if ('oracle' in stages or 'fetch' in stages) and destination.exists():
        raise FileExistsError(f'Local evidence already exists: {destination}; change output.local_dir to fetch elsewhere')
    import modal
    print(f'Run: {run_id}; volume: {config["modal"]["volume_name"]}', flush=True)
    with modal.enable_output(), app.run():
        for stage in stages:
            if stage == 'fetch':
                continue
            remote = gpu if stage in ('dense', 'visual') and config[stage]['device'] == 'cuda' else cpu
            path = remote.remote(stage, config, run_id, source)
            print(f'{stage}: {path}', flush=True)
        if 'oracle' in stages or 'fetch' in stages:
            payload = collect.remote(config, run_id, source)
            # ZIP received from our worker; still apply the same traversal checks.
            destination.mkdir(parents=True, exist_ok=False)
            extract_zip(io.BytesIO(payload), destination)
            verify_evidence(destination)
            print(f'Verified evidence: {destination}', flush=True)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ValueError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2)
