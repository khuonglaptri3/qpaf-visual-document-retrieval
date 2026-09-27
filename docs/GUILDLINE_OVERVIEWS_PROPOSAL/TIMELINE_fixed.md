# KẾ HOẠCH HOÀN THÀNH TIMELINE 14–27/09 TRONG 5 NGÀY

**Thời gian thực hiện:** 23/09/2026 – 27/09/2026

**Mục tiêu:** Hoàn thành toàn bộ các nhiệm vụ còn lại của Milestone M1 từ M1.4 đến M1.10 và đóng M1 vào cuối ngày 27/09.

---

## 1. Phân công tổng thể

| Thành viên   | Vai trò chính                  | Nhiệm vụ chịu trách nhiệm                                                                           |
| ------------ | ------------------------------ | --------------------------------------------------------------------------------------------------- |
| **Khương**   | Technical / Data Owner         | M1.4 Repository Audit, M1.6 Collision Audit, M1.8 OCR & Artifact Namespace, xử lý technical blocker |
| **Tấn Phát** | Research Lead / Protocol Owner | M1.5 Protocol Freeze, M1.9 G1 Gate, M1.10 Progress Report, quản lý blocker                          |
| **Thanh**    | Experiment Governance / QA     | M1.7 Experiment Registry, traceability, independent evidence audit, final QA                        |

---

# 2. MASTER TIMELINE 23–27/09

| Ngày      | Người        | Task                                       | Công việc chi tiết                                                                                                                            | Deliverable cuối task                                                                         | Việc song song                                                                    | Queue / Phụ thuộc                                                          |
| --------- | ------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **23/09** | **Khương**   | **M1.4 Repository Audit**                  | Kiểm kê source code, dataset, config, experiment cũ, output, Git commit, branch, hash; xác định file thiếu và run không trace được            | Repository inventory, data inventory, config inventory, run inventory, hash manifest, gap log | Song song với M1.5 của Phát và M1.7 Draft của Thanh                               | **Queue 1 – bắt đầu ngay**, không cần chờ task khác                        |
| **23/09** | **Tấn Phát** | **M1.5 Protocol Freeze – Draft**           | Chốt research question, dataset role, split, primary/secondary metric, seeds, baselines, QARF/QPAF comparison, statistical policy, run policy | Experiment Protocol Draft                                                                     | Song song với M1.4 và M1.7 Draft                                                  | **Queue 1 – bắt đầu ngay**                                                 |
| **23/09** | **Thanh**    | **M1.7 Experiment Registry – Draft**       | Thiết kế experiment ID, naming rule, schema, seed field, config field, Git commit field, output field, test classification, append-only rule  | Registry schema v1                                                                            | Song song với M1.4 và M1.5                                                        | **Queue 1 – dựng schema trước**, chưa freeze cho tới khi M1.5 hoàn tất     |
| **24/09** | **Khương**   | **M1.6 Collision Audit**                   | Kiểm duplicate document/page/content, aliases, hash duplicates, split leakage, qrel inconsistency, orphan records                             | Page manifest, alias manifest, duplicate/collision report                                     | Song song với Phát freeze protocol và Thanh freeze registry                       | **Queue 2 – chỉ bắt đầu sau khi M1.4 đủ dữ liệu**                          |
| **24/09** | **Khương**   | **M1.8 Draft OCR / Artifact Plan**         | Trong lúc collision scripts chạy, chuẩn bị OCR checklist, failure threshold và cấu trúc artifact                                              | OCR draft + artifact namespace draft                                                          | Có thể làm song song với M1.6 nếu đang chờ script/output                          | **Queue phụ – bắt đầu sau khi cấu trúc repo từ M1.4 đã rõ**                |
| **24/09** | **Tấn Phát** | **M1.5 Final Freeze**                      | Đối chiếu protocol với trạng thái repo/data thực tế; chốt split, metrics, seeds, baseline roster, change-control                              | Frozen Protocol                                                                               | Song song với M1.6                                                                | **Queue 2 – cần input M1.4 để kiểm feasibility nhưng không phải chờ M1.6** |
| **24/09** | **Tấn Phát** | **G1 Checklist Preparation**               | Tạo danh sách điều kiện cần kiểm tra trước G1; map mỗi requirement tới evidence và owner                                                      | G1 checklist v1                                                                               | Song song với Thanh freeze M1.7                                                   | **Sau M1.5 Freeze**                                                        |
| **24/09** | **Thanh**    | **M1.7 Registry Freeze**                   | Đồng bộ registry với protocol đã freeze; chốt naming, test classification, traceability fields                                                | Experiment Registry Final                                                                     | Song song với M1.6                                                                | **Queue 2 – Draft có thể trước, Final phải chờ M1.5 Freeze**               |
| **25/09** | **Khương**   | **M1.8 Final**                             | Chốt OCR calibration rule, khi nào dùng native text/OCR, failure threshold, artifact naming, canonical output structure                       | OCR checklist + failure threshold + artifact namespace                                        | Song song với Independent Audit và Pre-G1                                         | **Queue 3 – cần M1.4 và hiểu trạng thái data/repo; không cần đợi G1**      |
| **25/09** | **Thanh**    | **Independent Evidence Audit**             | Kiểm Run → Config → Commit → Data → Hash → Output; kiểm registry có tuân thủ protocol; lập issue list                                         | Evidence audit report + issue list                                                            | Song song với M1.8 và Pre-G1                                                      | **Queue 3 – cần M1.5 + M1.7 đã freeze; tốt nhất M1.4/M1.6 đã gần xong**    |
| **25/09** | **Tấn Phát** | **G1 Pre-review**                          | Tổng hợp evidence từ M1.4–M1.8; kiểm requirement nào chưa đủ; xác định blocker trước gate                                                     | G1 readiness matrix                                                                           | Song song với Thanh audit và Khương M1.8                                          | **Queue 3 – cần evidence từ M1.4–M1.7, M1.8 có thể hoàn tất trong ngày**   |
| **25/09** | **Cả nhóm**  | **M1.9 G1 – First Review**                 | Đánh giá toàn bộ starting evidence và frozen protocol; phân loại PASS/PARTIAL/BLOCKED/FAIL                                                    | G1 decision v1 + blocker list                                                                 | Không chạy song song với các task có thể thay đổi evidence trong thời điểm review | **Queue 4 – chỉ chạy khi M1.4–M1.8 đã đủ evidence để review**              |
| **25/09** | **Tấn Phát** | **M1.10 Draft Report**                     | Viết sẵn objective, completed work, evidence, status, risk; chừa final G1 result                                                              | Sprint Report Draft                                                                           | Có thể song song sau khi G1 lần 1 có blocker list                                 | **Sau G1 v1 hoặc khi evidence chính đã đủ**                                |
| **26/09** | **Khương**   | **Technical Blocker Fix**                  | Sửa missing hash, collision, wrong manifest, config/output mismatch, OCR issues, artifact path                                                | Updated technical evidence                                                                    | Song song với Thanh và Phát sửa blocker của phần mình                             | **Queue 5 – dựa trên blocker list từ G1**                                  |
| **26/09** | **Thanh**    | **Governance / Evidence Fix**              | Sửa registry metadata, naming, missing links, test classification, traceability issues                                                        | Registry vFinal + updated audit                                                               | Song song với Khương và Phát                                                      | **Queue 5 – dựa trên G1 issues**                                           |
| **26/09** | **Tấn Phát** | **Protocol / Governance Fix**              | Xử lý protocol blocker, amendment nếu cần, hoàn thiện G1 evidence matrix                                                                      | Updated frozen protocol/amendment                                                             | Song song với technical/evidence fix                                              | **Queue 5 – dựa trên G1 issues**                                           |
| **26/09** | **Tấn Phát** | **M1.10 Progress Report**                  | Hoàn thiện report, thêm blocker resolution, current status, next sprint                                                                       | R1 draft gần final                                                                            | Song song với việc sửa blocker                                                    | **Có thể làm sau khi G1 v1 đã có**                                         |
| **26/09** | **Cả nhóm**  | **G1 Recheck**                             | Kiểm tra lại các blocker đã sửa                                                                                                               | Provisional PASS hoặc issue remaining                                                         | Sau khi 3 owner báo fix hoàn tất                                                  | **Queue 6 – chờ blocker quan trọng được xử lý**                            |
| **27/09** | **Khương**   | **Technical Freeze**                       | Final verification repository, hashes, data manifest, collision, OCR, artifact structure                                                      | Technical Sign-off                                                                            | Song song với Thanh Final QA                                                      | **Queue 7 – sau toàn bộ technical blocker fix**                            |
| **27/09** | **Thanh**    | **Final Independent QA + Registry Freeze** | Kiểm registry, traceability, naming, evidence completeness; random trace một số run end-to-end                                                | QA Sign-off + Registry Freeze                                                                 | Song song với Khương Technical Freeze                                             | **Queue 7 – sau governance blocker fix**                                   |
| **27/09** | **Tấn Phát** | **M1.9 Final G1**                          | Nhận sign-off từ Khương và Thanh, review final evidence, chốt gate                                                                            | G1 Final Decision                                                                             | Phải chờ Khương + Thanh hoàn thành sign-off                                       | **Queue 8 – bắt buộc chờ Technical Freeze + Final QA**                     |
| **27/09** | **Tấn Phát** | **M1.10 Final Report**                     | Cập nhật final G1 decision, closed issues, remaining risks, next sprint M2                                                                    | Sprint 1 Progress Report Final                                                                | Sau Final G1                                                                      | **Queue 9 – task cuối cùng**                                               |
| **27/09** | **Cả nhóm**  | **Close M1**                               | Freeze toàn bộ M1 evidence package và sẵn sàng chuyển M2                                                                                      | M1 CLOSED                                                                                     | Không mở task mới                                                                 | **Queue cuối – chỉ sau G1 final**                                          |

---

# 3. NHIỆM VỤ CHI TIẾT – KHƯƠNG

## Vai trò

**Technical & Data Owner**

Khương chịu trách nhiệm đảm bảo:

* repository có thể kiểm tra;

* data có thể trace;

* run có thể xác định nguồn;

* corpus không có collision chưa xử lý;

* OCR/artifact pipeline có quy tắc;

* technical evidence đủ để G1 PASS.

---

## Timeline Khương

| Ngày      | Task       | Công việc chi tiết                  | Output                     | Việc song song                                | Queue                             |
| --------- | ---------- | ----------------------------------- | -------------------------- | --------------------------------------------- | --------------------------------- |
| **23/09** | M1.4       | Audit source code                   | Danh sách module + status  | Phát làm M1.5; Thanh làm M1.7                 | Queue 1                           |
| 23/09     | M1.4       | Audit dataset/data                  | Data inventory             | Song song nội bộ nếu chia script/manual check | Queue 1                           |
| 23/09     | M1.4       | Audit configs                       | Config inventory           | —                                             | Sau source/data discovery         |
| 23/09     | M1.4       | Audit historical runs               | Run inventory              | —                                             | Sau khi config structure rõ       |
| 23/09     | M1.4       | Git audit                           | Commit/branch snapshot     | Có thể song song với run audit                | Không phụ thuộc                   |
| 23/09     | M1.4       | Hash generation/verification        | Hash manifest              | Có thể chạy script song song với manual audit | Sau khi file list đủ              |
| 23/09     | M1.4       | Gap identification                  | Gap log                    | Cuối M1.4                                     | Sau toàn bộ audit                 |
| **24/09** | M1.6       | Generate page/content manifest      | Page manifest              | Phát/Thanh làm việc riêng                     | Sau M1.4                          |
| 24/09     | M1.6       | Detect duplicate content            | Duplicate report           | Có thể chạy tự động trong khi draft M1.8      | Sau manifest                      |
| 24/09     | M1.6       | Check aliases                       | Alias manifest             | Song song collision checks                    | Sau M1.4                          |
| 24/09     | M1.6       | Check split leakage                 | Leakage report             | Song song duplicate checks                    | Cần split info từ protocol nếu có |
| 24/09     | M1.6       | Resolve/explain collisions          | Reviewed collision report  | —                                             | Sau detection                     |
| 24/09     | M1.8 Draft | Draft OCR rules                     | OCR draft                  | Trong lúc collision script chạy               | Sau M1.4                          |
| 24/09     | M1.8 Draft | Draft artifact namespace            | Folder/namespace draft     | Song song với collision processing            | Sau repo structure rõ             |
| **25/09** | M1.8       | Final OCR calibration checklist     | OCR checklist              | Thanh Audit, Phát Pre-G1                      | Sau draft                         |
| 25/09     | M1.8       | Freeze failure threshold            | Threshold policy           | Song song artifact work                       | Sau OCR tests/check               |
| 25/09     | M1.8       | Freeze canonical artifact structure | Artifact namespace         | —                                             | Sau M1.4/M1.6 hiểu rõ structure   |
| 25/09     | G1         | Trình technical evidence            | Evidence package           | Cả nhóm review                                | Sau M1.4/M1.6/M1.8                |
| **26/09** | Fix        | Resolve G1 technical blockers       | Updated evidence           | Phát/Thanh fix song song                      | Chờ G1 blocker list               |
| 26/09     | Fix        | Update hashes/manifests             | Revised manifests          | Song song các fix khác                        | Theo issue                        |
| 26/09     | Fix        | Rerun collision checks nếu cần      | Final collision report     | —                                             | Nếu G1 yêu cầu                    |
| **27/09** | Freeze     | Final repo/data/hash check          | Technical Sign-off         | Thanh Final QA                                | Sau blocker fix                   |
| 27/09     | Freeze     | Freeze technical evidence           | Technical evidence package | —                                             | Task cuối của Khương              |

---

## Deliverables bắt buộc của Khương

```text
01_repository_audit/
├── repo_inventory.csv
├── data_inventory.csv
├── config_inventory.csv
├── run_inventory.csv
├── git_snapshot.txt
├── hash_manifest.csv
└── gap_log.md
03_collision_audit/
├── page_manifest.csv
├── alias_manifest.csv
├── duplicate_report.csv
└── collision_report.md
05_ocr_artifacts/
├── ocr_checklist.md
├── ocr_failure_threshold.md
├── artifact_namespace.md
└── technical_signoff.md
```

---

# 4. NHIỆM VỤ CHI TIẾT – TẤN PHÁT

## Vai trò

**Research Lead / Protocol & Gate Owner**

Phát chịu trách nhiệm đảm bảo:

* experiment không chạy tùy ý;

* protocol được freeze;

* dataset/split/metric/seed/baseline được quyết định trước;

* G1 được review đúng evidence;

* blocker được theo dõi;

* Sprint 1 có báo cáo hoàn chỉnh.

---

## Timeline Tấn Phát

| Ngày      | Task       | Công việc chi tiết                         | Output                    | Việc song song                   | Queue                     |
| --------- | ---------- | ------------------------------------------ | ------------------------- | -------------------------------- | ------------------------- |
| **23/09** | M1.5       | Chốt research questions                    | Research question section | Khương M1.4, Thanh M1.7          | Queue 1                   |
| 23/09     | M1.5       | Chốt dataset roles                         | Dataset policy            | Song song các phần protocol khác | Queue 1                   |
| 23/09     | M1.5       | Chốt split policy                          | Split policy              | —                                | Sau dataset role          |
| 23/09     | M1.5       | Chốt primary/secondary metrics             | Metric policy             | —                                | Không phụ thuộc technical |
| 23/09     | M1.5       | Chốt seeds                                 | Seed policy               | —                                | Không phụ thuộc           |
| 23/09     | M1.5       | Chốt baseline roster                       | Baseline policy           | —                                | Theo scope research       |
| 23/09     | M1.5       | Chốt QARF/QPAF matching rules              | Comparison rule           | —                                | Theo research design      |
| 23/09     | M1.5       | Chốt candidate policy                      | Candidate policy          | —                                | Theo architecture         |
| 23/09     | M1.5       | Chốt statistical policy                    | Bootstrap/W-T-L policy    | —                                | Không phụ thuộc           |
| 23/09     | M1.5       | Chốt run/change policy                     | Governance policy         | —                                | Không phụ thuộc           |
| **24/09** | M1.5       | Cross-check protocol với repo/data thực tế | Frozen Protocol           | Khương M1.6, Thanh M1.7 Final    | Cần M1.4 input            |
| 24/09     | G1 Prep    | Lập G1 checklist                           | G1 checklist v1           | Thanh registry freeze            | Sau protocol freeze       |
| 24/09     | G1 Prep    | Map requirement → evidence → owner         | Evidence matrix           | Song song                        | Sau protocol freeze       |
| **25/09** | Pre-G1     | Kiểm M1.4–M1.8 evidence                    | Readiness matrix          | Khương/Thanh làm song song       | Cần evidence              |
| 25/09     | M1.9       | Điều phối G1 lần 1                         | G1 Decision v1            | Cả nhóm                          | Chờ đủ evidence           |
| 25/09     | M1.9       | Lập blocker list                           | Blocker log               | —                                | Sau G1 review             |
| 25/09     | M1.10      | Draft Progress Report                      | R1 Draft                  | Sau G1 có thể viết song song     | Cần status/evidence       |
| **26/09** | Fix        | Xử lý protocol blocker                     | Amendment/fixed protocol  | Khương & Thanh fix song song     | Theo G1 issues            |
| 26/09     | M1.10      | Hoàn thiện completed work/evidence/risk    | R1 near-final             | Song song blocker fix            | Có thể làm liên tục       |
| 26/09     | G1 Recheck | Review blocker resolution                  | Provisional Gate Result   | Cả nhóm                          | Chờ critical fix          |
| **27/09** | Final G1   | Nhận Technical Sign-off                    | Evidence                  | Thanh QA song song trước đó      | Chờ Khương                |
| 27/09     | Final G1   | Nhận QA Sign-off                           | Evidence                  | —                                | Chờ Thanh                 |
| 27/09     | M1.9       | Chốt PASS/PARTIAL/BLOCKED/FAIL             | Final G1 Decision         | —                                | Sau 2 sign-off            |
| 27/09     | M1.10      | Finalize Sprint Report                     | Final Progress Report     | —                                | Sau Final G1              |
| 27/09     | Close      | Chốt M1 Closure                            | M1 Closure Record         | —                                | Queue cuối                |

---

## Deliverables bắt buộc của Tấn Phát

```text
02_protocol/
├── frozen_protocol.md
├── dataset_split_policy.md
├── metric_policy.md
├── seed_policy.md
├── baseline_policy.md
├── candidate_policy.md
├── statistical_policy.md
├── run_policy.md
└── protocol_amendments.md
06_G1/
├── G1_checklist.md
├── G1_evidence_matrix.csv
├── G1_blocker_log.md
└── G1_final_decision.md
07_R1/
├── Sprint_1_Progress_Report.md
└── M1_closure_record.md
```

---

# 5. NHIỆM VỤ CHI TIẾT – THANH

## Vai trò

**Experiment Governance / Independent QA**

Thanh chịu trách nhiệm đảm bảo:

* mọi experiment được đăng ký;

* không có run vô danh;

* mỗi kết quả đều trace được về data/config/code;

* experiment type rõ;

* protocol và registry nhất quán;

* G1 có independent review.

---

## Timeline Thanh

| Ngày      | Task         | Công việc chi tiết                   | Output              | Việc song song            | Queue                                  |
| --------- | ------------ | ------------------------------------ | ------------------- | ------------------------- | -------------------------------------- |
| **23/09** | M1.7 Draft   | Thiết kế experiment ID               | Naming draft        | Khương M1.4, Phát M1.5    | Queue 1                                |
| 23/09     | M1.7 Draft   | Thiết kế registry schema             | Registry schema     | Song song                 | Queue 1                                |
| 23/09     | M1.7 Draft   | Thiết kế test classification         | Test types          | Song song                 | Queue 1                                |
| 23/09     | M1.7 Draft   | Append-only rule                     | Governance rule     | Song song                 | Queue 1                                |
| 23/09     | M1.4 Support | Kiểm trace run → config → output     | Audit notes         | Song song schema work     | Dựa trên inventory Khương cung cấp dần |
| **24/09** | M1.7 Final   | Đồng bộ registry với frozen protocol | Registry Final      | Khương M1.6, Phát G1 Prep | Chờ M1.5 Freeze                        |
| 24/09     | M1.7 Final   | Freeze naming rules                  | Naming Rules Final  | Song song                 | Sau protocol                           |
| 24/09     | M1.7 Final   | Freeze test classification           | Test Policy Final   | Song song                 | Sau protocol                           |
| 24/09     | Traceability | Build traceability matrix            | Traceability matrix | Song song                 | Cần registry + inventory               |
| **25/09** | QA           | Audit Experiment ID → Method         | Evidence report     | Khương M1.8, Phát Pre-G1  | Sau M1.7                               |
| 25/09     | QA           | Audit Method → Config                | Evidence report     | Song song                 | Sau M1.7                               |
| 25/09     | QA           | Audit Config → Commit                | Evidence report     | Song song                 | Sau inventory                          |
| 25/09     | QA           | Audit Data → Hash                    | Evidence report     | Song song                 | Sau M1.4                               |
| 25/09     | QA           | Audit Output → Run                   | Evidence report     | Song song                 | Sau inventory                          |
| 25/09     | QA           | Kiểm Registry ↔ Protocol             | Issue list          | Song song                 | Sau M1.5 + M1.7                        |
| 25/09     | G1           | Independent reviewer                 | QA findings         | Cả nhóm                   | Queue 4                                |
| **26/09** | Fix          | Sửa registry metadata                | Updated registry    | Khương/Phát fix song song | Theo G1 blocker                        |
| 26/09     | Fix          | Sửa naming/classification            | Updated governance  | Song song                 | Theo issue                             |
| 26/09     | QA           | Re-audit evidence                    | QA recheck          | Song song                 | Sau fix                                |
| **27/09** | Final QA     | Kiểm registry completeness           | QA Sign-off         | Khương technical freeze   | Queue 7                                |
| 27/09     | Final QA     | Random end-to-end trace experiment   | QA evidence         | Song song                 | Sau all fixes                          |
| 27/09     | Freeze       | Freeze registry                      | Registry Freeze     | —                         | Sau final audit                        |

---

## Deliverables bắt buộc của Thanh

```text
04_experiment_registry/
├── experiment_registry.csv
├── experiment_naming_rules.md
├── test_classification.md
├── append_only_policy.md
├── traceability_matrix.csv
├── evidence_audit.md
├── issue_log.csv
└── qa_signoff.md
```

---

# 6. CÁC TASK ĐƯỢC PHÉP LÀM SONG SONG

| Nhóm song song                        | Công việc                                                              |
| ------------------------------------- | ---------------------------------------------------------------------- |
| **Parallel Block 1 – 23/09**          | Khương M1.4 + Phát M1.5 + Thanh M1.7 Draft                             |
| **Parallel Block 2 – 24/09**          | Khương M1.6 + Phát Final M1.5/G1 Prep + Thanh Final M1.7               |
| **Parallel Block 3 – 25/09 trước G1** | Khương M1.8 + Phát Pre-G1 + Thanh Independent Audit                    |
| **Parallel Block 4 – 26/09**          | Khương Technical Fix + Phát Protocol/Report Fix + Thanh Governance Fix |
| **Parallel Block 5 – 27/09 đầu ngày** | Khương Technical Freeze + Thanh Final QA                               |

---

# 7. CÁC TASK BẮT BUỘC THEO QUEUE

| Queue   | Điều kiện trước                | Task tiếp theo                |
| ------- | ------------------------------ | ----------------------------- |
| **Q1**  | Không cần điều kiện            | M1.4, M1.5 Draft, M1.7 Draft  |
| **Q2**  | M1.4 có inventory              | M1.6 Collision Audit          |
| **Q3**  | M1.5 frozen                    | M1.7 Final/Freeze             |
| **Q4**  | M1.4–M1.7 đủ evidence          | M1.8 Final + Pre-G1           |
| **Q5**  | M1.4–M1.8 đủ review            | G1 lần 1                      |
| **Q6**  | Có G1 blocker list             | 3 người sửa blocker song song |
| **Q7**  | Critical blocker resolved      | G1 Recheck                    |
| **Q8**  | Technical Freeze + QA Sign-off | Final G1                      |
| **Q9**  | Final G1 Decision              | Final R1 Report               |
| **Q10** | Final report hoàn tất          | Close M1                      |

---

# 8. CRITICAL PATH

```text
M1.4 Repository Audit
       ↓
M1.6 Collision Audit
       ↓
M1.8 OCR/Artifact
       ┐
       │
       ├────────→ G1 First Review
       │              ↓
M1.5 Protocol         Blocker Fix
       ↓              ↓
M1.7 Registry ────────┘
                      ↓
                 G1 Recheck
                      ↓
           Technical + QA Freeze
                      ↓
                 FINAL G1
                      ↓
                 FINAL R1
                      ↓
                   M1 CLOSED
```

---

# 9. CHECKPOINT CUỐI MỖI NGÀY

| Ngày      | Điều kiện bắt buộc trước khi kết thúc ngày                                       |
| --------- | -------------------------------------------------------------------------------- |
| **23/09** | M1.4 ≥95% hoặc Done; Protocol Draft gần Freeze; Registry Draft hoàn chỉnh        |
| **24/09** | M1.4 Done; M1.5 Frozen; M1.6 hoàn thành hoặc chỉ còn minor review; M1.7 Frozen   |
| **25/09** | M1.4–M1.8 hoàn thành; G1 lần 1 chạy xong; blocker list có owner rõ               |
| **26/09** | Critical blockers được xử lý; G1 recheck đạt mức có thể final; R1 gần hoàn chỉnh |
| **27/09** | Technical Sign-off + QA Sign-off + Final G1 + Final R1 + M1 Closed               |

---

# 10. QUY TẮC LÀM VIỆC TRONG 5 NGÀY

1. **Không chờ người khác nếu task của mình chưa bị dependency chặn.**

2. Khi đang chờ script chạy, hash chạy, collision scan chạy:

   * chuyển sang documentation;

   * chuẩn bị task kế tiếp;

   * hỗ trợ review.

3. Không báo tiến độ kiểu:

   * “được 70%”

   * “gần xong”.

   Phải báo bằng artifact:

   ```text
   repo_inventory.csv       DONE
   hash_manifest.csv        DONE
   collision_report.md      IN PROGRESS
   ocr_checklist.md         BLOCKED
   Reason: ...
   ```

4. Nếu một issue làm block người khác trên critical path:

   * ưu tiên xử lý ngay;

   * không để sang cuối ngày.

5. Ngày 26–27:

   * không mở experiment mới;

   * không đổi architecture;

   * không thêm feature;

   * không mở benchmark mới.

6. Mọi thay đổi sau Protocol Freeze phải được ghi:

   * nội dung thay đổi;

   * lý do;

   * ngày;

   * người approve.

---

# 11. CẤU TRÚC BÀN GIAO CUỐI CÙNG

```text
M1_FINAL/
│
├── 01_repository_audit/
│
├── 02_protocol/
│
├── 03_collision_audit/
│
├── 04_experiment_registry/
│
├── 05_ocr_artifacts/
│
├── 06_G1/
│
└── 07_R1/
```

## Definition of Done toàn Milestone

M1 chỉ được coi là hoàn thành khi:

* M1.4 Repository Audit hoàn thành.

* M1.5 Protocol đã freeze.

* M1.6 không còn unresolved collision nghiêm trọng.

* M1.7 Registry đã freeze.

* M1.8 OCR/artifact policy hoàn chỉnh.

* G1 đã có quyết định chính thức.

* Critical blocker đã được xử lý hoặc documented rõ.

* R1 Progress Report hoàn thành.

* Technical evidence và experiment evidence có thể trace end-to-end.

**Target cuối ngày 27/09:**

> **M1 CLOSED → READY FOR M2 FROM 28/09.**
