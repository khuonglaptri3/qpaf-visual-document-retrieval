"""Measure CPU thread overhead for the unchanged F3 loss; no model tuning."""
import collections
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))
import pyarrow.parquet as pq
import torch
from qpaf.lab.variants.f3_approxndcg import approx_ndcg_loss

bundle = ROOT / "results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle"
counts = collections.Counter(pq.read_table(bundle / "raw_scores.parquet", columns=["query_id"])
                             .column("query_id").to_pylist())
units = max(counts.values())
torch.manual_seed(12345)
base = torch.rand((16, units), dtype=torch.float64)
base[:, 0] = 0.999
base[:, units // 2] = 0.99
mask = torch.ones_like(base, dtype=torch.bool)
positive = torch.zeros_like(mask)
positive[:, 0] = True
positive[:, units // 2] = True
rows, first_grad = [], None
for threads in (1, 2, 4, 6):
    torch.set_num_threads(threads)
    durations = []
    for iteration in range(6):
        scores = base.clone().requires_grad_(True)
        started = time.perf_counter()
        loss, valid = approx_ndcg_loss(scores, mask, positive, torch.zeros(()), base)
        loss.backward()
        duration = time.perf_counter() - started
        assert valid == 16 and torch.isfinite(scores.grad).all()
        assert scores.grad.abs().max() > 1e-6
        if first_grad is None:
            first_grad = scores.grad.clone()
        assert torch.allclose(scores.grad, first_grad, rtol=1e-10, atol=1e-12)
        if iteration:
            durations.append(duration)
    rows.append({"threads": threads, "seconds_per_forward_backward": sum(durations) / len(durations),
                 "loss": float(loss.detach()), "gradients_agree": True,
                 "max_abs_gradient": float(scores.grad.abs().max())})
result = {"batch_size": 16, "units": units, "concurrent_full_run_threads": 2, "rows": rows,
          "note": "Execution-only thread measurement; no model hyperparameters changed."}
Path(__file__).with_name("cpu-benchmark.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
