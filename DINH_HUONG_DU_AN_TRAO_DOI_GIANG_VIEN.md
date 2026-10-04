# Định hướng dự án để trao đổi với giảng viên

**Đề tài:** Adaptive Retrieval Fusion for Visually Rich Document RAG

**Tên tiếng Việt:** Dung hợp truy xuất thích ứng cho hệ thống RAG trên tài liệu giàu thông tin trực quan

**Cập nhật ngày:** 08/09/2026.

> **Định hướng đề xuất:** Nghiên cứu một module nhẹ kết hợp kết quả tìm kiếm từ khóa, ngữ nghĩa và hình ảnh; module tự điều chỉnh trọng số theo từng cặp câu hỏi–trang để tìm đúng trang bằng chứng. Cần kiểm chứng liệu cách này có tốt hơn cách dùng trọng số cố định hoặc chỉ điều chỉnh theo câu hỏi hay không.

**Cách dùng trong buổi gặp:** Trình bày bài toán và ý tưởng ở mục 1–3, báo cáo ngắn trạng thái ở mục 5, rồi chốt các câu hỏi ở mục 7. Mục 4 và 6 dùng khi cần trao đổi sâu về đánh giá và lộ trình.

## 1. Bài toán muốn giải quyết

Khi hỏi một hệ thống RAG về báo cáo tài chính, tài liệu kỹ thuật hoặc slide, hệ thống phải tìm được trang chứa bằng chứng trước khi sinh câu trả lời. Tuy nhiên, bằng chứng có thể nằm trong đoạn văn, bảng số liệu, biểu đồ hoặc bố cục của trang. Chuyển mọi nội dung thành văn bản có thể làm mất một phần thông tin hữu ích.

Dự án tập trung vào **truy xuất và xếp hạng trang bằng chứng**. Đầu vào là câu hỏi và kho tài liệu; đầu ra là danh sách các trang được xếp theo mức độ liên quan. Một mô hình đọc tài liệu có thể sử dụng danh sách này để trả lời ở bước sau, nhưng chất lượng sinh câu trả lời chưa nằm trong phạm vi đánh giá chính.

Ví dụ minh họa: với câu hỏi “Doanh thu của công ty thay đổi như thế nào qua các năm?”, trang thuyết minh có thể hữu ích nhờ nội dung văn bản, còn trang biểu đồ có thể hữu ích nhờ thông tin trực quan. Đây là tình huống thúc đẩy ý tưởng kết hợp nhiều kênh; chưa phải kết quả thực nghiệm của dự án.

## 2. Hướng giải quyết: QPAF

Ba kênh truy xuất trong thiết kế hiện tại gồm:

| Kênh | Vai trò trong hệ thống |
| --- | --- |
| BM25 | Đối sánh từ khóa trên văn bản được trích xuất từ tài liệu. |
| BGE-M3 | Đối sánh ngữ nghĩa giữa câu hỏi và văn bản. |
| ColQwen2.5 | Đối sánh câu hỏi với hình ảnh của trang tài liệu. |

**Query-Page-Adaptive Fusion (QPAF)** nhận điểm từ ba kênh, chuẩn hóa thang điểm, rồi dự đoán mức đóng góp của từng kênh cho mỗi cặp câu hỏi–trang.

Luồng xử lý dự kiến:

```text
Câu hỏi + kho tài liệu
         ↓
BM25 / BGE-M3 / ColQwen2.5 tạo điểm và danh sách ứng viên
         ↓
Hợp nhất ứng viên → chấm đủ ba kênh trên cùng tập ứng viên
         ↓
Chuẩn hóa điểm và tạo đặc trưng
         ↓
QPAF dự đoán ba trọng số riêng cho từng cặp câu hỏi–trang
         ↓
Tính điểm tổng hợp → xếp hạng → trả về các trang bằng chứng
```

Công thức trực giác:

```text
Điểm QPAF = wB × điểm BM25 đã chuẩn hóa
          + wD × điểm BGE-M3 đã chuẩn hóa
          + wV × điểm ColQwen2.5 đã chuẩn hóa

wB, wD, wV ≥ 0 và wB + wD + wV = 1.
Ba trọng số có thể thay đổi giữa các trang của cùng một câu hỏi.
```

Phương án tối thiểu trong kế hoạch hiện tại là bộ dự đoán tuyến tính kết hợp softmax, phép biến đổi tạo ba trọng số không âm có tổng bằng 1. Đầu vào gồm 13 đặc trưng từ điểm, thứ hạng, chênh lệch điểm và mức bất đồng giữa các kênh. Bản tối thiểu sử dụng các tín hiệu truy xuất này; chưa bổ sung bộ mã hóa câu hỏi hoặc trang vào module fusion.

**Module học bằng cách nào?** Khi huấn luyện, mô hình nhận điểm của các trang ứng viên và nhãn cho biết trang hoặc tài liệu nào liên quan. Hàm mất mát xếp hạng theo danh sách (listwise) điều chỉnh bộ tạo trọng số để ưu tiên kết quả liên quan. Khi suy luận với câu hỏi mới, mô hình chỉ dùng các đặc trưng điểm/thứ hạng để tạo trọng số. Nhãn không được đưa vào đặc trưng hay dùng để xây dựng tập ứng viên ở bất kỳ giai đoạn nào.

Các retriever nền được giữ cố định; chỉ huấn luyện module tạo trọng số. Cách thiết kế này giúp xác định phần cải thiện đến từ cơ chế kết hợp. Chi phí tạo điểm của ba retriever vẫn phải được tính riêng: module fusion nhẹ không có nghĩa toàn bộ hệ thống truy xuất đều rẻ.

## 3. Câu hỏi nghiên cứu và đóng góp dự kiến

**Câu hỏi trung tâm:** Khi giữ cùng dữ liệu, tập ứng viên và ba retriever, trọng số riêng cho từng cặp câu hỏi–trang có giúp xếp hạng tốt hơn trọng số chung cho toàn bộ câu hỏi không?

| Phương án | Phạm vi dùng chung trọng số | Vai trò so sánh |
| --- | --- | --- |
| Fixed/Global fusion | Mọi câu hỏi và mọi trang | Kiểm tra hiệu quả của cách kết hợp đơn giản. |
| QARF — thích ứng theo câu hỏi | Mọi trang của một câu hỏi | Đối chứng trực tiếp để kiểm tra có cần thích ứng theo trang không. |
| QPAF — thích ứng theo câu hỏi–trang | Riêng từng cặp câu hỏi–trang | Phương pháp đề xuất. |

Ngoài ra, cần so sánh với từng retriever riêng và RRF, phương pháp kết hợp dựa trên thứ hạng. CARF, tức thích ứng theo nhóm trang ứng viên, là phân tích bổ sung có điều kiện trong kế hoạch; không nên đặt thành một hướng chính ngang hàng khi trình bày mục tiêu đề tài.

Hai công trình định hướng trong đề cương có vai trò khác nhau:

- **mFAR — Multi-Field Adaptive Retrieval:** Học mức đóng góp của các trường thông tin và kênh lexical/dense theo câu hỏi. Đề tài lấy cảm hứng từ cách tạo trọng số thích ứng, rồi đề xuất điều kiện hóa theo cặp câu hỏi–trang và bổ sung kênh hình ảnh. Bản QPAF tối thiểu là thiết kế riêng trên đặc trưng điểm/thứ hạng, không phải áp dụng nguyên bản kiến trúc mFAR. Nguồn: [bài báo mFAR](https://arxiv.org/abs/2410.20056).
- **DAT — Dynamic Alpha Tuning:** Dùng LLM đánh giá kết quả đứng đầu của BM25 và dense để điều chỉnh trọng số theo từng câu hỏi. DAT là đối chứng liên quan; baseline QARF dự kiến trong repo là một bộ tạo trọng số học được cho cả ba kênh. Khi so sánh với DAT, phải ghi rõ khác biệt số kênh và chi phí gọi LLM. Nguồn: [bài báo DAT](https://arxiv.org/abs/2503.23013).

Điểm cần kiểm chứng là lợi ích của **trọng số phụ thuộc cả câu hỏi và trang**, vượt lên trên lợi ích chỉ do thêm kênh hình ảnh. Vì vậy, QARF và QPAF phải dùng cùng ba kênh và ngân sách huấn luyện tương đương. Tính mới so với toàn bộ nghiên cứu liên quan vẫn cần được rà soát và giảng viên góp ý.

Đóng góp dự kiến gồm:

1. Một phương pháp kết hợp ba kênh ở mức câu hỏi–trang, giữ cố định các retriever nền.
2. Thực nghiệm làm rõ khi nào thích ứng theo trang có ích, và khi nào cách đơn giản hơn đã đủ.
3. Bộ mã nguồn, cấu hình và kết quả có thể kiểm tra, tái lập; kèm phân tích chất lượng và chi phí của module fusion.

Nếu QPAF không cải thiện đủ rõ so với QARF hoặc fixed fusion, hướng xử lý là báo cáo giới hạn và chọn phương án đơn giản hơn. Giá trị của kết luận này đối với yêu cầu khóa luận là một điểm cần thống nhất với giảng viên.

## 4. Phạm vi thực nghiệm và tiêu chí đánh giá

Kế hoạch dữ liệu hiện tại phân chia ba vai trò:

| Dữ liệu | Vai trò | Đơn vị đánh giá |
| --- | --- | --- |
| ViDoSeek | Khảo sát ban đầu; đã chuẩn bị 1.142 câu hỏi và 5.385 trang | Trang tài liệu. |
| ViMDoc | Kiểm chứng trên bộ dữ liệu thứ hai | Tài liệu theo ánh xạ HEAVEN; lấy điểm trang cao nhất làm điểm tài liệu. |
| ViDoRe V3 Finance EN | Đánh giá ngoài miền theo protocol giữ riêng | Trang tài liệu. |

QPAF vẫn tính trọng số theo trang trên ViMDoc, nhưng phải đánh giá bằng nhãn tài liệu; không tự suy ra nhãn trang từ nhãn tài liệu. Các vai trò dữ liệu trong bảng là kế hoạch thực nghiệm, chưa phải các đánh giá đã hoàn tất.

Chỉ số chính là **nDCG@10**, phản ánh chất lượng sắp xếp các kết quả liên quan trong 10 vị trí đầu. Chỉ số phụ gồm Recall@1, Recall@3 và MRR@10; đồng thời đo độ trễ và bộ nhớ.

Mục tiêu đang được ghi trong kế hoạch cho mô hình QPAF đã học là tăng ít nhất **0,01 nDCG@10 tuyệt đối** so với baseline triển khai được mạnh nhất, có khoảng tin cậy 95% của mức tăng nằm trên 0, và độ trễ fusion bổ sung trung vị không quá 10 ms/câu hỏi trên phần cứng đánh giá được khai báo. Giới hạn bộ nhớ trong kế hoạch là mức cấp phát CUDA cực đại dưới 1,50 GiB cho thí nghiệm learned fusion, không phải toàn bộ ba retriever. Đây là **tiêu chí mục tiêu, chưa phải kết quả đạt được**; mọi điều chỉnh cần được thống nhất và ghi lại trước khi chạy thí nghiệm liên quan.

So sánh phải dùng cùng tập ứng viên, cách chuẩn hóa và phân chia dữ liệu; tách câu hỏi huấn luyện, validation và test. Kế hoạch cuối có ba seed và các thí nghiệm bỏ từng thành phần để xác định nguồn cải thiện. Tỷ lệ chia train/validation/test cụ thể vẫn cần chốt. ViDoRe đã có một số kiểm tra baseline trên tập ứng viên, nên cần kiểm tra lịch sử sử dụng nhãn trước khi khẳng định tính độc lập của đánh giá ngoài miền.

## 5. Hiện tại dự án đang ở đâu?

Trạng thái dưới đây được đối chiếu từ tài liệu, cấu hình và các bản ghi kiểm tra trong repo ngày 08/09/2026. Bundle P1-02R, audit fixed-profile và exploratory-24 đều có receipt kiểm tra độc lập; đây là bằng chứng oracle hậu kiểm/thăm dò, không phải hiệu năng của mô hình đã học.

| Nội dung | Trạng thái được ghi nhận |
| --- | --- |
| Đề cương, công thức và kế hoạch đánh giá | Đã có; một số lựa chọn như tỷ lệ chia dữ liệu và lịch tiếp theo còn cần chốt. |
| Pipeline tạo điểm và kiểm tra dữ liệu | Đã xây dựng, có bản ghi kiểm tra. |
| Bộ điểm ViDoSeek toàn corpus, nhánh P1-02R | Đã được ghi nhận xác minh: 6.149.670 cặp câu hỏi–trang, độ phủ 1,0. |
| Bằng chứng QPAF tốt hơn QARF | Có tín hiệu oracle W7 thăm dò trên 24 câu hỏi: tăng 0,050011 nDCG@10, CI95 [0,008344; 0,101921], thắng/hòa/thua 5/19/0. Chưa phải kết luận Phase 1 chính thức. |
| Audit fixed-profile toàn discovery | Đã hoàn tất 1.142 câu hỏi; QARF đạt 0,908268 và cận trên lý thuyết còn lại cho QPAF là 0,091732. Audit không chạy QPAF. |
| Module QARF/QPAF đã học | Chưa triển khai và huấn luyện. |
| Benchmark ba seed, phân tích thành phần và đánh giá ngoài miền cuối cùng | Chưa hoàn thành. |

**Độ phủ 1,0 có nghĩa gì?** Tập ứng viên của bộ điểm này chứa đủ các trang được gán nhãn liên quan. Nó không có nghĩa hệ thống xếp đúng tất cả các trang hay trả lời chính xác 100%. QPAF chỉ xếp lại các trang đã có trong tập ứng viên; nó không thể phục hồi một trang đã bị loại ở bước truy xuất.

**Vướng mắc cần giải thích nếu được hỏi:** Thí nghiệm ban đầu P1-02 dùng tập ứng viên giới hạn. Sau lần mở rộng đã quy định, vẫn có một câu hỏi thiếu trang liên quan nên thí nghiệm được giữ trạng thái `BLOCKED`. Nhánh P1-02R đã tạo và xác minh bộ điểm trên toàn corpus để khảo sát riêng vấn đề này; nó không làm cho thí nghiệm gốc tự động đạt yêu cầu.

Bước tiếp theo cần được thống nhất về protocol và tài nguyên trước khi thực hiện: W66 trên đúng 24 câu hỏi đã cố định để kiểm tra độ nhạy theo độ mịn của lưới trọng số. Chưa được coi kết quả oracle thăm dò là hiệu năng QPAF có thể triển khai hoặc xem giai đoạn huấn luyện đã được mở. Mốc quyết định 05/09/2026 trong kế hoạch cũ đã qua; muốn ra quyết định Phase 1 chính thức cần cập nhật lịch và task graph.

## 6. Lộ trình đề xuất để xin góp ý

Đây là thứ tự trao đổi và thực hiện có điều kiện, không phải thay đổi trạng thái các nhiệm vụ trong repo.

| Chặng | Việc cần đạt | Điều kiện chuyển tiếp |
| --- | --- | --- |
| 1. Chốt phạm vi | Thống nhất câu hỏi nghiên cứu, dữ liệu, protocol tiếp tục, lịch và sản phẩm cuối | Có quyết định rõ về phần bắt buộc và phần có thể thu hẹp. |
| 2. Kiểm tra tiềm năng | W7 thăm dò đã có tín hiệu; tiếp theo đánh giá W66 trên cùng 24 câu hỏi nếu protocol và tài nguyên được duyệt | W7/W66 nhất quán theo cổng quyết định đã thống nhất; nếu chưa đạt thì điều chỉnh hoặc dừng hướng này. |
| 3. Học module fusion | Xây dựng baseline QARF trước, rồi QPAF khi đủ điều kiện | So sánh công bằng trên dữ liệu tách biệt, không dùng nhãn khi suy luận. |
| 4. Đánh giá và hoàn thiện | Đo chất lượng, độ ổn định, chi phí; phân tích thành phần và khả năng khái quát | Mỗi kết luận có kết quả đối chiếu và cấu hình tái lập. |

Sản phẩm cuối dự kiến là báo cáo nghiên cứu, mã nguồn module fusion và bộ thực nghiệm tái lập. Demo trả về trang bằng chứng có thể là sản phẩm minh họa; demo hỏi–đáp hoàn chỉnh cần được giảng viên xác nhận là yêu cầu bổ sung hay bắt buộc.

## 7. Những điểm muốn giảng viên quyết định

1. **Tính mới:** So sánh thích ứng theo trang với thích ứng theo câu hỏi có đủ rõ và đủ giá trị làm trọng tâm đề tài không? Cần bổ sung đối chứng hoặc công trình liên quan nào?
2. **Phạm vi:** Giữ ba bộ dữ liệu theo kế hoạch hay thu hẹp? Sản phẩm chính là nghiên cứu retrieval hay phải có hệ thống hỏi–đáp hoàn chỉnh?
3. **Thiết kế tiếp tục:** Có chấp nhận W7 hậu kiểm như bằng chứng thăm dò riêng, giữ nguyên giới hạn của protocol ban đầu, và duyệt W66 trên đúng 24 câu hỏi đã cố định không?
4. **Tiêu chí thành công:** Ngưỡng cải thiện, yêu cầu thống kê và giới hạn độ trễ hiện tại có phù hợp không? Nếu QPAF không hơn QARF, cần những phân tích nào để kết luận vẫn đủ giá trị?
5. **Tiến độ và nguồn lực:** Thời hạn báo cáo, ngân sách tính toán và mốc cần quyết định tiếp tục/dừng là khi nào?

### Đoạn mở đầu có thể nói trong khoảng một phút

> Dạ, nhóm em nghiên cứu cách tìm đúng trang bằng chứng trong tài liệu có văn bản, bảng và biểu đồ. Nhóm đề xuất QPAF, kết hợp điểm từ khóa, ngữ nghĩa và hình ảnh bằng trọng số riêng cho từng cặp câu hỏi–trang. Trên 24 câu hỏi ViDoSeek bổ sung được chọn trước, oracle W7 cải thiện 0,050011 nDCG@10 so với QARF, với khoảng bootstrap 95% nằm trên 0. Đây là tín hiệu thăm dò chứ chưa phải mô hình đã học hay kết luận Phase 1. Nhóm mong Thầy góp ý về việc duyệt W66 trên cùng tập câu hỏi, cập nhật protocol/mốc thời gian và điều kiện mở giai đoạn huấn luyện.

### Ghi lại sau buổi trao đổi

- Trọng tâm/tên đề tài được thống nhất: …
- Phạm vi dữ liệu và sản phẩm bắt buộc: …
- Protocol và tiêu chí đánh giá cần giữ hoặc điều chỉnh: …
- Việc ưu tiên tiếp theo, người phụ trách và hạn hoàn thành: …
- Mốc báo cáo tiếp theo với giảng viên: …

## Tài liệu đối chiếu trong repo

- [Đề xuất nghiên cứu](DE_XUAT_NGHIEN_CUU_QPAF.md): động lực, phương pháp, đóng góp dự kiến và nghiên cứu liên quan.
- [Tổng quan dự án](PROJECT_OVERVIEW.md): kiến trúc, dữ liệu và giới hạn bằng chứng hiện tại.
- [Thiết kế chi tiết](Context.md): mô hình tối thiểu, giả định và tiêu chí đánh giá.
- [Nhiệm vụ và cổng quyết định](Tasks.md): nguồn đối chiếu trạng thái P1-02, P1-02R và các bước tiếp theo.

Tài liệu này phục vụ trao đổi định hướng; không thay thế đề cương, không sửa protocol và không ghi nhận thêm kết quả thực nghiệm.
