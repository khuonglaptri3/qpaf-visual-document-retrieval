"""Replay the frozen CPU result in its exact runtime using public pinned inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import modal

EVIDENCE = Path(__file__).resolve().parent/'cpu-replay'


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    global EVIDENCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, default=EVIDENCE)
    args = parser.parse_args()
    EVIDENCE = args.evidence_dir.resolve()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    EVIDENCE.mkdir(exist_ok=False)
    auth = {'task_id': 'M5.5', 'activity': 'read-only verification of existing CPU diagnostics',
            'approval': 'Owner authorized finishing M5.5 and delegated validation implementation details',
            'source_commit': '1bdb491ec3b74f578c31dda5ba796d1d375ac586',
            'manifest_sha256': 'f141871d5adbd90c11fad5084d6c08a599009e3bd0bbbe5f60513e8eebff03be',
            'runtime': {'python': '3.11.14', 'numpy': '2.4.6', 'pandas': '3.1.0', 'pyarrow': '26.0.0'},
            'permissions': {'public_pinned_snapshot_download': True, 'validation_replay': True,
                            'development_container_read': True, 'test_qrels': False,
                            'gpu': False, 'training': False, 'new_scientific_run': False},
            'cpu_cores': 2, 'memory_mib': 4096, 'function_timeout_seconds': 300,
            'whole_app_watchdog_seconds': 600, 'invocations': 1, 'automatic_retries': 0,
            'cost_target_usd': .05, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
            'reason': 'Windows package downloads stalled; preserve exact runtime instead of weakening replay pins'}
    auth['archive_transport'] = 'Short-lived read-only asset URL; no GitHub token sent to Modal or stored'
    write(EVIDENCE/'authorization.json', auth)
    # The release is a draft: authenticate only to GitHub, then give the CPU
    # verifier a short-lived capability for this single hash-pinned asset.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            return None
    token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
    request = urllib.request.Request(
        'https://api.github.com/repos/khuonglaptri3/qpaf-visual-document-retrieval/releases/assets/669652087',
        headers={'Authorization': 'Bearer '+token, 'Accept': 'application/octet-stream',
                 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'qpaf-m55-verifier'})
    del token
    try:
        urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
        raise RuntimeError('Expected an asset download redirect')
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise RuntimeError('GitHub asset authorization failed: HTTP '+str(exc.code)) from None
        archive_url = exc.headers['Location']
    if not archive_url.startswith(('https://release-assets.githubusercontent.com/',
                                   'https://objects.githubusercontent.com/')):
        raise ValueError('Unexpected GitHub asset download host')
    image = (modal.Image.from_registry('python:3.11.14-slim-bookworm')
             .apt_install('git')
             .run_commands('timeout 240s python -m pip install --no-cache-dir '
                           'numpy==2.4.6 pandas==3.1.0 pyarrow==26.0.0')
             .env({'PYTHONDONTWRITEBYTECODE': '1'}))
    app = modal.App('qpaf-m55-cpu-replay', include_source=False)

    @app.function(image=image, cpu=(2., 2.), memory=(4096, 4096), timeout=300,
                  retries=0, max_containers=1, min_containers=0, buffer_containers=0,
                  scaledown_window=2, single_use_containers=True, serialized=True)
    def replay(archive_url):
        import json
        from pathlib import Path
        import shutil
        import subprocess
        import tempfile
        import urllib.request
        with tempfile.TemporaryDirectory(prefix='m55-cpu-replay-') as temp:
            root = Path(temp)
            for command in (['git', 'init', '-q'],
                            ['git', 'fetch', '--quiet', '--depth=1',
                             'https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git',
                             '1bdb491ec3b74f578c31dda5ba796d1d375ac586'],
                            ['git', 'checkout', '-q', '--detach', 'FETCH_HEAD']):
                subprocess.run(command, cwd=root, check=True, capture_output=True, timeout=90)
            archive = root/'m42.zip'
            request = urllib.request.Request(archive_url, headers={'User-Agent': 'qpaf-m55-read-only-verifier'})
            try:
                with urllib.request.urlopen(request, timeout=60) as incoming, archive.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            except Exception as exc:
                raise RuntimeError('Archive transport failed: '+type(exc).__name__) from None
            code = r'''
import json,os,sys
from pathlib import Path
root=Path.cwd()
sys.path.insert(0,str(root/'src'))
from qpaf.m55.runner import restore_inputs,verify,runtime_versions,sha
expected={'python':'3.11.14','numpy':'2.4.6','pandas':'3.1.0','pyarrow':'26.0.0'}
if runtime_versions()!=expected: raise ValueError('Exact CPU runtime differs')
restore_inputs(root,root/'m42.zip')
output=root/'results/m5.5/RUN-QPAF-M5_5-ABL-001-20261027T033016Z-A01'
before={p.name:sha(p) for p in output.iterdir()}
audit={'writes':0,'network':0,'forbidden_imports':0,'test_qrels':0}
def hook(event,args):
    if event=='open':
        name=str(args[0]).lower()
        if 'qrels_test' in name or 'test_qrels' in name:
            audit['test_qrels']+=1; raise RuntimeError('test qrels forbidden')
        mode=args[1] if len(args)>1 else None
        flags=args[2] if len(args)>2 else 0
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            audit['writes']+=1; raise RuntimeError('replay write forbidden')
    if event=='socket.connect':
        audit['network']+=1; raise RuntimeError('replay network forbidden')
    if event=='import' and args[0].split('.')[0] in {'torch','modal'}:
        audit['forbidden_imports']+=1; raise RuntimeError('replay GPU/cloud import forbidden')
sys.addaudithook(hook)
result=verify(root,output,'f141871d5adbd90c11fad5084d6c08a599009e3bd0bbbe5f60513e8eebff03be')
after={p.name:sha(p) for p in output.iterdir()}
if before!=after: raise ValueError('CPU output bytes changed')
print(json.dumps({'status':'PASS','verification':result,'runtime':expected,'audit':audit,
                  'run_files_sha256':after,'run_bytes_unchanged':True,
                  'execution_location':'Modal CPU, no GPU','new_scientific_run':False}))
'''
            done = subprocess.run(['python', '-c', code], cwd=root, capture_output=True, text=True, timeout=240)
            if done.returncode:
                raise RuntimeError('CPU replay failed: '+done.stdout+done.stderr)
            return json.loads(done.stdout)

    def watchdog():
        write(EVIDENCE/'_WATCHDOG.json', {'status': '600s wall limit', 'app_id': app.app_id})
        try:
            subprocess.run([sys.executable, '-m', 'modal', 'app', 'stop', '--yes', app.app_id], timeout=30)
        finally:
            os._exit(124)
    timer = threading.Timer(600, watchdog)
    timer.daemon = True
    write(EVIDENCE/'_ATTEMPTED.json', {'authorization_sha256': hashlib.sha256((EVIDENCE/'authorization.json').read_bytes()).hexdigest()})
    timer.start()
    try:
        with modal.enable_output(), app.run():
            write(EVIDENCE/'runtime_binding.json', {'app_id': app.app_id, 'image_id': image.object_id,
                                                   'gpu': False, 'local_sdk': modal.__version__})
            call = replay.spawn(archive_url)
            write(EVIDENCE/'function_call.json', {'function_call_id': call.object_id})
            result = call.get(timeout=600)
            write(EVIDENCE/'verification.json', result)
            print(json.dumps({k: v for k, v in result.items() if k != 'run_files_sha256'}, indent=2))
    except BaseException as exc:
        write(EVIDENCE/'_FAILURE.json', {'exception': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        timer.cancel()


if __name__ == '__main__':
    main()
