# M2.2 — Nhật ký thực hiện

**Trạng thái hiện tại:** Hoàn thành implementation và kiểm chứng kỹ thuật M2.2; run thật PASS, revision `m2.2-001` đã bàn giao.

## 2026-10-17 — Khảo sát và quyết định

- Đối chiếu bảng milestone gốc: M2.2 là hiệu chỉnh BM25, BGE-M3 và visual retriever;
  đầu ra gồm smoke test ghim phiên bản, parity checks và resource caps.
- M2.1 được chọn tại `evidence/revisions/m2.1-002/`, trạng thái
  `VERIFIED_ACTIVE_PRIMARY_SPLITS`; counts train/validation/test là 799/171/172.
  Các counts trên là số trong bản ghi M2.1, chưa phải lượt xác minh lại cho một run M2.2.
- Xác định có scorer tái sử dụng tại `src/qpaf/m11/retrieval.py`.
- Import PyTorch local thất bại: `OSError [WinError 126]`, lỗi load
  `torch/lib/shm.dll` hoặc dependency. Chưa chẩn đoán được nguyên nhân.
- Có tạo ba file code/config nháp trong lần khảo sát đầu, sau đó đã gỡ toàn bộ
  theo yêu cầu chỉ phân tích của người dùng. Không có pipeline M2.2 được chạy.
- Người dùng chốt **ColQwen2.5** cho visual retrieval. Repository/revision cụ thể
  và khả năng tương thích với code cũ còn chờ xác minh.

## 2026-10-17 — Kiểm tra Modal

| Lệnh từ gốc repo | Kết quả quan sát |
|---|---|
| `.venv/Scripts/python.exe -m modal --version` | `modal client version: 1.5.5` |
| `.venv/Scripts/python.exe -m modal profile list` | Profile/workspace `tlcn-group1` |
| `.venv/Scripts/python.exe -m modal app list --json` | `[]`, exit code 0 |

Kết luận: kết nối và xác thực Modal API thành công. Danh sách app trả về trống.
Chưa chạy container/GPU, chưa load ColQwen2.5 hoặc BGE-M3. Kết quả này được ghi
lại từ output CLI trong phiên làm việc, không phải log của một run M2.2.

## 2026-10-17 — Chuẩn hóa nơi lưu tài liệu

- Đặt đặc tả tại `docs/superpowers/specs/` và kế hoạch tại `docs/superpowers/plans/`.
- Bổ sung nhật ký tại `docs/superpowers/progress/`, báo cáo tại `docs/superpowers/reports/`.
- Tạo mục lục `docs/superpowers/README.md`, liên kết thứ tự đọc và vị trí artifacts.
- Giữ nguyên tài liệu M1. Chưa tạo runner/config chạy thật hay khởi chạy cloud.

## 2026-10-17 — Triển khai được người dùng yêu cầu

- Người dùng yêu cầu "impliment toàn bộ m2.2 đi", cho phép triển khai và chạy mẫu có kiểm soát.
- Tạo config riêng, chọn mẫu, runner, telemetry, cache/parity checks và xuất evidence.
- Khóa `vidore/colqwen2.5-v0.2@dcbe8d9cede518bce830488364ba0e40c873645b`,
  base `vidore/colqwen2.5-base@92908120384b7a2110c5beda3ab29cbdb2c08e49`.
- BGE-M3 dùng commit `5617a9f61b028005a4858fdac845db406aefb181`.
- Processor/tokenizer cùng revision checkpoint, giữ `Query: ` và 10 augmentation tokens.
- Mẫu ban đầu: 4 validation queries, 16 pages, seed 2026, hash-order selection,
  không dùng qrels. Xác minh lại đầy đủ raw payload/splits với M2.1 trước render.
- Linux environment dùng direct/transitive pins tại `requirements/m22-modal.lock`;
  lock được compile với constraint từ lock M1.1 để giữ tương thích.
- Run `RUN-QPAF-M2_2-SMOKE-001-20261017T035945Z-A01` khởi tạo inputs trên Volume
  thành công nhưng CPU function chưa hydrate do CPU/GPU đăng ký cùng tên `execute`.
  Không có retriever nào chạy; summary ghi FAIL và giữ nguyên run.
- Đã tách `cpu_stage`/`gpu_stage`, bổ sung xác minh hash source package được deploy,
  khởi chạy run mới `RUN-QPAF-M2_2-SMOKE-001-20261017T040322Z-A01`.
- Local M2.2 tests: 13 tests, 12 pass, 1 skip do PyTorch local lỗi import.
- Lượt regression đầu trên Modal: 160 tests, 3 failures do helper gửi source snapshot
  thiếu Git metadata mà các CLI cũ cần; không phải lỗi logic retriever.
  Đã sửa helper tạo synthetic test checkout và chạy lại.

## Bước tiếp theo

M2.2 đã hoàn tất theo [kế hoạch](../plans/2026-10-17-m22-retriever-smoke.md).
Các công việc OCR quality/full corpus/learned training thuộc milestone tiếp theo.

## 2026-10-17 — Hiệu chỉnh từ các run thật

- Run `20261017T040322Z-A01` (cùng prefix `RUN-QPAF-M2_2-SMOKE-001-`) dừng ở
  prepare vì một trang ảnh không có từ OCR. Đã kiểm tra ảnh; giữ trang và bổ sung
  trạng thái `NO_TEXT_DETECTED`, `M23_REVIEW_PENDING`. Không hạ ngưỡng OCR hoặc đổi mẫu.
- Run `20261017T040629Z-A01`: prepare/BM25/dense PASS; visual load được weights
  nhưng processor lỗi chat-template với Transformers 4.53.3.
- Đã chuyển processor sang đọc snapshot local đúng revision, `use_fast=False`;
  không thay checkpoint hoặc nội dung processor. Bổ sung seed Python/NumPy/Torch
  trên worker và tắt TF32; ghi nguồn cùng môi trường chạy.
- Run `20261017T041005Z-A01`: visual hoàn thành cả batch 2 và reference batch 1;
  score parity, MaxSim độc lập và cache PASS, nhưng token-embedding parity FAIL.
  Sai lệch embedding lớn nhất: query 0.0482177734375, page 0.435546875;
  dung sai absolute đã đặt là 0.02. Run tổng thể giữ FAIL.
- Chọn thử float32 cho visual trong cùng resource caps, giữ nguyên toàn bộ dung sai.
  Run mới `20261017T041244Z-A01` liên kết `retry_of` tới run trước.
- Đã cung cấp runner regression có thể tái chạy: `scripts/verify_m22_smoke.py`.
  Biên bản `results/m2.2/verification/tests-2026-10-17T041130.024906_0000.json`
  ghi 164 tests, 163 pass, 1 platform skip, cùng source/test hashes;
  source không đổi trong thời gian test. Cấu hình float32 được kiểm tra lại ở lượt cuối bên dưới.

## 2026-10-17 — Kết quả cuối và bàn giao

- Run chọn: `RUN-QPAF-M2_2-SMOKE-001-20261017T041244Z-A01`, trạng thái **PASS**.
  Prepare, BM25, BGE-M3 và ColQwen2.5 float32 đều đạt kiểm tra cùng mẫu 4 × 16.
- Visual float32: query/page embedding max absolute error 1.95384e-5 / 0.00109602;
  score batch/reference 8.39233e-5; MaxSim độc lập 1.90735e-6. Dung sai không thay đổi.
- Peak reserved VRAM: dense 2268 MiB, visual 14978 MiB, đều dưới cap 22528 MiB.
  Peak process RSS visual 11833.14 MiB, dưới cap 32768 MiB.
- Regression cuối: `scripts/verify_m22_smoke.py` chạy **164 tests, 163 pass,
  1 platform skip**, không failure/error. Receipt:
  `results/m2.2/verification/tests-2026-10-17T041449.342184_0000.json`.
- Xác minh toàn bộ run bằng `scripts/run_m22_smoke.py --verify`; kết quả VERIFIED.
  Hash manifest SHA-256:
  `feb5b87b8a6252f7a6cc9d5c9525d96d10f51a24e20f7e75319ad714596c59aa`.
- Tạo create-once revision `evidence/revisions/m2.2-001/` bằng lệnh `--publish`;
  thêm điểm tra cứu `evidence/M2_FINAL/02_retriever_calibration/README.md`.
- Kết quả bfloat16 FAIL và các run lỗi trước được giữ nguyên. Trang no-text vẫn
  nằm trong mẫu với trạng thái M2.3 review pending; không có thay mẫu để đạt PASS.
- Modal app run chọn `ap-lKwzev8nSGKx7Qxdu9dAOg` và app regression cuối
  `ap-fCHdKSOG33r3TMQdqVNssR` đã dừng, tasks=0. Volume vẫn giữ payloads/model cache.
- Chi tiết số đo, giới hạn kết luận và đường dẫn bằng chứng:
  [báo cáo](../reports/2026-10-17-m22-retriever-smoke.md).

## 2026-10-17 — Đối chiếu chi phí theo yêu cầu người dùng

- Chỉ gọi API/CLI đọc trạng thái và billing; không khởi chạy compute/GPU mới.
- Xác nhận các app M2.2 stopped, tasks=0.
- Billing report cho các app M2.2: 0.24355357 USD trước credits/allowances,
  gồm 0.08188917 GPU, 0.06703663 CPU, 0.07498530 RAM và 0.01964247 network.
- Riêng run PASS được chọn: 0.06825165 USD, đã bao gồm trong tổng.
- Workspace monthly summary hiện trả billed_cost=0; số liệu có thể còn cập nhật.
- Raw receipt local/Git-ignored: `.superpowers/m22-billing-2026-10-17.json`.
- Bổ sung mục chi phí trong báo cáo; ghi rõ resource caps chưa phải trần tiền USD.
  Giữ nguyên evidence revision m2.2-001 và không thay workspace budget.

## 2026-10-17 — Dự trù với giới hạn billing 30 USD

- Người dùng cho biết billing hiện chỉ cho đặt 30 USD; ghi nhận làm giới hạn
  lập kế hoạch, chưa xác minh loại budget/spend limit và không thay thiết lập.
- Đọc số đo đã có và giá công bố; không chạy GPU/benchmark mới.
- Ngoại suy visual khoảng 46.67 phút, compute khoảng 1.202 USD ở preset 256 tokens;
  dự trù vận hành 3–10 USD cho một lượt chuẩn bị/cache toàn ViDoSeek.
- Ghi rõ đây là ước lượng từ mẫu nhỏ, không phải chi phí đo thật hoặc cam kết
  toàn bộ dự án. [Chi tiết dự toán](../plans/2026-10-17-m22-full-corpus-cost-estimate.md).

## Cách ghi các lần thực hiện tiếp theo

Ghi thêm ngày/giờ có timezone, bước kế hoạch, hành động/lệnh, run ID hoặc file liên
quan, kết quả quan sát, lỗi và cách xử lý, cùng việc còn lại. Không ghi token/secret.
Nếu có thông tin sai, ghi mục đính chính để giữ lịch sử.
