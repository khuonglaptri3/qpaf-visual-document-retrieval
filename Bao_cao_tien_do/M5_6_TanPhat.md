# M5.6 / R6 — Báo cáo ablation (Tấn Phát)

**Phạm vi:** chỉ validation (171 query), seed `20260820`, CPU local, một lần chạy.
Không mở test, không đổi QPAF-v1, baseline, checkpoint đã freeze hay seed.
Chi tiết và hash: [evidence/revisions/m5.6-001/README.md](../evidence/revisions/m5.6-001/README.md).

## Kết luận

1. **Bỏ từng nhóm feature phụ không làm thay đổi đáng kể QPAF.** Bỏ rank, gap,
   disagreement hay `query_length` đều cho ΔnDCG@10 trong khoảng ±0.002 so với control
   đủ 13 feature, CI 95% chứa/chạm 0, và ≥163/171 query giữ nguyên kết quả. Trên
   validation này, tín hiệu chính của gate nằm ở ba score đã chuẩn hoá; các nhóm phụ
   gần như dư thừa.
2. **Điều kiện hoá theo trang (page-level) là yếu tố tạo khác biệt.** QPAF − QARF
   = +0.1187 nDCG@10 (trung bình 3 seed theo query, CI [+0.0819, +0.1566],
   W/T/L 61/97/13), ổn định ở cả ba seed (+0.114 / +0.125 / +0.117).
3. **Tính toàn vẹn:** control tái tạo pilot M3.4 chính xác (sai khác 0.0); reload
   checkpoint trong process mới sai khác 0.0; trọng số của feature bị bỏ không đổi.

## Giới hạn

- Khám phá, không xác nhận: thứ tự ablation chốt sau khi đã thấy validation; epoch
  được chọn trên chính validation nên giá trị tuyệt đối lạc quan.
- Một seed cho R6-01..04 (đúng preregistration); không suy ra độ ổn định qua seed.
- Lệch D1 (bản chép authorization trong run bị chuẩn hoá xuống dòng) đã ghi rõ, không
  ảnh hưởng số liệu; cần reviewer chấp nhận.

## Bàn giao

Thanh review độc lập M5.6 (post-run check + D1). Kết quả R6 không được dùng để chọn
method/checkpoint cho R7 (TEST-172).
