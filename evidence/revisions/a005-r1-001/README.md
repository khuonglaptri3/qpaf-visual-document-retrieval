# A005-R1 — training tinh chỉnh (post-hoc) cho QARF-SA / QPAF-SA

Cấu hình chốt trước khi xem kết quả: anchor `[0.1, 0.2, 0.7]`, epsilon 1e-6 (A005 dùng 1e-3), 40 epoch với
LR cosine từ 0,01, trung bình đều trọng số của 21 checkpoint epoch 20–40 (không chọn epoch), ensemble 3 seed
(20260820/21/22), cùng cấu hình cho `query` và `page`. Mọi thứ khác giống A005 Stage 4.

Nội dung (mọi file ghi create-once, `*.pt` được force-add, mỗi file khoảng 2,7 KB):

- `runs/<variant>-<qarf|qpaf>-sa-r1-<seed>/`: `result.json` (history 0–40, nDCG validation và per-query của model
  trung bình và model best-epoch, sha checkpoint, `source_commit`), `averaged.pt`, `best_epoch.pt`.
  `full`: 2 granularity x 3 seed. Ablation `eps1e3` (epsilon 1e-3) và `constlr` (LR cố định 0,01): seed 20260820.
- `validation.json`: bảng validation (7 dòng mỗi granularity, kèm delta so với `train_fitted_static` 0,956878).
- `confirmation.json`: confirmation mở một lần cho cấu hình `full`, ghi `post_hoc: true`.

| nDCG@10 confirmation | Giá trị |
| --- | ---: |
| `train_fitted_static` | 0,958940 |
| QPAF-SA-v2 gốc (3 seed) | 0,960760 |
| QARF-SA-R1 ensemble | 0,961391 |
| QPAF-SA-R1 ensemble | 0,961556 |

Confirmation đã được mở một lần ở Stage 5 của A005, nên các con số này là post-hoc; kết quả sạch vẫn là A005.
Xem `docs/06_handover/a005-result-report.md`, mục 6.

## Replay

```powershell
.venv/Scripts/python.exe scripts/train_a005_refine.py --cache <cache> --variant full --granularity page --seed 20260820
.venv/Scripts/python.exe scripts/evaluate_a005_refine.py --cache <cache> --validation
```
