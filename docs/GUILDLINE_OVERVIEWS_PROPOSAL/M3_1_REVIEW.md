# M3.1 — Kết quả để Khương review

**Kết quả kỹ thuật: PASS. Nghiệm thu của người phụ trách: PENDING_USER_REVIEW.**

- Owner: **Khương**; thực hiện ngày **21/10/2026** theo yêu cầu trong phiên làm việc.
- Nguồn chính thức: [workbook hoàn chỉnh](POAI_Milestone_Group01_Hoan_Chinh.xlsx), sheet `Milestones`, dòng 39.
- Run: `RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01`.
- Commit implementation: `2113b043cbcd56b8a18467dd91f52ef95662dac1`.
- D1 đầu vào: [`m2.11-002`, PASS](../../evidence/revisions/m2.11-002/decision.json).
- [Bộ bằng chứng M3.1](../../evidence/revisions/m3.1-001/README.md) và [hướng dẫn bàn giao](M3_1_HANDOFF.md).

## 1. Công việc đã thực hiện

Đã lấy đúng input binding M2.7-003 và candidate revision M2.8-002 sau A003,
kiểm tra SHA-256, rồi copy nguyên byte sang namespace M3.1 riêng. Hai lần load
records độc lập được replay qua batching và feature builder M2.4/M1.2. Không
thay đổi split, candidate policy, hyperparameter hay các revision M2 cũ.

| Kiểm tra | Kết quả |
| --- | --- |
| Workbook chính thức, task/owner/dependency | PASS — M3.1, Khương, D1 |
| Lineage D1 → M2.7 binding → M2.8 handover | PASS |
| Cache/candidate schema, keys và thứ tự | PASS — 551.764 rows trong cache đầy đủ |
| Split manifests | PASS — 799 train / 171 validation / 172 sealed test |
| Records đi vào pipeline pilot | PASS — 799 train + 171 validation; không dựng test records |
| Rows của train / validation | 386.390 / 82.255 |
| Replay batch train | PASS — 20 epoch, 1.000 batch cho mỗi phương pháp |
| Thứ tự batch so với M2.7-003 | PASS — khớp hash đã chấp nhận |
| Validation | PASS — một lượt cố định, 11 batch |
| 13 features, normalized scores, masks và qrels | PASS — fingerprints của hai phương pháp giống nhau |
| Candidate recall train / validation | 1,0 / 1,0; zero uncovered |
| Test qrels | Chỉ copy/hash bytes; không deserialize |
| Model forward, backward, optimizer | Không thực hiện |
| Read-only replay | PASS — 16 files giữ nguyên, không thêm/xóa/sửa |

Fingerprints bao phủ query IDs, query texts, page IDs/thứ tự, raw scores,
normalized scores, 13 features, padding mask, labels và tổng positive trong qrels.
Các hash theo từng phương pháp/split có trong
[`verification.json`](../../evidence/revisions/m3.1-001/verification.json).

## 2. Nguồn kết quả các task trước

| Task | Kết quả được sử dụng |
| --- | --- |
| M2.1 — Thanh | Split ID manifests và hashes |
| M2.2/M2.3/M2.6 — Khương | Retriever/OCR/page identity được kế thừa qua cache M2.8 |
| M2.8-002 sau A003 | Raw score cache, candidate pool, query texts, qrels và handover |
| M2.4 — Tấn Phát | Dataset/batch pipeline dùng thật trong pilot |
| M2.7-002/003 — Tấn Phát | Shared config, input binding và baseline batch-order evidence |
| M2.10/M2.11 — Thanh | Audit, A003 acceptance và D1 PASS |

Sáu Parquet đã được phục hồi từ ba score matrix gốc và đều khớp byte SHA-256
của M2.8-002. Không chạy lại retrieval, GPU hoặc re-encoding. Xem
[`payload_materialization.json`](../../evidence/revisions/m3.1-001/payload_materialization.json).

## 3. Dọn tài liệu theo nguồn chính thức

Đã loại bỏ **19 tài liệu/workbook cũ** bên ngoài thư mục chính: 10 file ở gốc,
5 file trong `docs/01_overview` và 4 file trong `docs/02_project_plan`.
Mục lục và catalog đã trỏ về `docs/GUILDLINE_OVERVIEWS_PROPOSAL`.

**Năm tài liệu gốc trong thư mục chính giữ nguyên SHA-256**, gồm workbook hoàn
chỉnh, đề xuất, tổng quan, timeline và Word. Các bằng chứng/protocol lịch sử
M1–M2 giữ nguyên. Danh sách file đã loại bỏ và hash trước khi xóa nằm trong
[`documentation_cleanup.json`](../../evidence/revisions/m3.1-001/documentation_cleanup.json).

## 4. Môi trường và kiểm chứng phần mềm

- Python `3.13.7`, Torch `2.11.0+cpu`;
  CPU, float64, 1 tensor thread, deterministic algorithms trong parity replay.
- NumPy `2.5.4`, pandas `3.0.6`,
  PyArrow `26.0.0`.
- Full suite: **375 tests — 373 passed, 2 skipped, 0 errors, 0 failures**.
- Bao gồm **12 regression tests M3.1**, kiểm tra hash/source drift, candidate
  mismatch, label-bearing score schema, qrels/row-order mismatch, actual coverage,
  create-once, external manifest pin và runtime pin.
- Dependency check: PASS. AI static code review không còn issue quan trọng;
  kết quả này không thay thế việc Khương review/nghiệm thu.
- Tạo seal: **73.36 s**. Read-only replay:
  **56.66 s**. Đây là thời gian data audit, không phải latency của model.

[`software_checks.json`](../../evidence/revisions/m3.1-001/software_checks.json),
[`tests.txt`](../../evidence/revisions/m3.1-001/tests.txt),
[`code_review.json`](../../evidence/revisions/m3.1-001/code_review.json).

## 5. Artifact để review và lệnh kiểm lại

Manifest SHA-256 đã chốt:

`0832af156b79d0448ecc630ff572a0053d7cb5da98b4dac2dec1c6ee49e27893`

Payload local ở `results/m3.1/RUN-QPAF-M3_1-SEAL-001-20261021T142631Z-A01/inputs/`; các file lớn không được commit.
Manifest và bằng chứng portable được lưu tại `evidence/revisions/m3.1-001/`.

```powershell
$sealPin = Get-Content evidence/revisions/m3.1-001/seal_pin.json -Raw | ConvertFrom-Json
.venv/Scripts/python.exe scripts/seal_m31_inputs.py `
  --verify $sealPin.run_path `
  --expected-manifest-sha256 $sealPin.manifest_sha256
```

Dùng hash từ hồ sơ đã review/commit. Verify từ chối khi payload, source code,
numerical runtime hoặc manifest bị thay đổi. Verify không ghi lại seal.

## 6. Bàn giao cho các task tiếp theo

| Task | Owner | Sử dụng kết quả này |
| --- | --- | --- |
| M3.2 | Tấn Phát | Chạy learned QARF trên gói đầu vào đã khóa, sau authorization riêng |
| M3.3 | Thanh | Đối chiếu input pin rồi kiểm chứng QARF metrics/provenance và reload |
| M3.4 | Tấn Phát | Dùng lại cùng seal cho QPAF sau accepted QARF review và authorization riêng |
| M3.5 | Thanh | So sánh per-query QPAF−QARF trên cùng dữ liệu |
| M3.6 | Khương | Đối chiếu workload/input khi kiểm tra output integrity và resource |
| M3.7/G2, M3.8/R3 | Tấn Phát | Dùng chuỗi bằng chứng để ra quyết định và báo cáo |

**M3.1 PASS xác nhận đầu vào matched, chưa chứng minh QPAF cải thiện chất lượng.**
Không có learned checkpoint hoặc test ranking metric được tạo. Chưa có human
acceptance M3.1 và chưa cấp phép các run M3.2/M3.4. Workbook nguồn giữ nguyên;
trạng thái thực hiện được ghi ở evidence này để Khương review.
