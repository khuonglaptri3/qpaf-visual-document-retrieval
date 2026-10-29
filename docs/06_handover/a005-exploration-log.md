# A005 exploration log

One line per decision or result. Format: date | stage | change or decision | reason | result.

2026-10-29 | S1 | Giữ 2 query validation không có positive (8768, 9437), tính nDCG 0 cho mọi phương pháp; không mở rộng candidate | project môn học, so sánh giữa các phương pháp không bị lệch vì dùng chung pool | —
2026-10-29 | S2 | Authorization sinh bằng scripts/authorize_a005.py (light mode, approval_text của người dùng); chạy probe trên 1.600 query train | project môn học, không amendment | Gate PASS: Spearman -0.997, nDCG@10 tại loss thấp nhất 0.9612 (= max lưới), weights [0.1,0.2,0.7]
2026-10-29 | S3 | Authorization Stage 3 sinh bằng authorize_a005.py; chạy 6 baseline trên validation | project môn học | train_fitted_static 0.9569 > colqwen25 0.9506 > uniform_combsum 0.9375 > rrf_k60 0.9231 > bm25 0.8769 > bge_m3 0.8678; weights [0.1,0.2,0.7]; co-strongest = [train_fitted_static]
