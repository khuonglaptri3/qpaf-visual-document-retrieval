# Khương: branch nghiên cứu Jev đã có code

**Đã có toolkit runnable và lệnh khởi động.** Branch `research/jev-khuong-model` tích hợp shared implementation `796410160ee90bbe2a86b6799a76976f958f576f`. Kết quả mô hình 4B trên dữ liệu đồ án còn chờ chạy.

```bash
git clone --branch research/jev-khuong-model --single-branch https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git
cd qpaf-visual-document-retrieval
python scripts/run_jev_khuong.py
```

Python >=3.11 chạy demo offline, không cần thư viện model. Output mặc định ở common task `evidence/runs/khuong/`, có nhãn synthetic. Đây là kiểm tra setup; số demo không dùng kết luận chất lượng Jev.

[Hướng dẫn dùng dữ liệu thật, model và GPU](../jev-runnable-team-kit-20261120/README.md) có lệnh prepare/score/evaluate/compare/export-train/train, pin môi trường và ví dụ local/Modal. Dùng input riêng và môi trường model riêng theo runbook; `--execute` mới chạy training/cloud.

## Phần việc tiếp theo của Khương

- Nhận pairs/split/page-level train labels đã khóa từ Phát; kiểm tra ví dụ query–OCR.
- Chạy Kev-4B frozen trên cùng pairs với BGE/Qwen4B; lưu score/token/time/VRAM thực tế.
- Smoke GPU forward/backward và save/reload; fine-tune LoRA/head từ Kev và cùng kiến trúc từ Qwen3.5-4B-Base với cùng data/loss/budget.
- Chọn checkpoint bằng train/validation, gửi scores cho Thanh; viết ablation frozen/adapted và base/Kev.

Đọc [spec](superpowers/spec.md), [plan](superpowers/plan.md), [workflow](evidence/workflow.md), [kiểm chứng](evidence/validation.json) và [hash](evidence/hashes.json). Bootstrap ban đầu được lưu trong evidence; trạng thái cũ không mô tả bản code hiện tại. Source F9, kết quả/receipts đã đóng băng giữ nguyên. [Bằng chứng shared implementation](../jev-runnable-team-kit-20261120/README.md).
