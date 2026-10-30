"""Compare the unchanged dense objective against its positive-rank implementation."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
import torch
from test_lab_f3 import dense_approx_reference, LargestTensor
from qpaf.lab.variants.f3_approxndcg import approx_ndcg_loss

torch.set_num_threads(6)
torch.manual_seed(12345)
base = torch.rand((16, 579), dtype=torch.float64)
base[:, 0], base[:, 289] = 0.999, 0.99
mask = torch.ones_like(base, dtype=torch.bool)
positive = torch.zeros_like(mask)
positive[:, 0], positive[:, 289] = True, True
outputs, rows = {}, {}
functions = {
    "dense": lambda s: dense_approx_reference(s, mask, positive),
    "positive_ranks": lambda s: approx_ndcg_loss(s, mask, positive, torch.zeros(()), None),
}
for name, function in functions.items():
    times = []
    for i in range(6):
        scores = base.clone().requires_grad_(True)
        started = time.perf_counter()
        loss, count = function(scores)
        loss.backward()
        elapsed = time.perf_counter() - started
        if i:
            times.append(elapsed)
    outputs[name] = (loss.detach(), scores.grad)
    with LargestTensor() as allocations:
        value, _ = function(base.clone().requires_grad_(True))
        value.backward()
    rows[name] = {"loss": float(loss.detach()), "valid_queries": count,
                  "seconds_per_forward_backward": sum(times) / len(times),
                  "largest_intermediate_elements": allocations.elements}
torch.testing.assert_close(outputs["dense"][0], outputs["positive_ranks"][0], rtol=1e-12, atol=1e-12)
torch.testing.assert_close(outputs["dense"][1], outputs["positive_ranks"][1], rtol=1e-10, atol=1e-12)
result = {"shape": [16, 579], "positives_per_query": 2, "threads": 6, "rows": rows,
          "loss_and_gradients_match": True,
          "speedup": rows["dense"]["seconds_per_forward_backward"] / rows["positive_ranks"]["seconds_per_forward_backward"],
          "note": "Microbenchmark only; full experiments retain the original objective and recipe."}
Path(__file__).with_name("sparse-benchmark.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
