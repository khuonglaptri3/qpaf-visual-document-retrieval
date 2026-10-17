# M2.2 — Báo cáo kết quả

**Ngày:** 2026-10-17

**Kết luận:** PASS kỹ thuật trên mẫu dữ liệu thật, đủ ba retriever.

**Run được chọn:** `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`.

**Revision bàn giao:** [m2.2-001](../../../evidence/revisions/m2.2-001/README.md).

## 1. Công việc đã hoàn thành

Đã triển khai cấu hình riêng, xác minh M2.1, chọn mẫu xác định, chuẩn bị text/ảnh
chung, chạy BM25/BGE-M3/ColQwen2.5, lưu scores/embeddings/cache, kiểm tra parity,
đo tài nguyên và xuất bằng chứng. Tái sử dụng `retrieval.py`, bổ sung ColQwen2.5
và các điểm đo; các ranh giới thực thi M1.1 cũ vẫn được bộ regression kiểm tra.

Mẫu gồm **4 validation queries và 16 pages**, seed 2026, chọn theo hash ID,
không dùng qrels để chọn trang hoặc tính điểm. Xác minh lại raw payloads và
split bundle với `m2.1-002`; không có test query trong mẫu. Cả ba kênh dùng
cùng page IDs/thứ tự, ma trận điểm đều có shape `[4, 16]`.

Chuẩn bị text: 13 trang native; 3 trang qua OCR, gồm 2 trang đạt ngưỡng tạm thời
và 1 trang `NO_TEXT_DETECTED / M23_REVIEW_PENDING`. Trang cuối được giữ nguyên,
text rỗng được ghi rõ; không có lỗi extraction kỹ thuật trong run được chọn.

## 2. Cấu hình đã kiểm chứng

| Thành phần | Cấu hình |
|---|---|
| BM25 | Unicode word/lowercase, k1=1.5, b=0.75 |
| Dense | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`; tokenizer cùng commit; float32; normalized embeddings; max length 8192; batch 2 |
| Visual adapter/processor/tokenizer | `vidore/colqwen2.5-v0.2@dcbe8d9cede518bce830488364ba0e40c873645b` |
| Visual base | `vidore/colqwen2.5-base@92908120384b7a2110c5beda3ab29cbdb2c08e49` |
| Visual inference | **float32**, SDPA; page/query batch 2; score batch 4; 200704 pixels, tối đa 256 visual tokens |
| Processor | Snapshot local đúng commit, `use_fast=False`, `Query: ` và 10 augmentation tokens |
| Môi trường | Python 3.11.12, PyTorch 2.7.1, transformers 4.53.3, colpali-engine 0.3.12; Linux; NVIDIA A10, CUDA 12.6 |
| Trọng số | Frozen; chỉ inference |

[Config đầy đủ](../../../configs/m2.2/retriever_smoke.toml),
[resolved config của run](../../../results/m2.2/RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01/resolved_config.json).
Model-file SHA-256, environment và source hashes nằm trong run/revision.
Git base commit là `51087eee5e00ad53572cae2b7b2da141ce4dd082`; code chưa commit
được nhận diện bằng `source.json` và `source_snapshot.zip`, không coi base commit
là đã chứa các thay đổi M2.2.

## 3. Tính đúng và parity

| Kênh | Kiểm tra chính | Sai lệch tuyệt đối lớn nhất | Kết quả |
|---|---|---:|---|
| BM25 | Công thức tham chiếu độc lập trên cùng corpus mẫu | 0 | PASS |
| BGE-M3 | Điểm batch 2 so với reference batch 1 | 1.78814e-7 | PASS |
| BGE-M3 | Query/page embeddings batch-reference | 1.17347e-7 / 2.96161e-7 | PASS |
| ColQwen2.5 | Điểm batch 2 so với reference batch 1 | 8.39233e-5 | PASS |
| ColQwen2.5 | Query/page token embeddings batch-reference, bỏ zero padding | 1.95384e-5 / 0.00109602 | PASS |
| ColQwen2.5 | MaxSim tham chiếu float32 độc lập từ embeddings đã lưu | 1.90735e-6 | PASS |
| Cả ba | IDs/shape/finite; lưu/đọc score cache; ranking reload | Score reload sai lệch 0 | PASS |

Dung sai được đặt trước lần chạy model đầu tiên: BM25 atol 1e-12;
dense atol/rtol 1e-5; visual score atol 0.25, rtol 0.005; visual embedding
atol 0.02, rtol 0.05. Chuyển float32 không thay hoặc nới dung sai.

## 4. Tài nguyên đo được

Đơn vị bộ nhớ là MiB. Tổng stage bao gồm load, kiểm tra, cache và reference;
không gồm thời gian image build, cấp phát container hay tải artifact về máy.

| Kênh | Tổng stage (s) | Peak process RSS | Peak reserved VRAM | Kết quả caps |
|---|---:|---:|---:|---|
| BM25 | 0.182 | 3378.74 | 0 | PASS |
| BGE-M3 | 15.636 | 7392.95 | 2268 | PASS |
| ColQwen2.5 float32 | 31.188 | 11833.14 | 14978 | PASS |

| Kênh | Model load (s) | Query encoding (s) | Page encoding (s) | Scoring (s) |
|---|---:|---:|---:|---:|
| BM25 | — | — | — | 0.002860 |
| BGE-M3 | 4.160 | 0.358 | 0.205 | 0.000072 |
| ColQwen2.5 | 4.359 | 0.255 | 7.268 | 0.002923 |

Visual processor load: 0.634 s. Model resolution/download + file hashing:
dense 3.104 s, visual 11.301 s; model cache đã tồn tại từ các lượt trước, nên
các số này không đại diện cold download. Số đo RSS bao gồm framework của worker;
không phải bộ nhớ tối thiểu riêng thuật toán BM25. RSS lấy mẫu mỗi 20 ms,
không cộng subprocess OCR; VRAM là PyTorch reserved, không phải toàn bộ driver.

Caps: 1800 s/stage, 32768 MiB process RSS, 22528 MiB reserved VRAM,
512 MiB artifacts; input payload tối đa 64 MiB; không automatic retries.
Model cache ở ngoài thư mục run và không tính vào kích thước output artifacts.

## 5. Hiệu chỉnh và các run chưa đạt

Giữ nguyên các run và nhật ký lỗi tại `results/m2.2/`:

| Run suffix | Kết quả | Nguyên nhân / xử lý |
|---|---|---|
| `20261017T035945Z-A01` | FAIL trước inference | CPU/GPU đăng ký cùng function name; đã tách tên |
| `20261017T040322Z-A01` | FAIL prepare | OCR không có từ trên một trang ảnh; bổ sung trạng thái no-text rõ ràng và giữ trang |
| `20261017T040629Z-A01` | BM25/dense PASS; visual FAIL | Processor chat-template không tương thích; load từ pinned local snapshot |
| `20261017T041005Z-A01` | BM25/dense PASS; visual FAIL | bfloat16 đạt score/cache parity nhưng token embeddings lệch tới 0.435547, vượt atol 0.02 |
| `20261017T041244Z-A01` | **PASS đủ ba kênh** | Chọn float32 trong cùng caps, giữ nguyên mẫu và dung sai |

Suffix có cùng prefix `RUN-QPAF-M2_2-SMOKE-001-`.
Bfloat16 chưa được chấp nhận theo tiêu chí này; không dùng run FAIL làm bằng chứng PASS.

## 6. Kiểm thử và xác minh bằng chứng

Regression cuối trong môi trường Modal đã khóa: **164 tests, 163 passed,
1 platform skip, không failures/errors**.
[Biên bản đầy đủ](../../../results/m2.2/verification/tests-2026-10-17T041449.342184_0000.json)
ghi environment, full unittest output, source/test hashes và hash snapshot gửi lên;
source không đổi trong thời gian kiểm thử. Có kiểm thử lỗi mô phỏng OOM/timeout,
ghi evidence khi thất bại, no-text, config/ID/hash mismatch và cache tampering.

Run được xác minh read-only bằng `scripts/run_m22_smoke.py --verify` trước khi
tạo revision bất biến. Run hash manifest:
`feb5b87b8a6252f7a6cc9d5c9525d96d10f51a24e20f7e75319ad714596c59aa`.

## 7. Bàn giao và giới hạn

- [Run report](../../../results/m2.2/RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01/report.md)
- [Revision m2.2-001](../../../evidence/revisions/m2.2-001/README.md)
- [Điểm tra cứu M2_FINAL](../../../evidence/M2_FINAL/02_retriever_calibration/README.md)
- [Runbook và lệnh tái chạy](../../../results/m2.2/README.md)
- [Nhật ký](../progress/2026-10-17-m22-retriever-smoke.md)

Modal Volume: `qpaf-m22-smoke-artifacts`, `runs/<run-id>`; scores, embeddings và
ảnh mẫu giữ ở local/Volume, hashes và báo cáo được quản lý bằng Git.
[Modal app của run được chọn](https://modal.com/apps/tlcn-group1/main/ap-lKwzev8nSGKx7Qxdu9dAOg)
đã dừng sau khi hoàn tất; không có app tiếp tục inference cho công việc này.

Kết quả xác nhận pipeline trên mẫu và cấu hình float32/256 visual tokens đã đo.
Cần xem xét lại tài nguyên/parity khi tăng độ phân giải, batch hoặc thay dtype.
OCR quality còn chờ M2.3; cache toàn corpus thuộc M2.8. Không có huấn luyện learned
model hoặc kết luận chất lượng retrieval toàn corpus. PASS kỹ thuật không thay
thế chữ ký QA độc lập hoặc quyết định Research Lead.

## 8. Chi phí Modal và credit

Bổ sung sau khi người dùng yêu cầu làm rõ chi phí GPU thuê. Đọc trực tiếp bằng
`modal billing report --for today --show-resources --json` và
`modal billing summary --json`, lúc **2026-10-17 04:27:42 UTC**.

| Phạm vi M2.2, trước credit/allowance | USD |
|---|---:|
| GPU A10G | 0.08188917 |
| CPU | 0.06703663 |
| RAM | 0.07498530 |
| Network egress | 0.01964247 |
| **Tổng mọi app smoke và verification M2.2, gồm các lượt lỗi** | **0.24355357** |
| Riêng run PASS được chọn, đã nằm trong tổng trên | 0.06825165 |

Workspace monthly summary tại thời điểm đọc trả `billed_cost=0`, với credits và
network egress allowance được áp dụng. Đây là trạng thái API hiện có, không phải
cam kết hóa đơn cuối kỳ; report và monthly summary có thể cập nhật lệch thời điểm.
Raw receipt giữ local tại `.superpowers/m22-billing-2026-10-17.json` (Git-ignored).
Không đưa thông tin billing toàn workspace vào revision nghiên cứu bất biến.

Các app M2.2 đã `stopped`, `tasks=0`; việc giữ Volume không làm GPU tiếp tục chạy.
Caps RAM/VRAM/sample/timeout trong config là giới hạn vận hành và tiêu chí kiểm tra,
**không phải trần chi tiêu USD của workspace**. Chưa thay đổi workspace budget
hoặc spend limit. Đợt chạy lớn tiếp theo cần dự toán tiền và trần ngân sách cụ thể.

Nguồn: [Modal pricing](https://modal.com/pricing),
[billing và độ trễ số liệu](https://modal.com/docs/guide/billing),
[workspace budgets/spend limits](https://modal.com/docs/guide/budgets).
