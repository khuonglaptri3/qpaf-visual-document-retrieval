# Báo cáo M4.2 của Khương — nghiên cứu nguồn và kết quả thực hiện

Ngày: 23/10/2026. Nhánh: `feature/m4-2-baseline-freeze`.
Base: `5bbb2ded966ac53328109358420c9bc9f731eb58`, đã merge PR #33.

## Kết luận kiểm chứng

**Hoàn thành phần nghiên cứu, phần mềm và preparation audit; chưa đủ điều kiện
nghiệm thu trọn M4.2.** Trạng thái thực tế là
`PREPARED_SETTINGS_REAL_INPUTS_PENDING`, real-input readiness **BLOCKED**.

| Hạng mục | Kết quả thực tế |
|---|---|
| Xác định đúng nhiệm vụ và owner | M4.2, Khương, theo workbook Milestones hàng 49 |
| Tra cứu tài liệu gốc internet | Đã đọc nguồn RRF, convex fusion, train/test leakage, Elastic và HEAVEN |
| Baseline roster và thiết lập preparation | Đủ bảy baseline; sáu reference scorer, learned QARF cần checkpoint thật |
| Document-level scoring/evaluation | Đã triển khai và kiểm bằng fixture tính tay theo M4.1 |
| Static train-only fitting | Đã triển khai 66-grid và guard; chỉ chạy fixture tổng hợp |
| Exact split và policy/hash audit | PASS: 1.600/400/8.904 IDs, không overlap, 27 file bind SHA-256 |
| Test mới M4.2 | 22/22 PASS sau sửa ba lỗi review |
| Test M4.1 + M4.2 | 25/25 PASS |
| Full repository suite | 878 passed, 30 failed, 3 skipped; 303 subtests passed |
| Đối chiếu lỗi trên base sạch | Cùng 29 failing test nodes tái hiện đủ 30 failure trên commit gốc |
| Cache/qrels ViMDoc thật | Chưa có bundle đã xác minh trong checkout bàn giao |
| Real fitted weights / strongest baseline | Chưa tạo; để null/PENDING |
| Nghiệm thu của owner / independent human | PENDING; không tự ký thay người phụ trách |

## 1. Nguồn đã dựa vào

1. [PR #33](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/pull/33)
   và [seal M4.1 tại commit gốc](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/revisions/m4.1-001/manifest.json):
   ViMDoc document-level, exact splits, access gate và các hash còn pending.
2. [Baseline policy](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/baseline_policy.md)
   và [candidate policy](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/candidate_policy.md):
   roster, fairness, shared candidate rows, normalization và train-only.
3. [M2.5 freeze](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/configs/m2.5/freeze.json):
   nguồn cụ thể của grid bước 0.1/66 trọng số, k=60, tie 1e-12. Không tự nghĩ
   thêm search space. Chuyển grid sang ViMDoc dùng objective document đã seal,
   và ghi rõ adoption cho real execution vẫn cần review.
4. [Cormack et al., SIGIR 2009 — bài RRF gốc](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf):
   kiểm tra công thức reciprocal-rank và lựa chọn cố định k trong nghiên cứu gốc.
5. [Bruch et al., An Analysis of Fusion Functions for Hybrid Retrieval, v2](https://arxiv.org/abs/2210.11934v2):
   căn cứ giữ cả static weighted fusion và RRF; không suy kết quả bài báo thành
   ưu thế trên ViMDoc của dự án.
6. [scikit-learn — Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage):
   fitted components chỉ học từ train; không dùng dữ liệu đánh giá để fit.
7. [Elastic — Linear retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/linear-retriever)
   và [RRF](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion):
   đối chiếu weighted sum sau normalization và rank bắt đầu từ 1.
8. [HEAVEN official utils.py, commit 3eea5ca](https://github.com/juyeonnn/HEAVEN/blob/3eea5ca61f492d3fa18594d455ee10024932f851/retrieval/heaven/utils.py):
   đối chiếu page-to-document và max aggregation. Metric nDCG@10/tie rule lấy
   từ M4.1, không gán cho evaluator HEAVEN.

Bảng ánh xạ chi tiết từng quyết định và giới hạn nguồn nằm trong
[`m4.2-baseline-research.md`](../docs/03_method/m4.2-baseline-research.md).

## 2. Những gì đã làm

- [`configs/m4.2/freeze.json`](../configs/m4.2/freeze.json): roster bảy baseline;
  top-200 mỗi kênh/union tối đa 600; rescore đủ ba kênh; min-max epsilon 1e-15;
  static train-only 66-grid; RRF k=60 cố định; mọi real input hash còn thiếu để null.
- [`src/qpaf/m42/baselines.py`](../src/qpaf/m42/baselines.py): document max aggregation,
  binary document nDCG@10 với IDCG dùng toàn bộ positives; scoring không đọc qrels;
  fitting từ chối query thừa/thiếu, duplicate, label column và nonfinite score.
- [`scripts/freeze_m42_baselines.py`](../scripts/freeze_m42_baselines.py): pin chính xác
  config và seal M4.1; replay split/G2/tám policy; bind 27 file bằng SHA-256;
  create-once và verify chỉ đọc. Có thông báo BLOCKED rõ dù kỹ thuật PASS.
- [`evidence/revisions/m4.2-001/`](../evidence/revisions/m4.2-001/): README nguồn,
  manifest và verification JSON tạo từ command thực tế.

Không thay implementation page-level M2.5, không sửa evidence M1–M4.1.
Không lấy ViDoSeek pilot/cache/checkpoint thay cho ViMDoc. Không mở confirmation
labels và chưa có real baseline prediction/metric trong kết quả này.

## 3. Kiểm thử và review

Đã viết test trước implementation và quan sát fail: 12 test baseline, 7 test
freeze. Sau implementation 19/19 PASS. Reviewer độc lập tìm ba lỗi quan trọng;
mỗi lỗi được tái hiện RED rồi sửa GREEN:

1. Qrels dạng scalar string/set/dict có thể bị hiểu sai thành tập ID: đã từ chối.
2. Config thiếu/mâu thuẫn vẫn được seal: đã pin toàn bộ exact configuration v1.
3. `--root` khác có thể hash implementation khác code chạy fixture: đã buộc
   implementation hash khớp code đang thực thi.

Sau sửa: **22 test M4.2 PASS**; thêm 3 test M4.1 thành **25/25 PASS**.
Verifier tạo và replay revision đều trả PASS kỹ thuật, **BLOCKED real input**.
Không có finding Critical hoặc Minor để hoãn lại từ review.

Các lệnh chính:

```powershell
python -m unittest tests.test_m42_baselines tests.test_m42_freeze tests.test_m41_confirmation_seal -q
python scripts/freeze_m42_baselines.py --output-dir evidence/revisions/m4.2-001 --verify
```

Kiểm tra mở rộng trước đó trên Anaconda Python 3.14: 49 passed, 5 failed,
37 subtests passed trong nhóm M4.1/M4.2/ViMDoc preparation. Cả năm failure ở
`tests/test_vimdoc_m3_preparation.py` đều do historical manifest hash drift của
`configs/datasets.yaml`. Đã so sánh byte config, implementation, test và manifest
với `git show` của base: **không đổi**.

Full repository suite trên Python 3.13: **878 passed, 30 failed, 3 skipped,
303 subtests passed**, thời gian 318 giây. Toàn bộ 29 failing test nodes được
chạy lại trong checkout sạch của base `5bbb2de`, cùng interpreter và dependency:
**30 failed, 1 passed**, cùng tập failing nodes. Hai subtest lỗi cùng nằm trong
một test node nên số failure là 30 trong 29 nodes.

Kết quả đối chiếu cho thấy những failure quan sát được cũng tồn tại trên base;
không failure nào thuộc M4.1/M4.2 mới. Không gọi full suite là PASS. Trong đó
**7 failure do môi trường thiếu `huggingface_hub`** (các ca materialization/OCR);
23 failure còn lại liên quan historical source/config/artifact hash và environment
drift. Toàn bộ tên failure và traceback được giữ lại để kiểm tra, không sửa
evidence cũ để ép xanh.

- [Log đầy đủ](../results/m4.2/verification/full-pytest.txt).
- [Danh sách failing nodes](../results/m4.2/verification/failed-nodeids.json).
- [Log chạy lại trên base](../results/m4.2/verification/base-failing-tests.txt).
- [So sánh machine-readable](../results/m4.2/verification/base-comparison.json).
- [Log 25 kiểm tra liên quan](../results/m4.2/verification/focused-tests.txt).

Thay đổi được giữ tại worktree `.worktrees/m4-2-baseline-freeze`, nhánh
`feature/m4-2-baseline-freeze`; chưa push, mở PR hay merge. Root checkout và
những thay đổi sẵn có của người dùng được giữ nguyên.

## 4. Vì sao chưa thể ghi hoàn thành toàn bộ M4.2

M4.1 yêu cầu cache/candidates ViMDoc và qrels contract verified trước execution.
Checkout có receipt lịch sử `score_input_probe_vimdoc.json`, không có bundle
ViMDoc verified cho raw/normalized scores, candidate table, top lists,
development document qrels, OCR, page identity, coverage và runtime parity.
Receipt lịch sử không được dùng để tuyên bố remote hiện nay không có dữ liệu.

Vì chưa có input bundle đó, không thể xác thực candidate fairness/coverage
thật, fit trọng số train thật, hoặc tạo hash cho baseline inputs thật.
Checkpoint QARF ViMDoc cũng chưa có trong seal; việc này thuộc thực thi downstream.
Không có số nDCG thực nghiệm hay strongest baseline nào được tạo ra để lấp chỗ trống.

Đây là kết quả và giới hạn đã kiểm chứng để người dùng quyết định bước tiếp theo.
