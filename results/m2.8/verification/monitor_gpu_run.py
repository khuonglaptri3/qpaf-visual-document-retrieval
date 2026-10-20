"""Read-only progress observer for the explicitly authorized real GPU run."""
import json
from pathlib import Path
import time
import modal

folder = Path(__file__).resolve().parents[1]/'RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01'
record = json.loads((folder/'execution.json').read_text(encoding='utf-8'))
volume = modal.Volume.from_name(record['volume'])
call = modal.FunctionCall.from_id(record['function_call_id'])
last = None
while True:
    try:
        payload = b''.join(volume.read_file(record['remote_path']+'/progress.json'))
        progress = json.loads(payload)
        key = (progress.get('stage'), progress.get('completed'), progress.get('status'))
        if key != last:
            print(json.dumps(progress, ensure_ascii=False), flush=True)
            with (folder/'progress_observations.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps(progress, ensure_ascii=False)+'\n')
            last = key
    except Exception as exc:
        print('Progress read:', type(exc).__name__, str(exc), flush=True)
    try:
        result = call.get(timeout=1)
    except TimeoutError:
        time.sleep(30)
    else:
        (folder/'gpu_result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print('TERMINAL '+json.dumps(result), flush=True)
        break
