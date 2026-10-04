# Statistical Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1`  
> **Primary comparison unit:** query

## 1. Paired analysis

Mọi comparison claim-bearing phải paired trên cùng query, candidate rows, split và
evaluation code. Primary delta cho query `q`, seed `s`:

`delta(q,s) = nDCG@10_QPAF(q,s) - nDCG@10_comparator(q,s)`.

Comparator bắt buộc gồm matched learned QARF và từng co-strongest deployable baseline.

## 2. Three-seed aggregation

- Báo riêng aggregate/per-query metrics cho từng seed.
- Báo mean và sample standard deviation của aggregate metric qua ba seeds.
- Với final paired test, trước hết tính mean của `delta(q,s)` qua đúng ba seeds cho
  từng query; sau đó bootstrap trên vector one-value-per-query này.
- Không coi ba seed của cùng query là ba independent observations.

## 3. Bootstrap confidence interval

- Resampling unit: query, paired across methods.
- Resamples: `10,000`.
- RNG: NumPy `default_rng`, seed `20260820`.
- Sample size mỗi resample bằng số query, sampling with replacement.
- Statistic: mean paired delta.
- CI: percentile `[2.5%, 97.5%]`.
- Empty/incomplete/misaligned samples bị reject; không impute query.

## 4. Win / Tie / Loss

Trên seed-averaged per-query delta:

- Win: `delta > 1e-12`;
- Tie: `abs(delta) <= 1e-12`;
- Loss: `delta < -1e-12`.

Báo count và fraction; tổng W/T/L phải bằng exact query count.

## 5. Gain concentration

1. Clip negative deltas về 0 để có positive-gain vector.
2. `top_count = max(1, ceil(0.05 * N))`.
3. `top_5pct_gain_share = sum(top top_count positive gains) / sum(all positive gains)`;
   bằng 0 nếu total positive gain bằng 0.

Stable-gain claim yêu cầu share `< 0.90`. Nếu `>= 0.90`, H3 fail và outcome tối đa là
`PARTIAL` cho broad stability claim, kể cả khi mean/CI đạt.

## 6. Decision table

| Evidence | Decision |
|---|---|
| Mean delta `>=0.01`, CI lower `>0`, strongest baseline beaten, concentration and operational gates pass | Positive core claim eligible after independent review |
| Mean/CI pass nhưng concentration `>=0.90` | `PARTIAL`; claim phải thu hẹp và nêu concentration |
| Quality pass nhưng latency/memory/reload fail | Research-quality result only; no operational-good-enough claim |
| Mean `<0.01` hoặc CI lower `<=0` trên valid final protocol | H1 not supported; report negative/inconclusive result, prefer simpler method |
| Pairing, hashes, split, seed hoặc query coverage invalid | `BLOCKED`; no scientific interpretation |

Không dùng secondary metric, subgroup hoặc alternative CI post-hoc để đảo primary
decision. Multiple exploratory/ablation comparisons phải được label diagnostic; không
được nhập vào core confirmatory claim như independent confirmatory tests.

## 7. Independent verification

Verifier phải recompute metrics, per-query deltas, seed averages, bootstrap CI, W/T/L
và concentration từ saved predictions/per-query artifacts, không chỉ tin summary JSON.
