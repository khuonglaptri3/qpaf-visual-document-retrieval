"""Run the repository regression suite in the pinned M2.2 Modal CPU image."""
import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import modal
from qpaf.m11.artifacts import digest, source_provenance, utc, write_json


def run_suite(payload):
    from qpaf.m11.dataset import extract_zip
    from qpaf.m22.worker import runtime_info
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        extract_zip(io.BytesIO(payload), root)
        # Tests call git rev-parse; this is an explicitly synthetic test checkout.
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        subprocess.run(['git', '-c', 'user.name=Test Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '--allow-empty', '-qm', 'Synthetic checkout for regression tests'], cwd=root, check=True)
        env = dict(os.environ, PYTHONPATH=str(root/'src'), PYTHONUTF8='1')
        process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
            cwd=root, env=env, capture_output=True, text=True, timeout=900)
        return {'completed_utc': utc(), 'returncode': process.returncode, 'stdout': process.stdout,
                'stderr': process.stderr, 'environment': runtime_info(),
                'checkout_note': 'Source snapshot extracted into a synthetic Git repository for CLI tests.'}


def main():
    files = set(subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines())
    for dirname in ('src', 'scripts', 'tests', 'configs', 'requirements'):
        files.update(p.relative_to(ROOT).as_posix() for p in (ROOT/dirname).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            path = ROOT/name
            if path.is_file():
                archive.write(path, name)
    image = (modal.Image.debian_slim(python_version='3.11')
        .apt_install('tesseract-ocr', 'tesseract-ocr-eng', 'libglib2.0-0', 'libgl1', 'git')
        .pip_install_from_requirements(str(ROOT/'requirements/m22-modal.lock'))
        .env({'TOKENIZERS_PARALLELISM': 'false', 'HF_HUB_DISABLE_TELEMETRY': '1'})
        .add_local_python_source('qpaf'))
    app = modal.App('qpaf-m22-verification')
    remote = app.function(image=image, cpu=4, memory=8192, timeout=1200, retries=0)(run_suite)
    snapshot_source = source_provenance(ROOT, 'requirements/m22-modal.lock')
    test_files = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': digest(p)}
                  for p in sorted((ROOT/'tests').glob('*.py'))]
    with modal.enable_output(), app.run():
        result = remote.remote(data.getvalue())
    result['uploaded_snapshot_sha256'] = hashlib.sha256(data.getvalue()).hexdigest()
    result['source'] = snapshot_source
    result['test_files'] = test_files
    result['source_unchanged_during_tests'] = snapshot_source['digest'] == source_provenance(ROOT, 'requirements/m22-modal.lock')['digest']
    out = ROOT/'results/m2.2/verification'
    out.mkdir(parents=True, exist_ok=True)
    filename = out/('tests-'+result['completed_utc'].replace(':','').replace('+','_')+'.json')
    write_json(filename, result)
    print(result['stderr'][-10000:])
    print(filename)
    return result['returncode']


if __name__ == '__main__':
    raise SystemExit(main())
