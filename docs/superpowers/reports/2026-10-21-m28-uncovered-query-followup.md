# M2.8 — Ghi chú query train bị trượt và hướng triển khai

Ngày ghi chú: 2026-10-21.

**Ghi chú ca lỗi: HOÀN TẤT. Đề xuất bên dưới: CHƯA TRIỂN KHAI / CHƯA PHÊ DUYỆT.
Nghiệm thu M2.8 hiện tại: BLOCKED_COVERAGE.**

## Kết quả đã quan sát

Query train: `04450a0f59f81025574451222aa26322ae7ede42_2`.

> What year did the European Commission's Pilot Project on Integrated Techniques
> for the Seismic Strengthening & Energy Efficiency of Existing Buildings start?

Nhãn nguồn ghi `reference_answer = May 2019`, `reference_page = [7]`,
`source_type = 2d_layout`, `query_type = multi_hop`.

| Bằng chứng | Nhận xét |
|---|---|
| [Trang 7 — Timeline](../../../results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01/output/pages/04450a0f59f81025574451222aa26322ae7ede42_page_0007/image.png) | Mốc đầu bên trái là May 2019, phù hợp nhãn đáp án. |
| [Trang 2 — bìa bài trình bày](../../../results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-20261019T135838Z-A01/output/pages/04450a0f59f81025574451222aa26322ae7ede42_page_0002/image.png) | Có tên dự án và ngày 17 November 2020; ngày trên bìa không được dùng thay cho mốc timeline. |
| Text trang 7 | Có 341 ký tự native+OCR, gồm May 2019; render OK, technical_failure=false. Hash ảnh và text đã được kiểm chứng. |
| Trang đứng đầu từng kênh | BM25: trang 1; dense và visual: trang 2. Cả ba đều thuộc đúng PDF chứa trang 7. |
| Thứ hạng trang 7 | BM25 271, dense 273, visual 769; đều ngoài top-200. |

Người dùng đã mở hai ảnh và cho biết nhìn thấy cả May 2019 lẫn 17 November
2020. Đây là quan sát của ca cụ thể, không được ghi thành phê duyệt toàn bộ
M2.10/D1 hoặc chấp thuận một amendment.

Tập ứng viên của query có 448 trang và không chứa trang 7. Toàn bộ baseline
thu hồi 1.141/1.142 positive pages, macro candidate recall 0.999124343257443;
query bị trượt thuộc train, validation/test đều có coverage 1.0.

**Kết luận:** chưa tìm thấy lỗi mất trang, OCR kỹ thuật, namespace hay ghép shard.
Retriever tìm đúng PDF nhưng bỏ sót trang đáp án trong audit ở đơn vị page.
Việc lấy được trang khác của cùng PDF chưa thỏa điều kiện positive page của
bundle hiện tại. Giả thuyết là trang timeline thiếu tên/ngữ cảnh dự án so với
trang bìa; đây là suy luận từ ca lỗi, chưa phải quan hệ nhân quả đã chứng minh.

## Hướng triển khai đề xuất

Ưu tiên thử **bổ sung trang của tài liệu được xếp hạng cao, dùng phần dung lượng
còn trống của tập ứng viên**. Giữ ảnh, OCR, nhãn, split, model và ba ma trận điểm
gốc. Đề xuất này thay đổi semantics của candidate policy, dù vẫn giữ trần 600,
nên cần amendment trước khi được triển khai như policy chính thức.

Một phương án xác định cụ thể để review, chưa phải cấu hình được chấp thuận:

1. Tạo `C0` bằng đúng baseline: top-200 mỗi kênh, union, giữ đủ ba raw scores.
2. Xếp hạng **toàn bộ corpus** trong mỗi kênh bằng raw score giảm dần, hòa điểm
   theo page ID tăng dần; rank bắt đầu từ 1. Tính
   `RRF(q,p) = sum_c 1 / (60 + rank_c(q,p))`.
3. Chấm mỗi PDF bằng RRF lớn nhất của một trang thuộc PDF đó. Chọn đúng **một**
   PDF có điểm cao nhất; hòa điểm theo document ID tăng dần.
4. Lấy những trang của PDF này chưa có trong `C0`, xếp theo RRF giảm dần,
   hòa điểm theo page ID tăng dần. Thêm tối đa `600 - len(C0)` trang. Giữ toàn
   bộ `C0`, không đẩy ứng viên cũ ra để dành chỗ cho trang mới.
5. Ghi tập mới theo page ID tăng dần, lấy đủ ba raw scores từ ma trận gốc và
   tính lại min-max trên union mới với epsilon `1e-15`.

Quy tắc chỉ đọc query, điểm, page IDs và mapping page→PDF. Không đọc đáp án,
qrels, query_type, source_type, tên query bị trượt hoặc số trang đáp án để quyết
định thêm trang. Cùng một quy tắc áp dụng cho mọi query và mọi phương pháp so sánh.

RRF là cách kết hợp thứ hạng không cần nhãn; công thức tham khảo
[Cormack, Clarke và Büttcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).
`k=60` cũng đã có trong `configs/m2.5/freeze.json`. Tuy nhiên, việc dùng max-RRF
để chọn PDF và bổ sung trang là **đề xuất mới của ghi chú này**, không phải kết
quả được bài báo chứng minh. Rank ở đây tính trên toàn corpus; không dùng trực
tiếp rank trên union của baseline RRF M2.5 thay thế cho định nghĩa này.

Đối với riêng ca train đã quan sát, PDF có 21 trang: 14 trang đã có trong `C0`,
7 trang còn ngoài, gồm trang 7. Query còn 152 chỗ trống. **Nếu PDF này được chọn
và thêm đủ 7 trang, union sẽ là 455 trang và chứa positive page.** Đây là tính
toán tập hợp của một ca, chưa phải kết quả chạy/coverage của policy mới.

## Các bước triển khai sau khi policy được chấp thuận

- [ ] Ghi amendment với old/new candidate definition, lý do, tác động leakage,
  fairness, chi phí và các run phải chạy lại. Ghi nhận đề xuất phát sinh sau
  khi đã quan sát một lỗi train của baseline; không gọi đây là giả thuyết độc lập
  được đăng ký trước. Dùng quy trình trong
  [protocol_amendments.md](../../../evidence/M1_FINAL/02_protocol/protocol_amendments.md),
  đối chiếu cả ledger bổ sung hiện hành trước khi cấp ID.
- [ ] Thêm builder/verifier riêng có policy ID và provenance rõ ràng. Đầu vào:
  ba full score matrices, query/page IDs, page→PDF mapping, policy đã khóa;
  đầu ra: raw/normalized rows, top-lists gốc, tập ứng viên mới, log trang được
  bổ sung và hash manifest. Mỗi trang thêm cần lưu source PDF, thứ tự ưu tiên
  và lý do `top_document_expansion`. Verifier baseline hiện tại cố ý chỉ chấp
  nhận exact top-200 union nên không dùng nguyên trạng cho union mở rộng.
- [ ] Kiểm thử label-free construction, tie determinism, duplicate/missing/
  NaN/Inf rejection, preservation của `C0`, cap 600 khi hết chỗ hoặc PDF quá
  dài, đủ ba điểm cho trang thêm, normalization mới và schema M2.4/M2.5.
  Bộ kiểm thử có cả query đã có positive và query chưa có positive; nhãn chỉ
  xuất hiện ở bước audit sau freeze.
- [ ] Thử đúng policy đã chốt trên train/validation bằng cache sẵn có. Báo
  coverage toàn bộ hai split, danh sách uncovered, min/mean/max candidate,
  tổng số trang bổ sung và thời gian xử lý; kiểm tra preservation theo từng
  query. Không đổi policy riêng cho query này, không dùng test labels để chọn
  biến thể hoặc thử nhiều cấu hình cho đến khi đạt một con số mong muốn.
- [ ] Sau khi review development, tạo namespace mới, xác minh lại các hash
  ma trận nguồn và ghi policy/source/config identity mới. Sinh rồi freeze
  ứng viên cho mọi query trước khi audit coverage test. Chỉ dùng test qrels
  cho coverage của bản đã khóa, không tính test ranking metrics để chọn policy.
- [ ] Replay độc lập, kiểm tra M2.4/M2.5 loaders và matched candidate keys/order
  cho QARF/QPAF cùng các baseline dùng chung candidate pool. Nghiệm thu khi
  recall ≥0,95, zero uncovered, mọi query ≤600 trang và integrity checks pass;
  vẫn cần independent review theo protocol.

Ba ma trận đã chứa điểm cho mọi query–page nên phần thử chính sách ứng viên
không cần encode lại mô hình hay mở thêm worker GPU. Nếu sau này đổi model,
ảnh hoặc visual token budget thì đó là nhánh calibration/inference mới; khi
chạy inference trên Modal vẫn dùng GPU theo yêu cầu người dùng.

Candidate count lớn hơn có thể tăng chi phí và thêm distractor; coverage tăng
không chứng minh nDCG@10 hay learned QPAF sẽ tăng. Mọi đánh giá đánh đổi để
chọn policy phải thực hiện trong development, giữ phép so sánh matched.

## Trạng thái bàn giao

Ghi chú này hoàn tất phần mô tả ca lỗi và hướng triển khai. **Cache hiện tại,
nhãn, trạng thái `BLOCKED_COVERAGE` và revision `m2.8-001` được giữ nguyên.**
Chưa triển khai policy mới, chưa tạo candidate run mới, chưa có số đo cải thiện
hay phê duyệt amendment để ghi nhận.

Nguồn đối chiếu: [báo cáo baseline](2026-10-20-m28-score-cache.md),
[chẩn đoán có hash](../../../results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/uncovered_diagnosis.json),
[freeze gốc](../../../results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/bundle/candidate_freeze.json),
[handover gốc](../../../results/m2.8/RUN-QPAF-M2_8-CACHE-001-20261020T144311Z-A01/bundle/handover.json).
