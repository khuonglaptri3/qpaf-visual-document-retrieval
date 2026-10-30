# Kết quả chạy F3 objective — 30/10/2026

**Đã hoàn tất phần ViDoSeek: baseline và hai variant, 970 query, 5 fold, 1 seed.
Chưa có bằng chứng cải thiện rõ so với baseline: cả bốn CI95 đều chứa 0.
ViMDoc chưa chạy vì thiếu cache đầu vào.**

| Phương án | Static | QARF | QPAF | Compute (phút) |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 0.865492 | 0.865749 | 0.860889 | 10.26 |
| ApproxNDCG | 0.865492 | 0.866475 | 0.863102 | 8.94 |
| Top-k / hard | 0.865492 | 0.864335 | 0.861563 | 10.06 |

Chỉ số là nDCG@10 trên development pool; mỗi query được chấm bởi model chưa thấy nhãn của nó.
Thời gian là compute do harness ghi, không gồm cài môi trường, lượt dở và kiểm thử.

So với baseline **cùng method**, paired bootstrap 10.000 lần theo query, seed 20260820:

| Phương án | Method | Delta nDCG@10 | CI95 | Thắng/hòa/thua | Verdict |
| --- | --- | ---: | --- | --- | --- |
| ApproxNDCG | QARF | +0.000725 | [-0.001336, +0.002758] | 12/946/12 | n/a |
| ApproxNDCG | QPAF | +0.002213 | [-0.001818, +0.006202] | 47/887/36 | n/a |
| Top-k / hard | QARF | -0.001415 | [-0.003647, +0.000694] | 8/949/13 | n/a |
| Top-k / hard | QPAF | +0.000674 | [-0.000641, +0.002102] | 15/942/13 | n/a |

ApproxNDCG tăng mean nhẹ ở cả hai method nhưng CI còn qua 0. Top-k/hard giảm mean QARF và tăng nhẹ QPAF,
cũng chưa phân biệt rõ với baseline. Không kết luận KEEP/DROP: `verdict()` của protocol chưa được chốt.
Đây là sàng lọc CV một seed, không phải xác nhận độc lập; không mở confirmation/TEST-172, không chọn epoch
hay quét siêu tham số.

**Phạm vi và kiểm chứng.** Recipe gốc: 40 epoch, trung bình trọng số epoch 20–40, Adam lr 0,01/cosine,
batch 16, seed 20260820. Fold sizes: 204/211/197/170/188. Input SHA-256 khớp tham chiếu.
Baseline tái lập sai lệch mean bằng 0. Cả ba JSON đầy đủ có `smoke=false`, `tracked_changes=false`,
cùng query IDs và recipe.

Môi trường riêng: Python 3.11.16, torch 2.7.1+cpu, numpy 2.2.6, pandas 2.2.3, pyarrow 20.0.0.
Baseline dùng 2 luồng OMP/MKL; hai variant cuối dùng 6 luồng. Baseline source `41bc94e`;
hai variant source `e3252f6`. Các file harness dùng chung và baseline không đổi giữa hai commit.

Đã tối ưu [f3_approxndcg.py](../../../../src/qpaf/lab/variants/f3_approxndcg.py): chỉ tính hạng cho positive,
mỗi positive vẫn so với mọi ứng viên. Loss, alpha, cutoff, width và recipe giữ nguyên.

- TDD RED bắt tensor quadratic ở code cũ; GREEN kiểm loss/gradient với công thức dense, padding, nhiều positive,
  query không hợp lệ và giới hạn working set. Hai smoke sau tối ưu khớp từng điểm query với bản gốc.
- Kiểm thử liên quan: **20/20 đạt**; [log](evidence/unit-tests.log).
- Toàn repo: **802 kiểm thử, OK, 6 bỏ qua**, 440,112 giây; [log](evidence/full-suite.log).
- Microbenchmark loss: khoảng **21,3 lần nhanh hơn**, intermediate lớn nhất từ 5.363.856 xuống 18.528 phần tử;
  [số đo](evidence/sparse-benchmark.json). Đây không phải mức tăng tốc toàn pipeline.
- Lượt dense 2/6 luồng bị ngắt để tối ưu: [lượt 2 luồng](evidence/attempt-threads2/),
  [lượt 6 luồng](evidence/attempt-threads6/). Không dùng metric từ lượt dở.

**Phần còn thiếu.** Ba lượt ViMDoc `f3_approxndcg`, `f3_topk_hard`, `f3_lse_pool` chưa chạy.
Cần nhận đúng `candidate_scores.parquet`, `queries.jsonl`, `dev_qrels.json`; không cần asset của F1/F4
hay nhãn confirmation. [Tên file và hash cần nhận](evidence/missing-inputs.json).
Tài liệu nhánh ghi cache do Tấn Phát giữ tại `C:/Users/HP/qpaf-cache/a005-s1-001`.
Tài khoản Modal đang cấu hình không có volume `qpaf-artifacts`; [volume đã kiểm tra](evidence/modal-volumes.json).
Không tạo compute cloud hay gửi yêu cầu tới thành viên khác.

**Quyết định thực thi và giới hạn.**

1. Giữ task ledger và mọi log dưới `evidence/` theo quy ước người dùng; không đổi ý nghĩa thí nghiệm.
2. Xác minh test cũ, không gán TDD hồi tố; RED→GREEN chỉ áp dụng cho tối ưu hiệu năng mới.
3. Chạy ViDoSeek đủ đầu vào trước; kết luận F3 còn thiếu ViMDoc.
4. Dùng CLI trực tiếp thay runner bắt buộc cả share folder; kiểm hash, baseline và smoke được thực hiện riêng.
5. Đổi 2 → 6 luồng và lưu lượt dở; chi phí là compute đã bỏ, không thêm lượt đó vào thống kê.
6. Tối ưu hạng positive tương đương; sai khác làm tròn được kiểm ở loss/gradient và smoke, source đổi được ghi rõ.

**Hồ sơ thực thi.**

- [Đặc tả](superpowers/spec.md), [kế hoạch](superpowers/plan.md), [thiết kế F3](../../../feature_lab/F3_ranking_objective.md).
- [Workflow và skill đã áp dụng](evidence/workflow.md), [nhật ký quyết định](evidence/execution-ledger.md).
- [JSON baseline và hai variant](evidence/results/vidoseek/), [bảng so sánh](evidence/SUMMARY_f3.md),
  [so sánh có cấu trúc](evidence/comparisons.json).
- [Đầu vào](evidence/input-validation.json), [parity baseline](evidence/baseline-validation.json),
  [môi trường](evidence/environment.json), [gói đã cài](evidence/installed-packages.txt).
- [Script thực thi đã dùng](evidence/run_f3.py), [lệnh và tiến trình](evidence/execution.log).
  Đây là bản ghi lượt chạy; khi tái lập, dùng output mới trong cây sạch để giữ đúng provenance.
- [Review độc lập bằng agent](evidence/final-review.md): không có lỗi Critical/Important; thống kê đã được tính lại và khớp.
- [Kiểm tra bàn giao](evidence/validation.json), [manifest SHA-256](evidence/hashes.json): layout, liên kết, provenance
  và điểm từng query đã được kiểm chứng. Nhánh local `feature/lab-f3-objective` được giữ trong workspace riêng.
