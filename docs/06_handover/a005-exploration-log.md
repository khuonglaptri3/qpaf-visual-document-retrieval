# A005 exploration log

One line per decision or result. Format: date | stage | change or decision | reason | result.

2026-10-29 | S1 | Giữ 2 query validation không có positive (8768, 9437), tính nDCG 0 cho mọi phương pháp; không mở rộng candidate | project môn học, so sánh giữa các phương pháp không bị lệch vì dùng chung pool | —
2026-10-29 | S2 | Authorization sinh bằng scripts/authorize_a005.py (light mode, approval_text của người dùng); chạy probe trên 1.600 query train | project môn học, không amendment | Gate PASS: Spearman -0.997, nDCG@10 tại loss thấp nhất 0.9612 (= max lưới), weights [0.1,0.2,0.7]
2026-10-29 | S3 | Authorization Stage 3 sinh bằng authorize_a005.py; chạy 6 baseline trên validation | project môn học | train_fitted_static 0.9569 > colqwen25 0.9506 > uniform_combsum 0.9375 > rrf_k60 0.9231 > bm25 0.8769 > bge_m3 0.8678; weights [0.1,0.2,0.7]; co-strongest = [train_fitted_static]
2026-10-29 | S4 | 6 run (QARF-SA x3 rồi QPAF-SA x3), authorization riêng mỗi run, checkpoint 2.7 KB force-add dù *.pt bị ignore | nhỏ, giúp replay/Stage 5 | QARF-SA gain +0.0035..+0.0041, QPAF-SA gain +0.0051..+0.0055 trên train_fitted_static (0.9569); best epoch QPAF 19/16/17; reload diff 0; stop-rule PROCEED
2026-10-29 | S5 | Mở confirmation một lần (8.904 query, hash sealed khớp); không đổi method, seed hay checkpoint | đúng quy trình create-once | 5 query không có positive trong pool, giữ, nDCG 0; static 0.9589, QARF-SA 0.9610, QPAF-SA 0.9608 (trung bình 3 seed)
2026-10-29 | S6 | Thống kê cặp theo query, 10.000 bootstrap | quy tắc verdict A005 | QPAF-SA - static +0.00182 CI95 [+0.00054, +0.00317] -> QPAF_SA_BEATS_BASELINE; QPAF-SA - QARF-SA -0.00023 CI95 [-0.00136, +0.00093] (không khác biệt)
