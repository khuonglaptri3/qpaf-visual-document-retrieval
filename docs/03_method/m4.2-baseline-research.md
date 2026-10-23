# M4.2 — Nghiên cứu nguồn và baseline preparation của Khương

Ngày tra cứu: 23/10/2026. Nhánh: `feature/m4-2-baseline-freeze`.
Base: `5bbb2ded966ac53328109358420c9bc9f731eb58` (đã merge PR #33).

**Kết luận:** đã chuẩn bị thiết lập và phần mềm baseline theo seal M4.1;
đầu vào ViMDoc thật và fit thực tế vẫn **BLOCKED**, chưa nghiệm thu M4.2.
PASS của verifier chỉ xác nhận hash, ID và fixture phần mềm.

## 1. Căn cứ dự án

- [PR #33](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/pull/33)
  và `evidence/revisions/m4.1-001/manifest.json`: ViMDoc document-level,
  1.600 train / 400 validation / 8.904 confirmation, confirmation access closed.
- Workbook `docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx`,
  sheet Milestones, hàng 49: M4.2 do Khương phụ trách, shared baseline bundle
  với static/RRF train-only audited settings.
- `evidence/M1_FINAL/02_protocol/baseline_policy.md`: đủ bảy deployable baseline,
  fitted component chỉ dùng train; strongest chọn bằng validation, giữ mọi
  co-strongest trong 1e-12; oracle chỉ là context.
- `candidate_policy.md`: BM25/BGE-M3/ColQwen2.5, top-200 mỗi kênh, union <=600,
  rescore đủ ba kênh, min-max theo query/kênh; range <=1e-15 thành 0.
- `configs/m2.5/freeze.json` và `src/qpaf/m25/baselines.py`: grid simplex 66 bộ
  trọng số bước 0.1, RRF k=60, tie theo thứ tự từ điển. Đây là nguồn của grid,
  **không phải** một thông số do paper RRF quy định.

## 2. Tra cứu nguồn gốc trên internet và cách áp dụng

| Nguồn đã đọc | Nội dung có căn cứ | Áp dụng và giới hạn |
|---|---|---|
| [Cormack, Clarke, Büttcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), DOI [10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114) | RRF cộng nghịch đảo k+rank; tác giả giữ k=60 sau pilot. | Dùng ranks bắt đầu 1, k=60 như protocol. Không khẳng định 60 tối ưu trên ViMDoc; không tune bằng confirmation. |
| [Bruch, Gai, Ingber, 2023, An Analysis of Fusion Functions for Hybrid Retrieval](https://arxiv.org/abs/2210.11934v2) | Phân tích convex combination và RRF; tham số fusion cần được kiểm soát, kết quả phụ thuộc thiết lập. | Giữ cả static weighted fusion và RRF trong roster. Kết quả bài báo về hai kênh không chứng minh bộ ba trọng số tốt nhất của dự án. |
| [scikit-learn: Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage) | Tách split trước fitting; không học preprocessing/model từ test. | Fit trọng số chỉ với đúng train IDs; qrels riêng; từ chối extra validation/confirmation query. Min-max từng query trên candidate union là phép biến đổi label-free, không fit scaler toàn bộ corpus. |
| [Elastic: Linear retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/linear-retriever) | Có weighted sum của điểm đã chuẩn hóa, gồm min-max. | Căn cứ kỹ thuật cho normalized CombSUM/static fusion; epsilon, 66-grid và tie rule lấy từ protocol dự án. |
| [Elastic: Reciprocal rank fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) | Công thức RRF và rank bắt đầu 1; default rank constant 60. | Kiểm chứng công thức độc lập. Scope rank của package vẫn theo M2.5: toàn bộ common union đã rescore, không âm thầm chuyển sang top-list-only. |
| [HEAVEN official utils.py @ 3eea5ca](https://github.com/juyeonnn/HEAVEN/blob/3eea5ca61f492d3fa18594d455ee10024932f851/retrieval/heaven/utils.py#L29-L40), [max aggregation](https://github.com/juyeonnn/HEAVEN/blob/3eea5ca61f492d3fa18594d455ee10024932f851/retrieval/heaven/utils.py#L266-L291) | Bỏ segment cuối sau underscore để ra document; lấy max điểm trang của document. | Fuse page trước rồi max lên document theo M4.1. nDCG@10 và tie document ID là yêu cầu dự án, không gán cho evaluator HEAVEN vốn báo MRR/Recall. |

Không nguồn nào ở trên cung cấp cache BM25/BGE-M3/ColQwen2.5 ViMDoc của dự án,
trọng số fit thật, hoặc cho phép suy ra QPAF đã thắng baseline.

## 3. Kết quả triển khai

- `configs/m4.2/freeze.json`: bảy baseline, common input contract, exact train-only
  settings, document objective và danh sách real input hashes còn thiếu.
- `src/qpaf/m42/baselines.py`: sáu baseline không cần learned checkpoint,
  document max aggregation/nDCG@10, static fit 66-grid và kiểm tra train-only.
- `scripts/freeze_m42_baselines.py`: kiểm manifest M4.1 bằng SHA-256 pin từ PR,
  tám policy hashes, G2, exact split bytes và inventory source/config/test.
- `tests/test_m42_baselines.py`, `tests/test_m42_freeze.py`: fixture tính tay,
  từ chối leakage/hash drift/overwrite và kiểm replay chỉ đọc.

Review độc lập đã phát hiện và được sửa bằng test tái hiện trước khi sửa:
qrels dạng chuỗi/set/dict phải bị từ chối; toàn bộ config preparation được
pin hash để không seal thiết lập thiếu/mâu thuẫn; fixture phải kiểm đúng bytes
implementation được ghi trong manifest, kể cả khi CLI nhận `--root` khác.

RRF giữ k cố định, không có bước fit nhãn. Static fitting cần train qrels;
validation chỉ dành cho strongest-baseline selection ở M4.4.
Learned QARF vẫn là baseline thứ bảy bắt buộc; package không giả checkpoint.
Grid kế thừa M2.5 được ghi thành preparation cho ViMDoc, chưa tự ký adoption.
Không sửa config/evidence M1–M4.1 và không áp amendment expansion ViDoSeek cho ViMDoc.

## 4. Bằng chứng thật và phần chưa có

Đã replay được exact ID files và tám policy hashes của M4.1. Verifier không đọc
Parquet query text/doc_ids, không tải dữ liệu, không truy cập Modal/GPU.

`artifacts/score_input_probe_vimdoc.json` là receipt lịch sử, ghi chưa bắt đầu
score extraction. Nó **không** chứng minh trạng thái remote hiện tại. Trong
checkout được bàn giao chưa có bundle ViMDoc verified để đóng băng các hash:

- raw/normalized scores, candidate table và channel top lists;
- development document qrels, OCR manifest và page-identity/content audit;
- coverage report và retriever runtime parity;
- learned QARF checkpoint ViMDoc theo seed.

Vì vậy real fitted weights, strongest baseline, acceptance đều để null/PENDING;
real-input readiness là BLOCKED. Candidate coverage phải >=0.95 và không query
nào thiếu positive theo policy; chưa có dữ liệu để đo nên không ghi PASS.
Đây là điều kiện nghiệm thu còn thiếu, không phải kết quả khoa học âm.

## 5. Lệnh kiểm chứng

```powershell
python -m unittest tests.test_m42_baselines tests.test_m42_freeze -v
python scripts/freeze_m42_baselines.py --output-dir evidence/revisions/m4.2-001 --verify
```

Tạo revision mới bằng cùng lệnh bỏ `--verify`; thư mục đích phải chưa tồn tại.
Verifier thành công vẫn báo `real-input readiness: BLOCKED; confirmation closed`.
Không có launcher chạy thật trong CLI này. Kết quả test suite và các lỗi nền
được ghi trong `Bao_cao_tien_do/M4_2_Khuong.md` sau khi chạy kiểm chứng.
