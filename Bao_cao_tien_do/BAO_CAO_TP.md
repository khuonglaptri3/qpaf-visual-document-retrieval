# BÁO CÁO PHẦN KẾT QUẢ VÀ ORACLE STUDY CỦA QPAF

## 1. Kết luận chính

Các thí nghiệm trên **ViDoSeek** cho thấy QPAF có **tiềm năng đáng để tiếp tục nghiên cứu**: trên cùng một tập 24 query đã cố định, QPAF oracle đều tốt hơn QARF oracle ở cả hai tập trọng số W7 và W66. Mức tăng trung bình `nDCG@10` lần lượt là `+0.050011` và `+0.032066`; cả hai khoảng tin cậy bootstrap 95% đều có cận dưới lớn hơn 0 và không có query nào bị giảm điểm.

Claim chính xác ở thời điểm hiện tại là:

> **Các oracle study đã xác nhận bounded headroom cho page-level adaptive fusion so với query-level adaptive fusion, đủ cơ sở để tiếp tục sang matched learned QARF–QPAF. Đây chưa phải bằng chứng rằng learned/deployable QPAF đã cải thiện.**

## 2. QPAF đang được so sánh với gì?

- **Global:** dùng một bộ trọng số BM25–dense–visual chung cho toàn bộ tập.
- **QARF:** chọn một bộ trọng số cho mỗi query, rồi dùng bộ đó cho mọi page của query.
- **QPAF:** có thể chọn trọng số khác nhau cho từng cặp query–page.

### W7 và W66 là gì?

Trong project, **W7 và W66 là hai tập gồm các bộ trọng số có thể lựa chọn** để phối hợp ba kênh BM25, dense và visual:

`S(q,p) = w_B × s_BM25 + w_D × s_dense + w_V × s_visual`, với `w_B + w_D + w_V = 1`.

W7 gồm 7 bộ trọng số đơn giản:

| Trọng số`(BM25, dense, visual)` | Ý nghĩa           |
| ----------------------------------- | ------------------- |
| `(1, 0, 0)`                       | Chỉ BM25           |
| `(0, 1, 0)`                       | Chỉ dense          |
| `(0, 0, 1)`                       | Chỉ visual         |
| `(0.5, 0.5, 0)`                   | BM25 + dense        |
| `(0.5, 0, 0.5)`                   | BM25 + visual       |
| `(0, 0.5, 0.5)`                   | Dense + visual      |
| `(1/3, 1/3, 1/3)`                 | Chia đều ba kênh |

W66 gồm đúng **66 bộ trọng số**. Mỗi trọng số nhận một giá trị trong `{0.0, 0.1, ..., 1.0}` và tổng ba trọng số bằng 1, chẳng hạn `(0.0, 0.2, 0.8)` hoặc `(0.6, 0.3, 0.1)`. W66 có nhiều cách kết hợp chi tiết hơn W7, nhưng **không phải 66 query, 66 mô hình hay trọng số learned cuối cùng**.

Với cùng một tập, Global chọn một bộ trọng số cho toàn tập; QARF oracle chọn một bộ cho mỗi query; QPAF oracle có thể chọn các bộ khác nhau cho từng cặp query–page. QPAF oracle hiện bắt đầu từ bộ trọng số của QARF, thử thay đổi theo từng page và chỉ giữ lại thay đổi làm `nDCG@10` tăng, tối đa hai lượt. Vì quá trình chọn này dùng relevance/qrels, kết quả chỉ cho thấy giới hạn tiềm năng theo oracle; learned QPAF sau này phải tự dự đoán trọng số từ label-free features.

Trong các oracle study, relevance/qrels được dùng để chọn trọng số tốt nhất. Vì vậy, các kết quả dưới đây đo **giới hạn tiềm năng (oracle upper bound)** của ý tưởng page-level adaptation, không đo khả năng dự đoán trọng số khi triển khai thực tế.

## 3. Kết quả thực nghiệm đã xác minh

Primary metric là mean per-query `nDCG@10`.

| Study                       |                          Phạm vi |   Global |     QARF |               QPAF |               QPAF − QARF | CI95                           | Thắng / hòa / thua |
| --------------------------- | --------------------------------: | -------: | -------: | -----------------: | -------------------------: | ------------------------------ | -------------------: |
| Full fixed-profile W7 audit |       1.142 query; 6.149.670 pair | 0.875138 | 0.908268 |        Chưa chạy | Không phải measured gain | —                             |                   — |
| Exploratory-24 W7           |            24 query; 129.240 pair | 0.817634 | 0.853845 | **0.903856** |        **+0.050011** | **[0.008344, 0.101921]** | **5 / 19 / 0** |
| Exploratory-24 W66          | Cùng 24 query; 66 bộ trọng số | 0.829678 | 0.853845 | **0.885911** |        **+0.032066** | **[0.002888, 0.071165]** | **4 / 20 / 0** |
| Pilot exploratory-12 W7     |             12 query; 64.620 pair | 0.952556 | 0.958333 |           1.000000 |                  +0.041667 | [0, 0.125]                     |           1 / 11 / 0 |

Các điểm đáng chú ý:

1. **Tín hiệu lặp lại trên hai tập trọng số:** W7 và W66 đều cho QPAF cao hơn QARF trên cùng 24 query; cận dưới CI95 đều dương và số query thua bằng 0.
2. **Không chỉ do một query như pilot ban đầu:** với W7, QPAF cải thiện 5/24 query; với W66, cải thiện 4/24 query. Tỷ lệ gain nằm trong top 5% query lần lượt là `0.666315` và `0.739788`, đều dưới ngưỡng concentration `0.90` đã dùng để quyết định tiếp tục.
3. **Chỉ cần thay đổi rất ít page:** W7 thay 6/129.240 page assignment trên 5 query; W66 thay 5/129.240 assignment trên 4 query nhưng vẫn tạo ra mức tăng trung bình dương. Điều này phù hợp với giả thuyết rằng một số page cần cách phối hợp kênh riêng, thay vì mọi page trong query đều dùng cùng một trọng số.
4. **Full fixed-profile audit cho thấy còn chỗ để cải thiện:** trên toàn bộ 1.142 query, QARF tăng `+0.033129` so với Global; 216 query vẫn chưa đạt trần `nDCG@10=1`. Mean theoretical headroom `1 − QARF` là `0.091732`. Đây chỉ là upper bound toán học, không phải mức tăng QPAF đã đo.

W66 **không tốt hơn W7** trong study này: mean QPAF của W66 thấp hơn W7 `0.017945`. Independent review truy chênh lệch này về một query có nhiều bộ trọng số QARF cùng đạt `nDCG@10=0`, khiến thứ tự duyệt chọn điểm bắt đầu khác. Kết quả này cho thấy cách tìm hiện tại còn nhạy với điểm bắt đầu; không chứng minh rằng nhiều bộ trọng số hơn luôn tốt hơn.

## 4. Case study dễ trình bày: query 797

Query 797 là query duy nhất cải thiện trong pilot 12 query và đã được tái dựng độc lập từ saved checkpoint:

| Phương pháp | Cách chọn trọng số           | Rank của relevant page |            nDCG@10 |
| -------------- | -------------------------------- | ----------------------: | -----------------: |
| Global         | Visual cho mọi page             |                       4 |           0.430677 |
| QARF oracle    | BM25 cho mọi page               |                       3 |           0.500000 |
| QPAF oracle    | Chuyển đúng 2 page sang dense |             **1** | **1.000000** |

QPAF hạ điểm distractor đứng đầu từ `1.000000` xuống `0.926680`, đồng thời tăng điểm relevant page từ `0.625620` lên `0.981792`, đưa relevant page lên rank 1. **Dense riêng lẻ cũng chỉ xếp relevant page ở rank 3**; vì vậy lợi ích đến từ việc chọn kênh có chọn lọc theo page, không phải từ việc đổi cả query sang một retriever khác.

Đây là minh họa rõ cơ chế QPAF có thể sửa ranking như thế nào, nhưng không được dùng riêng case này để claim hiệu quả tổng quát.

## 5. Độ tin cậy và tiến độ hiện tại

- Các kết quả không chỉ lấy từ summary. Independent review của W7 kiểm tra 82 manifest artifact, 50 checkpoint envelope, 960 raw ranking metric và 415 phép so sánh; review W66 kiểm tra 97 artifact, 50 checkpoint, 6.624 raw metric value và 127 phép so sánh. Tất cả đều `PASS`.
- P1-02R đã tạo và xác minh score table toàn corpus gồm 1.142 query × 5.385 page = 6.149.670 pair, coverage `1.0`, không thiếu relevant pair. Đây là data-readiness evidence, không phải kết quả QPAF.
- Method core learned đã có 13 label-free feature, linear QARF/QPAF gate, fusion scorer và masked listwise loss. Bộ test tập trung vừa được chạy lại ngày 15/09/2026: **14/14 test pass**.
- Chưa có optimizer step, trained checkpoint hay learned QPAF metric. P2-01/P2-02 mới `PASS_LOCAL_METHOD_CORE_ONLY`; P2-03/P2-04 chưa chạy; formal P1-02 và P1-03 vẫn `BLOCKED`.

## 6. Cách diễn đạt khi báo cáo

### Bản nói ngắn

> Phần em phụ trách tập trung kiểm tra liệu việc điều chỉnh trọng số theo từng query–page có tiềm năng tốt hơn việc dùng một trọng số chung cho cả query hay không. Trên cùng 24 query ViDoSeek, QPAF oracle đạt 0.903856 nDCG@10 với W7, cao hơn QARF 0.050011; CI95 là [0.008344, 0.101921], với 5 query thắng và không có query thua. Khi dùng tập W66 chi tiết hơn, mức tăng vẫn còn 0.032066, CI95 [0.002888, 0.071165], 4 query thắng và không có query thua. Case query 797 cho thấy cơ chế cụ thể: QPAF chỉ đổi trọng số ở hai page nhưng đưa relevant page từ rank 3 lên rank 1. Vì đây là oracle dùng relevance để chọn trọng số, kết luận đúng hiện tại là QPAF có bounded headroom và đáng để tiếp tục huấn luyện, chứ chưa thể nói learned QPAF đã tốt hơn QARF trong triển khai.

### Nếu giảng viên hỏi “Vậy QPAF đã tốt hơn chưa?”

> **Trong oracle study có, và kết quả đã lặp lại trên W7 lẫn W66. Trong learned/deployable setting thì chưa có kết quả; bước kế tiếp bắt buộc là train và so sánh matched learned QARF với learned QPAF trên cùng data, feature, loss, optimizer, seed và compute budget.**

Để chuyển từ “có tiềm năng” sang positive learned claim, kết quả cuối cần đạt tối thiểu `QPAF − QARF nDCG@10 >= 0.01`, CI95 có cận dưới `> 0`, thắng strongest deployable baseline và lặp lại đủ ba seed đã định trước.

## 7. Nguồn số liệu trong project

- [Định nghĩa chính xác của W7 và W66](src/oracle_study/profiles.py)
- [Full fixed-profile W7 audit](docs/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md)
- [Exploratory-24 W7 results](docs/QPAF_EXPLORATORY24_RESULTS.md) và [independent integrity review](artifacts/vidoseek_exploratory24_review/result_integrity_review.json)
- [Exploratory-24 W66 results](docs/QPAF_W66_EXPLORATORY24_RESULTS.md) và [independent integrity review](artifacts/vidoseek_w66_exploratory24_optimized_review/result_integrity_review.json)
- [Exploratory-12 results](docs/QPAF_EXPLORATORY12_RESULTS.md)
- [Query 797 case study](docs/QPAF_QUERY797_CASE_STUDY.md) và [case reconstruction review](artifacts/vidoseek_exploratory12_case797_review/case_review.json)
- [Current project context and claim boundaries](PROJECT_CONTEXT.md), [formal task DAG](Tasks.md), [scientific contract](Context.md)
