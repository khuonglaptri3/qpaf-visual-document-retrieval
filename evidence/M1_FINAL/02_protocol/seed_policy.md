# Seed Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1`  
> **Execution:** Closed

## 1. Seed registry

| Mục đích | Seed(s) | Quy tắc |
|---|---|---|
| Learned QARF/QPAF training | `20260820`, `20260821`, `20260822` | Cùng exact seed set cho hai methods; báo đủ ba seed |
| One-seed development gate | `20260820` | QARF chạy trước, QPAF chạy sau review; không tạo final robustness claim |
| Paired query bootstrap | `20260820` | 10.000 resamples; percentile CI95 |
| Historical 2.000-ID label-free sample | `20260820` trong namespace `20260820:<query_id>` | Identity selection, không phải training randomness |
| Frozen 1.600/400 split | namespace `vimdoc_m3_local_v1:dev_split:20260820` | Hash-order split từ exact 2.000 IDs; ID artifacts pending |
| CARF diagnostic, nếu có randomness | `20260820` | Cluster assignment phải freeze trước qrels |

Các seed có cùng số nhưng thuộc namespace khác nhau không được coi là cùng random
stream hoặc dùng thay thế lẫn nhau.

## 2. Reproducibility rules

- Config, manifest và registry record phải ghi seed dạng integer và seed purpose.
- Python, NumPy và PyTorch RNG phải được seed từ frozen training seed; data-order
  generator và worker seeding phải deterministic và được lưu trong resolved config.
- Nếu backend/hardware có nondeterministic operation, run phải fail hoặc được gắn
  `BLOCKED`; không được silently chấp nhận variance không giải thích.
- Non-random baselines có thể dùng `null` trong typed config nếu schema yêu cầu, nhưng
  M1.7 registry phải ghi controlled value `NA`; không gán seed giả.
- Split files và candidate lists được hash; không regenerate theo một order khác.

## 3. Reporting and no-result-shopping rule

- Không chọn best seed, không bỏ failed-but-valid seed và không thay seed sau khi thấy
  metric.
- Báo từng seed, mean/std across seeds và final paired analysis theo
  [statistical_policy.md](statistical_policy.md).
- Một invalid technical run chỉ được loại khi independent review ghi rõ lỗi kỹ thuật,
  artifact path và decision. Attempt vẫn được giữ trong ledger.
- Retry hoặc replacement seed cần protocol amendment/authorization mới; không được
  đổi seed để đạt threshold.

## 4. Completion rule

Positive robustness claim cần đủ cả ba seed cho matched QARF và QPAF. Nếu thiếu hoặc
invalid một seed, trạng thái là `BLOCKED`/`PARTIAL`, không phải positive final claim.
