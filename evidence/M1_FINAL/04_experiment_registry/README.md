# M1.7 — Experiment Registry Draft

**Owner:** Thanh — Experiment Governance / Independent QA
**Package status:** `DRAFT_RECONCILED_FINAL_BLOCKED`
**Prepared:** 27/09/2026; **post-merge reconciliation:** 28/09/2026
**Execution authorization:** `CLOSED`
**Final QA sign-off:** `NOT_CREATED`

Gói này hoàn thành phạm vi **M1.7 Draft**: schema, naming, classification,
append-only governance, traceability ban đầu, source-evidence audit và issue log.
Nó không phải M1.7 Final, không thay thế G1 review và không cấp quyền chạy OCR,
Oracle, training, evaluation, Modal/GPU hoặc external benchmark.

## Deliverables hiện có

| File | Vai trò | Trạng thái |
| --- | --- | --- |
| `experiment_registry.csv` | Append-only event ledger và schema v1 | Draft; 14 events, gồm 5 post-merge review events |
| `experiment_naming_rules.md` | Quy tắc ID/namespace/create-once | Draft |
| `test_classification.md` | Experiment/evidence taxonomy và claim boundary | Draft |
| `append_only_policy.md` | Quy tắc append, correction, supersession và freeze | Draft |
| `traceability_matrix.csv` | Trace method/config/commit/data/output/review | Draft; 14 traces, giữ các revision cũ |
| `evidence_audit.md` | Audit nguồn evidence hiện có | Reconciled source/hash review; không phải Final QA |
| `issue_log.csv` | Finding, owner và closure criterion | 16 finding; 6 finding mới sau merge |

`qa_signoff.md` chưa được tạo có chủ ý. File đó chỉ được tạo sau khi M1.5 được
adopt trong NEW repository, M1.4/M1.6/M1.8 đủ review, issue quan trọng được xử
lý, package được chọn và hash, rồi Thanh re-audit một sample end-to-end.

## Reconciliation ngày 28/09/2026

Snapshot được kiểm là `765803fee5465006658de35a4272414b27a5bb53`, đồng nhất
với `origin/develop` tại thời điểm review. Registry append event mới cho M1.4,
M1.5, M1.6, M1.8 và một event tổng hợp M1.7; các row ngày 27/09 không bị sửa.

- M1.4 `m1.4-003`: có inventory mới nhưng metadata vẫn `PARTIAL`, data count 0.
- M1.5 A001/A002: Research Lead đã approve; A001 khớp integrated pairwise-loss
  source/config, nhưng exact amended package/split hashes và independent sign-off
  còn thiếu.
- M1.6 `m1.6-001`: engine tests pass, nhưng ba CSV không khớp declared SHA-256,
  năm source PDF không resolve và full-corpus scope chưa được chứng minh.
- M1.8 `m1.8-001`: 4/4 declared payload hashes verify; threshold vẫn
  `PROVISIONAL`, chờ M2.3 hoặc explicit G1 scope decision.
- G1/R1: current documents vẫn là pre-merge preparation; official G1 `NOT_RUN`.

Kết quả reconciliation là `M1.7_DRAFT_RECONCILED__M1.7_FINAL_BLOCKED`.
Execution vẫn đóng và không có Final QA claim.

## Ranh giới của Draft

- Registry dùng vocabulary của `../02_protocol/run_policy.md` và đã trace hai
  amendment mới, nhưng chưa bind Final vì amended package identity, exact split
  hashes và independent sign-off còn thiếu.
- Mỗi ô CSV có giá trị; dùng `NA`, `PENDING`, `UNKNOWN` hoặc `NOT_RECORDED`
  thay vì để trống. `UNKNOWN`/`NOT_RECORDED` luôn có issue tương ứng.
- Schema có explicit `split_id`/`split_sha256`, retry lineage và hash-bound
  authorization manifest; các giá trị chưa có vẫn giữ blocker, không được đoán.
- Dòng M1.1 chỉ là `oracle_upper_bound`; M1.2 chỉ là software/engineering
  evidence. Không có learned scientific result nào được đăng ký.
- Không có event `AUTHORIZED` hoặc `STARTED`; mọi result-bearing execution giữ
  trạng thái đóng.
- Status mới phải append row mới. Không sửa row cũ để biến blocker thành PASS.

## Điều kiện chuyển sang M1.7 Final

1. Phát phát hành NEW-relative immutable protocol identity bind A001/A002, exact
   affected hashes và A002 split manifests; Thanh recheck.
2. Khương bàn giao M1.4 revision đủ data/provenance và append-only M1.6 revision
   có valid payload hashes, resolvable source locators và reviewed corpus scope.
3. Phát + Khương ghi explicit decision cho M1.8 provisional-vs-calibrated scope.
4. Exact data/split/cache hashes và selected Git snapshot tồn tại.
5. Thanh append event mới, refresh traceability/audit, xử lý hoặc giữ explicit
   blocker, rồi cả nhóm review package.
6. Chỉ sau recheck và Technical Sign-off mới tạo `qa_signoff.md` cho Final G1.

Chạy kiểm tra Draft:

```powershell
python -m unittest tests.test_m17_registry -v
```
