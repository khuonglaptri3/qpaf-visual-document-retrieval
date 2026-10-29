# A005 exploration log

One line per decision or result. Format: date | stage | change or decision | reason | result.

2026-10-29 | S1 | Giữ 2 query validation không có positive (8768, 9437), tính nDCG 0 cho mọi phương pháp; không mở rộng candidate | project môn học, so sánh giữa các phương pháp không bị lệch vì dùng chung pool | —
2026-10-29 | S2 | Authorization sinh bằng scripts/authorize_a005.py (light mode, approval_text của người dùng); chạy probe trên 1.600 query train | project môn học, không amendment | Gate PASS: Spearman -0.997, nDCG@10 tại loss thấp nhất 0.9612 (= max lưới), weights [0.1,0.2,0.7]
