# M4.2 của Khương — hoàn thành baseline trên dữ liệu chính

Ngày thực hiện: 23/10/2026. Nhánh: `feature/m4-2-baseline-freeze`.
Source commit của lần chạy: `363db3f18252a794c5edd9cec4803e1fecccbf83`.
Run: `RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01`.

**Hoàn thành kỹ thuật deliverable M4.2 trên active primary ViDoSeek:** đã seal
gói đầu vào dùng chung, chạy static fitting trên train thật, khóa thiết lập
của bảy baseline và kiểm replay. `PENDING_USER_REVIEW` trong manifest là
trạng thái nghiệm thu tại thời điểm tạo run; không sửa run đã seal.

## 1. Nhiệm vụ và phạm vi

Workbook Milestones hàng 49 giao Khương đóng băng baseline inputs và train-only
settings, bàn giao shared baseline bundle có kiểm tra static/RRF settings.
Nhận đúng cache/candidates/splits M3, kiểm hash và fairness, fit static trên
train, giữ RRF k=60, rồi bàn giao cho Tấn Phát làm M4.3/M4.4.

Phạm vi theo [A002 đã duyệt](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/amendments_after_import.md)
và [M2.5](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/docs/03_method/m2.5-baselines-statistics-leakage.md).
`m4.2-001` là preparation ViMDoc, giữ nguyên bằng chứng lịch sử; kết quả
active-primary chạy thực tế nằm riêng ở **m4.2-002**. ViMDoc confirmation và
baseline package tương ứng cần execution riêng khi đủ đầu vào.

## 2. Dữ liệu thực tế

- Dataset `Qiuchen-Wang/ViDoSeek`, revision
  `e91a92ba5f38690696c7e66be5c5474b54c6e791`, evaluation theo page.
- Đúng expanded bundle `EXPANSION-001` đã seal ở M3.1/M2.8: **551.764 rows /
  1.142 query**, gồm 2.075 trang bổ sung; tối đa 579 candidates/query, dưới cap 600.
- Split **799 train / 171 validation / 172 test**; train có 386.390 candidate rows.
- Raw/normalized/candidate/top-list hashes khớp byte. Normalization replay lệch
  lớn nhất **0.0**; top-list raw scores đã đối chiếu với common cache.
- Development qrels chứa train và validation được đọc để kiểm role; fitter chỉ
  nhận train IDs/records/qrels. Không tính validation metric để chọn trọng số.
- Test qrels chỉ được hash, **không deserialize và không đưa vào archive**.
  Không truy cập ViMDoc confirmation.

## 3. Kết quả fit thật

| Thông số | Kết quả |
|---|---:|
| Train query | 799 |
| Train candidate rows | 386.390 |
| Grid đã chốt | 66 bộ, bước 0.1 |
| **BM25 / BGE-M3 / ColQwen2.5 weights** | **0.0 / 0.1 / 0.9** |
| **Mean train page nDCG@10** | **0.8642244283102866** |
| Train relevant-page recall | 1.0 |
| Uncovered train queries | 0 |
| Thời gian seal/load/fit | 265,69 giây, CPU local |

Gọi nguyên `qpaf.m25.baselines.fit_static_on_train` và evaluator M2.4. Không đổi
grid/objective/tie rule. Replay độc lập bằng NumPy trên **cùng 66 điểm** chọn
đúng trọng số; objective lệch **3.33e-16**, dưới 1e-12.
[Toàn bộ grid](../results/m4.2/verification/independent-grid-replay/train_grid.csv).

Đây là objective train để chọn tham số của **static baseline**, chưa phải
held-out performance hay kết luận QPAF vượt baseline. BM25 bằng 0 trong static
không xóa BM25 khỏi candidate generation hoặc learned fusion.

## 4. Source và output

| Đường dẫn | Vai trò |
|---|---|
| `src/qpaf/m42/active_primary.py` | Seal inputs, audit common pool, giới hạn train-only, gọi fitter M2.5 và verify |
| `scripts/run_m42_active_primary.py` | CLI chạy/verify active primary |
| `configs/m4.2/active_primary.json` | Dataset revision, source/hash pins, splits và fit settings |
| `src/qpaf/m42/baselines.py`, `scripts/freeze_m42_baselines.py`, `configs/m4.2/freeze.json` | Preparation document-level ViMDoc tương lai, tách khỏi kết quả ViDoSeek |
| `tests/test_m42_active_primary.py`, `tests/test_m42_baselines.py`, `tests/test_m42_freeze.py` | Kiểm leakage, alignment, hashes, overwrite, fitter và aggregation |
| `.gitattributes` | Giữ bytes artifact/run để checksum không đổi sau checkout |
| `docs/03_method/m4.2-active-primary-scope.md` | Căn cứ phạm vi và nguồn áp dụng |

Output thật ở
[`results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/`](../results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/):

- `train_fit.json`: trọng số và objective.
- `shared_inputs.json`: namespace đầu vào chung và checksum.
- `baseline_contracts.json`: bảy baseline cùng shared-input hash: BM25,
  BGE-M3, ColQwen2.5, uniform CombSUM, RRF k60, static và learned QARF.
- `input_audit.json`, `access.json`: coverage, normalization, giới hạn truy cập.
- `manifest.json`, `_SUCCESS.json`: inventory và seal của lần chạy.

QARF dùng lại checkpoint được chấp nhận ở M3.3, seed 20260820, SHA-256
`e44ac1a4f3887700a70914fdba8a3e7b35330244e746253d1cd828508be30914`.
Không train lại retriever hoặc learned model, không chạy GPU/cloud.

Manifest SHA-256:
`4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86`.

## 5. Kiểm chứng và giới hạn

**45/45 test liên quan PASS**, gồm active-primary runner, M2.5, M4.1 và
preparation ViMDoc. Review kỹ thuật phát hiện lỗi provenance khi truyền root
khác executing checkout; đã tái hiện bằng test rồi sửa. Kiểm top-list score
khớp common cache cũng có test tương ứng.

Full suite tại lần chạy lưu bằng chứng: **894 passed, 29 failed, 2 skipped;
310 subtests passed**. Chạy lại đúng 28 failing nodes trên base sạch `5bbb2de`
trong cùng môi trường cho **29 failed, 1 passed**, cùng tập failure. Sáu
failure liên quan PDFium 5.14.0 khác cấu hình cũ 4.30.0; 23 còn lại là
historical hash/environment drift. Không ghi full suite là xanh.
[Log](../results/m4.2/verification/active-primary-full-pytest.txt),
[base comparison](../results/m4.2/verification/active-primary-base-comparison.json).

Lệnh fit ghi đủ outputs và `_SUCCESS.json`, sau đó CLI exit 1 do Windows
charmap không in được tên tiếng Việt. Không chạy lại fit để che lỗi. Hash và
objective đã replay; verifier với `-X utf8` exit 0.
[Execution receipt](../evidence/revisions/m4.2-002/execution_receipt.json).

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m42_active_primary.py --output results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01 --verify --expected-manifest-sha256 4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86
```

## 6. Artifact và người nhận bàn giao

ZIP đầy đủ gồm **24 files / 31.333.271 bytes**, có cả Parquet và checkpoint bị
Git ignore. SHA-256:
`45e764f6bfe081063ea2488dbf5e26ffcaacf2e6f43ea3ad47f56a10c331d2d8`.
`evidence/revisions/m4.2-002/delivery.json` giữ receipt local ban đầu; thông tin
bàn giao GitHub được ghi bổ sung, không sửa receipt cũ.

Xem [runbook bàn giao](../docs/06_handover/m4.2-baseline-handoff.md) để tải,
giải nén và kiểm chứng artifact. Tấn Phát nhận inputs/settings để thực hiện
M4.3/M4.4; Thanh kiểm fairness/uncertainty ở M4.5. Đây là phân công tiếp theo,
chưa phải xác nhận hai người đã nhận hoặc đã review.

Validation strongest-baseline selection, test evaluation và scientific claim
chưa chạy trong M4.2. Kết quả ViDoSeek không đóng nghĩa vụ ViMDoc confirmation.
Giữ nguyên các sign-off lịch sử của M3.1/A003.

## 7. Nguồn đã áp dụng

- [M2.5 freeze](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/configs/m2.5/freeze.json):
  grid, roster, objective, tie rule và RRF settings của dự án.
- [Cormack et al., SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf):
  công thức RRF, k=60 giữ cố định sau pilot trong nghiên cứu gốc.
- [scikit-learn: Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage):
  fitted component chỉ học từ train; dữ liệu đánh giá ngoài fitting.
- [A003 fairness](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A003.md):
  baseline dùng cùng expanded pool với matched learned runs.
- [Ghi chú nghiên cứu ban đầu](../docs/03_method/m4.2-baseline-research.md) giữ
  riêng phần preparation ViMDoc và các nguồn sơ cấp đã đọc.
