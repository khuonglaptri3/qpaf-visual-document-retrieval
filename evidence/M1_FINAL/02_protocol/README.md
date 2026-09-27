# M1.5 protocol — imported historical freeze

**Owner:** Tấn Phát

**NEW-repository status:** `IMPORTED_HISTORICAL_FREEZE_PENDING_ADOPTION`

**Execution:** `CLOSED`

Thư mục này chứa bản sao byte-identical của package `QPAF-M1.5-v1` từ OLD
repository. Chín file Markdown vẫn khớp
[`protocol_freeze_manifest.json`](protocol_freeze_manifest.json), và manifest
vẫn ghi đúng nguồn cũ: branch `chore/repository-hygiene`, HEAD `20cb3bf...`,
dirty worktree, chưa có freeze commit và chưa có independent reviewer sign-off.

Việc import bảo toàn provenance; nó **không tự động biến protocol cũ thành
protocol được NEW repository phê duyệt**. Xem
[`sync_reconciliation.md`](sync_reconciliation.md) để biết path mapping, khác
biệt với method core đã tích hợp trong `develop`, dependency còn thiếu và điều kiện tạo
một successor protocol có hiệu lực trong repo này.

Các file policy được bảo toàn nguyên byte nên một số liên kết sang M1.7 trỏ đến
artifact Draft của OLD repository chưa tồn tại trong NEW repository. Không sửa
những file đã hash để che dependency này. M1.7 Final, exact split/data evidence,
independent review và G1 vẫn còn thiếu; không có result-bearing execution nào
được mở bởi lần đồng bộ này.
