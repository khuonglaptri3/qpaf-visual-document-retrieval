# M1.9 G1 package

**Owner:** Tấn Phát; **review:** cả nhóm

**Preparation:** `REFRESHED_2026_09_28_POST_MERGE`

**Pre-G1 readiness:** `BLOCKED_FOR_G1_FIRST_REVIEW`

**Official G1 decision:** `NOT_RUN`

Current internal preparation (28/09):

- [`G1_checklist_2026-09-28.md`](G1_checklist_2026-09-28.md): điều kiện review và Final G1;
- [`G1_evidence_matrix_2026-09-28.csv`](G1_evidence_matrix_2026-09-28.csv): 36 requirement được map
  tới evidence, owner và trạng thái hiện tại;
- [`G1_pre_review_2026-09-28.md`](G1_pre_review_2026-09-28.md): internal readiness assessment trên
  NEW repository;
- [`G1_readiness_matrix_2026-09-28.csv`](G1_readiness_matrix_2026-09-28.csv): finding và closure
  evidence cần có.

The unsuffixed four files remain the byte-stable 27/09 preparation snapshot
referenced by Thanh's append-only M1.7 trace rows. They do not describe the
current post-merge evidence; the dated files above supersede them for internal
readiness review. Neither set is an official G1 decision.

`G1_blocker_log.md`, `G1_first_review_decision.md` và
`G1_final_decision.md` **chưa được tạo có chủ ý**. First Review Decision v1 và
Final G1 Decision là hai gate khác nhau.
Các finding Pre-G1 chỉ là blocker candidates; chúng không trở thành official
blocker hoặc gate decision trước khi cả nhóm review evidence. Snapshot mới nhất
được kiểm là `origin/develop` `2e74b97` ngày 28/09: M1.4 `m1.4-003` còn
`PARTIAL` và zero data; M1.5 có A001/A002 được Research Lead approve nhưng
successor chưa adopt; M1.6 `m1.6-001` có output nhưng hash/source/scope chưa
verify; M1.7 là Draft reconciled; M1.8 `m1.8-001` hash-valid nhưng threshold
`PROVISIONAL`. Technical Sign-off là `NOT SIGNED`, Final QA Sign-off chưa có.

Pre-G1 documents trong thư mục này là internal source review; chưa chọn một
immutable G1 review package và chưa có independent acceptance của cả nhóm.

Package này không mở execution và không chứng minh M1/G1 PASS.
