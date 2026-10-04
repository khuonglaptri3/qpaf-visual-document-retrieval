# Baseline Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1_EXECUTION_EVIDENCE_PENDING`  
> **Execution:** Closed

## 1. Required deployable roster

| Baseline | Adaptation | Frozen rule |
|---|---|---|
| BM25 | Single retriever | Same OCR, candidate rows và document evaluation; no confirmation fitting |
| BGE-M3 | Single retriever | Frozen model revision; same candidate/evaluation rows |
| ColQwen2.5 | Single retriever | Frozen model/runtime revision; same candidate/evaluation rows |
| Uniform normalized sum / CombSUM | Static | Exact weights `(1/3, 1/3, 1/3)` over normalized channels |
| RRF | Static rank fusion | `k=60`, frozen before confirmation |
| Train-fitted static weighted fusion | Global | Fit weights only on train; freeze before validation/confirmation reporting |
| Learned QARF | Query-adaptive | Mandatory matched comparator; same protocol as QPAF except gate granularity |

Learned QPAF là proposed method, không phải baseline.

## 2. Context-only and diagnostic rows

- Oracle QARF và oracle QPAF W7/W66 là non-deployable upper bounds; chỉ được đặt ở
  bảng context riêng.
- CARF là optional label-free-cluster oracle diagnostic/ablation; không phải required
  deployable baseline và không gate Phase 2.
- Một-hidden-layer gate/LTR chỉ là preregistered optional ablation sau core gates; nó
  không được thay linear gate trong primary comparison.

## 3. Strongest deployable baseline rule

1. Mỗi required baseline phải chạy trên same frozen development rows/evaluation.
2. Fitted components chỉ dùng train labels; validation được dùng theo frozen
   checkpoint/model-selection rule.
3. Trước khi mở untouched confirmation, chọn baseline có validation mean document
   nDCG@10 cao nhất.
4. Các baseline có mean nDCG@10 cách best không quá `1e-12` là **co-strongest**.
5. QPAF phải vượt từng co-strongest baseline trong paired confirmation analysis;
   không dùng secondary metric để loại một tied baseline.
6. Baseline selection artifact phải ghi candidates, config hashes, validation metrics,
   tied set, selected/co-selected IDs và independent verifier.

Oracle rows không đủ điều kiện tham gia strongest-deployable selection.

## 4. Fairness requirements

- Exact same candidate rows/order, qrels, split IDs và evaluation implementation.
- Same raw/normalized score cache for all fusion methods.
- Learned QARF và QPAF dùng same 13 features, loss, optimizer, budget và seeds.
- Single-channel/static baselines không được hưởng candidate pool khác.
- No confirmation-label fitting, baseline dropping hoặc post-hoc parameter search.

## 5. Current gaps after freeze, before execution

- Train-fitted static weighting config/search space/tie rule chưa có exact adopted
  artifact/hash.
- Real ViMDoc score cache và candidate rows chưa verified.
- ColQwen2.5 live runtime parity chưa verified cho ViMDoc.
- Baseline selection artifact chưa thể tạo trước real development outputs.

M1.5 có thể freeze roster và selection rule, nhưng không được đánh dấu baseline runs
hoặc strongest baseline là complete cho đến khi các evidence trên tồn tại.
