# Phát: branch nghiên cứu Jev đã có code

**Đã có toolkit runnable và lệnh khởi động.** Branch `research/jev-phat-data-infra` tích hợp shared implementation `796410160ee90bbe2a86b6799a76976f958f576f`. Kết quả mô hình 4B trên dữ liệu đồ án còn chờ chạy.

```bash
git clone --branch research/jev-phat-data-infra --single-branch https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git
cd qpaf-visual-document-retrieval
python scripts/run_jev_phat.py
```

Python >=3.11 chạy demo offline, không cần thư viện model. Output mặc định ở common task `evidence/runs/phat/`, có nhãn synthetic. Đây là kiểm tra setup; số demo không dùng kết luận chất lượng Jev.

[Hướng dẫn dùng dữ liệu thật, model và GPU](../jev-runnable-team-kit-20261120/README.md) có lệnh prepare/score/evaluate/compare/export-train/train, pin môi trường và ví dụ local/Modal. Dùng input riêng và môi trường model riêng theo runbook; `--execute` mới chạy training/cloud.

## Phần việc tiếp theo của Phát

- Khôi phục OCR/query/page/document mapping và raw channel/reranker cache riêng; lập inventory có/còn thiếu.
- Cùng nhóm khóa split/group/cohort/top-20 và input policy; tạo pairs/score manifests cùng hash, kiểm tra coverage.
- Chuẩn bị môi trường và Volume riêng cho job đồng thời; ghi GPU/token/time/cost, điều phối frozen và training pilot.
- Tích hợp outputs chung của Thanh/Khương; giữ raw pairs, revisions và log để tái lập.

Đọc [spec](superpowers/spec.md), [plan](superpowers/plan.md), [workflow](evidence/workflow.md), [kiểm chứng](evidence/validation.json) và [hash](evidence/hashes.json). Bootstrap ban đầu được lưu trong evidence; trạng thái cũ không mô tả bản code hiện tại. Source F9, kết quả/receipts đã đóng băng giữ nguyên. [Bằng chứng shared implementation](../jev-runnable-team-kit-20261120/README.md).
