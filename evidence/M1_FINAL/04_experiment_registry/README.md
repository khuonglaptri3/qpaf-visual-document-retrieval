# M1.7 — Experiment Registry Draft

**Owner:** Thanh — Experiment Governance / Independent QA
**Package status:** `DRAFT_NOT_FROZEN`
**Prepared:** 27/09/2026
**Execution authorization:** `CLOSED`
**Final QA sign-off:** `NOT_CREATED`

Gói này hoàn thành phạm vi **M1.7 Draft**: schema, naming, classification,
append-only governance, traceability ban đầu, source-evidence audit và issue log.
Nó không phải M1.7 Final, không thay thế G1 review và không cấp quyền chạy OCR,
Oracle, training, evaluation, Modal/GPU hoặc external benchmark.

## Deliverables hiện có

| File | Vai trò | Trạng thái |
| --- | --- | --- |
| `experiment_registry.csv` | Append-only event ledger và schema v1 | Draft; 9 current-state records |
| `experiment_naming_rules.md` | Quy tắc ID/namespace/create-once | Draft |
| `test_classification.md` | Experiment/evidence taxonomy và claim boundary | Draft |
| `append_only_policy.md` | Quy tắc append, correction, supersession và freeze | Draft |
| `traceability_matrix.csv` | Trace method/config/commit/data/output/review | Draft; blocker được ghi rõ |
| `evidence_audit.md` | Audit nguồn evidence hiện có | Draft source review; không phải Final QA |
| `issue_log.csv` | Finding, owner và closure criterion | Open/blocking issues |

`qa_signoff.md` chưa được tạo có chủ ý. File đó chỉ được tạo sau khi M1.5 được
adopt trong NEW repository, M1.4/M1.6/M1.8 đủ review, issue quan trọng được xử
lý, package được chọn và hash, rồi Thanh re-audit một sample end-to-end.

## Ranh giới của Draft

- Registry dùng vocabulary của `../02_protocol/run_policy.md` nhưng chưa bind
  vào một active NEW protocol: package M1.5 hiện chỉ là historical import.
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

1. Phát phát hành successor/amendment và NEW-relative protocol manifest giải
   quyết contract M1.2/M1.5; Thanh review exact bytes/hash.
2. Khương bàn giao selected M1.4 revision có actual assets, M1.6 corpus audit và
   M1.8 calibration/threshold đã review.
3. Exact data/split/cache hashes và selected Git snapshot tồn tại.
4. Thanh append event mới, refresh traceability/audit, xử lý hoặc giữ explicit
   blocker, rồi cả nhóm review package.
5. Chỉ sau recheck và Technical Sign-off mới tạo `qa_signoff.md` cho Final G1.

Chạy kiểm tra Draft:

```powershell
python -m unittest tests.test_m17_registry -v
```
