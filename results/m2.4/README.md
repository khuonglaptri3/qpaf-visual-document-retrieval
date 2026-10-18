# M2.4 — Bằng chứng pipeline learned

Loại: `synthetic_software_verification`. Config `configs/m2.4/pipeline.toml`
(seed 20260820, 20 epochs, Adam lr 0.01, batch 16). Đặc tả:
[m2.4-learned-pipeline.md](../../docs/03_method/m2.4-learned-pipeline.md).

| Method | Run | Epoch được chọn | Val nDCG@10 | Val MRR@10 | Reload Δ |
|---|---|---:|---:|---:|---:|
| QARF | `synthetic-verification/QARF/20261018T081405-c46dbcd9` | 12 | 0.500000 | 0.750000 | 0 |
| QPAF | `synthetic-verification/QPAF/20261018T081516-e008bcb1` | 17 | 0.556574 | 0.875000 | 0 |

Fixture: 24 train / 8 validation / 8 test query (test không mở), 12 candidate
mỗi query, mỗi query có một positive nằm ngoài union nên nDCG@10 tối đa ≈ 0.613.
Chênh lệch QARF/QPAF ở đây **không** phải bằng chứng retrieval; so sánh matched
thuộc M3 trên cache thật.

Theo quy ước repo, `checkpoints/` không vào Git (`.gitignore`); SHA-256 của
`best.pt`/`last.pt` nằm trong `summary.json` và `hashes.csv`. Chạy lại đúng lệnh
trong đặc tả tái tạo tham số gate và metric (deterministic, CPU float64); hash
file checkpoint sẽ khác vì history có thời gian chạy từng epoch.
Kiểm thử: `python -m unittest discover -s tests -p "test_m24*.py"`.
Review độc lập: PENDING.
