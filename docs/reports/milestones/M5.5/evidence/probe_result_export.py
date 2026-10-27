"""Check the result channel on a tiny CPU-only restricted Function before GPU."""
from pathlib import Path
import sys

import modal

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from scripts.run_m55_gpu import BASE_IMAGE, invoke_once  # noqa: E402
from scripts.m55_gpu_worker import write_new  # noqa: E402


def main():
    output = Path(__file__).resolve().parent/'export-probe'
    output.mkdir(exist_ok=False)
    write_new(output/'authorization.json', {'purpose': 'CPU-only restricted artifact export check',
                                          'gpu': False, 'invocations': 1, 'retries': 0,
                                          'timeout_seconds': 60, 'source_payload': 'synthetic integer sequence'})
    image = (modal.Image.from_registry(BASE_IMAGE)
             .env({'PYTHONPATH': '/workspace', 'PYTHONDONTWRITEBYTECODE': '1'})
             .add_local_file(ROOT/'scripts/m55_gpu_transport.py', '/workspace/scripts/m55_gpu_transport.py', copy=True)
             .workdir('/workspace'))
    app = modal.App('qpaf-m55-result-export-probe', include_source=False)

    @app.function(image=image, cpu=(.25, .25), memory=(512, 512), timeout=60,
                  retries=0, max_containers=1, min_containers=0, buffer_containers=0,
                  scaledown_window=2, single_use_containers=True, serialized=True,
                  block_network=True, restrict_modal_access=True)
    def probe():
        from scripts.m55_gpu_transport import encode_result
        metadata, chunks = encode_result({'status': 'COMPLETED', 'rows': list(range(10000))})
        for chunk in chunks:
            print(chunk, flush=True)
        return metadata
    with app.run():
        write_new(output/'runtime_binding.json', {'app_id': app.app_id, 'image_id': image.object_id, 'gpu': False})
        result = invoke_once(probe, output)
    if result != {'status': 'COMPLETED', 'rows': list(range(10000))}:
        raise ValueError('synthetic export round-trip differs')
    write_new(output/'verification.json', {'status': 'PASS', 'row_count': 10000, 'gpu_invocations': 0,
                                          'restricted_function': True, 'network_blocked': True,
                                          'full_result_verified': True})
    print('PASS: restricted CPU result export, 10000 integers, no GPU')


if __name__ == '__main__':
    main()
