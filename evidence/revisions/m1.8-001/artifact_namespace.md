# M1.8 — Canonical Artifact Namespace Specification

**Status:** `ACTIVE — ALIGNED WITH M1.7 EXPERIMENT REGISTRY`
**Owner:** Khương (Data & Technical Owner)
**Reviewed by:** Đồng bộ với `evidence/M1_FINAL/04_experiment_registry/experiment_naming_rules.md` của Thanh
**Updated:** 2026-09-28

---

## 1. Cấu trúc Không gian tên Bất biến (Immutable Layout)

Mọi lần chạy thực nghiệm hợp lệ trong tương lai (sau khi Gate G1 cấp phép) đều bắt buộc tuân thủ cấu trúc lưu trữ:

```text
artifacts/<experiment_id>/<run_id>/
├── metadata.json       # Metadata: Git commit, UTC start/end, hardware, config_hash, split_hash
├── config.json         # Cấu hình TOML/JSON đầy đủ đã resolve
├── command.txt         # Lệnh thực thi chính xác (CLI command)
├── environment.txt     # Python version, pip freeze, OS environment
├── outputs/            # Toàn bộ tệp kết quả (manifests, embeddings, BM25 scores)
├── failures.csv        # Nhật ký chi tiết các mẫu/trang lỗi (fail-closed)
└── hashes.csv          # Mã băm SHA-256 của từng tệp đầu ra trong thư mục
```

---

## 2. Quy tắc Đặt tên Run ID

Run ID tuân theo cú pháp nghiêm ngặt của M1.7:

```text
RUN-<experiment_id>-<YYYYMMDDTHHMMSSZ>-A<NN>
```

- `<experiment_id>`: Theo đăng ký registry, ví dụ `QPAF-M1_8-OCR-001`, `QPAF-M2_3-CAL-001`.
- `<YYYYMMDDTHHMMSSZ>`: Dấu thời gian bắt đầu theo chuẩn UTC (ví dụ `20260928T164500Z`).
- `A<NN>`: Số thứ tự lần thực thi được cấp phép (`A01` cho lần đầu; `A02` cho lần thử lại và phải có `retry_of`).

---

## 3. Nguyên tắc Create-Once & Chuỗi Thẩm định

1. **Bảo vệ Create-Once:** Thư mục `artifacts/<experiment_id>/<run_id>/` chỉ được tạo mới một lần. Nếu thư mục đã tồn tại trên ổ đĩa, chương trình lập tức ném ngoại lệ `FileExistsError` và từ chối ghi đè.
2. **Chuỗi thẩm định nguồn gốc (Review Chain):**
   $$	ext{Run} \longrightarrow 	ext{Config} \longrightarrow 	ext{Commit} \longrightarrow 	ext{Data} \longrightarrow 	ext{Hash} \longrightarrow 	ext{Output}$$
