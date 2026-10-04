# M1.5 protocol — imported historical freeze

**Owner:** Tấn Phát

**NEW-repository status:** `ADOPTION_CANDIDATE_PREPARED_REVIEW_BLOCKED`

**Execution:** `CLOSED`

Thư mục này chứa bản sao byte-identical của package `QPAF-M1.5-v1` từ OLD
repository. Chín file Markdown khớp
[`protocol_freeze_manifest.json`](protocol_freeze_manifest.json), và manifest
vẫn ghi đúng nguồn cũ: branch `chore/repository-hygiene`, HEAD `20cb3bf...`,
dirty worktree, chưa có freeze commit và chưa có independent reviewer sign-off.

Việc import bảo toàn provenance; nó **không tự động biến protocol cũ thành
protocol được NEW repository phê duyệt**. Xem
[`sync_reconciliation.md`](sync_reconciliation.md) để biết path mapping, khác
biệt với method core đã tích hợp trong `develop`, dependency còn thiếu và điều kiện tạo
một successor protocol có hiệu lực trong repo này.

Ngày 28/09, A001/A002 được ghi đè vào `protocol_amendments.md` và làm sai hash
của historical manifest. Bản historical ledger đã được phục hồi đúng byte từ
commit import `c82dd5a`; hai amendment được giữ nguyên trong
[`amendments_after_import.md`](amendments_after_import.md). Xem
[`adoption_readiness.md`](adoption_readiness.md) và
[`protocol_adoption_candidate.json`](protocol_adoption_candidate.json) để biết
NEW-relative references và các identity còn thiếu. Research Lead approval của
A001/A002 không thay thế independent review hoặc active adoption.

Các file policy được bảo toàn nguyên byte nên một số liên kết sang M1.7 vẫn
phản ánh OLD package. M1.7 Draft đã được reconcile trong NEW repository nhưng
M1.7 Final, exact split/data evidence, independent sign-off và G1 vẫn chưa có.
Không có result-bearing execution nào được mở bởi gói chuẩn bị này.
