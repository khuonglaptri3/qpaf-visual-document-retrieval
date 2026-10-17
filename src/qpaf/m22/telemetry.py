"""Synchronized timings and polled process-RSS peaks, with failure persistence."""
from contextlib import contextmanager
import threading
import time


class Telemetry:
    def __init__(self):
        self.phases = []
        self.peak_rss_mb = 0.

    @contextmanager
    def phase(self, name):
        import psutil
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        process, stop = psutil.Process(), threading.Event()
        peak = [process.memory_info().rss]

        def poll():
            while not stop.wait(.02):
                peak[0] = max(peak[0], process.memory_info().rss)

        thread = threading.Thread(target=poll, daemon=True)
        thread.start()
        started = time.perf_counter()
        try:
            yield
        finally:
            if cuda:
                torch.cuda.synchronize()
            elapsed = time.perf_counter()-started
            stop.set()
            thread.join()
            peak[0] = max(peak[0], process.memory_info().rss)
            rss_mb = peak[0]/1024**2
            self.peak_rss_mb = max(self.peak_rss_mb, rss_mb)
            self.phases.append({'phase': name, 'seconds': elapsed, 'peak_rss_mb': rss_mb,
                                'peak_cuda_allocated_mb': torch.cuda.max_memory_allocated()/1024**2 if cuda else 0.,
                                'peak_cuda_reserved_mb': torch.cuda.max_memory_reserved()/1024**2 if cuda else 0.})


def failure_record(exc):
    import traceback
    message = f'{type(exc).__name__}: {exc}'
    lower = message.lower()
    kind = 'OOM' if isinstance(exc, MemoryError) or 'out of memory' in lower else 'TIMEOUT' if isinstance(exc, TimeoutError) or 'timeout' in lower else 'ERROR'
    return {'status': 'FAIL', 'failure_kind': kind, 'error': message,
            'traceback': ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}
