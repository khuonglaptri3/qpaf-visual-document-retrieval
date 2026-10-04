# Tóm tắt QPAF để trao đổi với giảng viên

> Mục tiêu của tài liệu này: giúp hiểu ý tưởng cốt lõi của dự án trong khoảng 5–7 phút và trình bày trung thực trạng thái hiện tại. Đây không phải báo cáo kết quả nghiên cứu hoàn chỉnh.

## 1. Dự án này làm gì?

Dự án nghiên cứu **Query-Page-Adaptive Fusion (QPAF)** cho bài toán tìm kiếm trang tài liệu trong hệ thống Visual RAG.

Khi người dùng đặt câu hỏi, hệ thống cần tìm đúng những trang PDF có bằng chứng để mô hình phía sau đọc và trả lời. Một trang có thể được tìm thấy nhờ:

- từ khóa chính xác trong văn bản;
- ý nghĩa tương đồng dù dùng từ khác;
- bảng, biểu đồ, bố cục hoặc nội dung trực quan.

Vì không có một cách tìm kiếm nào luôn tốt nhất, dự án kết hợp ba kênh:

| Kênh | Hiểu đơn giản | Điểm mạnh chính |
| --- | --- | --- |
| **BM25** | Tìm theo từ khóa | Tốt khi câu hỏi và tài liệu dùng từ giống nhau |
| **BGE-M3** | Tìm theo ngữ nghĩa văn bản | Tốt khi hai câu diễn đạt khác nhau nhưng cùng ý |
| **ColQwen2.5** | Tìm trực tiếp trên hình ảnh của trang | Tốt với bảng, biểu đồ và bố cục khó biểu diễn bằng văn bản |

QPAF không thay thế ba bộ tìm kiếm này. Nó là một lớp nhẹ đứng phía sau, nhận điểm của cả ba kênh rồi quyết định nên tin kênh nào nhiều hơn cho từng trang.

## 2. Ý tưởng mới nằm ở đâu?

Có bốn mức kết hợp điểm cần so sánh:

1. **Global fusion:** dùng một bộ trọng số cố định cho mọi câu hỏi và mọi trang.
2. **QARF:** mỗi câu hỏi có một bộ trọng số, nhưng mọi trang của câu hỏi đó dùng chung trọng số.
3. **CARF:** mỗi nhóm trang ứng viên có một bộ trọng số; đây là phương án trung gian đang được đề xuất để chẩn đoán.
4. **QPAF:** mỗi cặp câu hỏi–trang có một bộ trọng số riêng.

Ví dụ, với câu hỏi “Doanh thu năm 2025 tăng bao nhiêu?”, một trang văn bản có thể cần BM25 hoặc BGE-M3, trong khi trang chứa biểu đồ có thể cần ColQwen2.5. QPAF muốn điều chỉnh trọng số ở cấp từng trang thay vì dùng một lựa chọn chung cho cả câu hỏi.

Công thức trực giác là:

```text
điểm cuối = trọng số từ khóa × điểm BM25
           + trọng số ngữ nghĩa × điểm BGE-M3
           + trọng số hình ảnh × điểm ColQwen2.5
```

Ba trọng số cộng lại bằng 1. Các retriever nền được giữ cố định; nếu dự án đi tiếp, chỉ module dự đoán trọng số được huấn luyện.

## 3. Câu hỏi nghiên cứu thật sự

Câu hỏi không phải chỉ là “QPAF có chạy được không?”, mà là:

> Việc chọn trọng số riêng cho từng trang có tạo ra cải thiện ổn định và đủ lớn so với cách đơn giản hơn như Global fusion hoặc QARF không?

Đây là câu hỏi có thể bị bác bỏ. Nếu QARF đã đạt gần hết lợi ích, nên chọn QARF vì đơn giản hơn thay vì cố bảo vệ QPAF.

Đóng góp dự kiến của đề tài là mở rộng tư tưởng adaptive fusion từ mức câu hỏi sang mức câu hỏi–trang, bổ sung kênh tìm kiếm trực quan, và kiểm tra xem mức thích ứng chi tiết đó có thực sự cần thiết hay không. Tuy nhiên, **tính mới và mức đóng góp đủ cho khóa luận vẫn cần giảng viên đánh giá**.

## 4. Dữ liệu và cách đánh giá

Dự án dự kiến dùng ba tập dữ liệu theo ba vai trò khác nhau:

- **ViDoSeek:** tập discovery chính, gồm 1.142 câu hỏi và 5.385 trang đã chuẩn bị.
- **ViMDoc:** tập confirmation; QPAF vẫn chấm điểm từng trang nhưng đánh giá ở mức tài liệu.
- **ViDoRe V3 Finance EN:** tập external validation được giữ riêng để kiểm tra khả năng khái quát.

Chỉ số chính là **nDCG@10**, đo xem các trang liên quan có được xếp đúng và đủ cao trong 10 kết quả đầu hay không. Chỉ số phụ gồm Recall@1, Recall@3 và MRR@10. Nếu có mô hình học, dự án còn phải đo độ trễ và bộ nhớ, không chỉ đo chất lượng.

## 5. Hiện tại đã làm được gì?

Các phần nền tảng đã có bằng chứng kiểm tra:

- phiên bản dữ liệu, mô hình và môi trường đã được cố định bằng cấu hình/hash;
- pipeline tạo điểm BM25, dense và visual cùng các kiểm tra schema, khóa, thứ hạng và độ phủ đã được xây dựng;
- công thức chuẩn hóa điểm và các metric đã có kiểm thử;
- bundle ViDoSeek hậu kiểm **P1-02R** đã được xác minh: 1.142 câu hỏi × 5.385 trang = 6.149.670 cặp, độ phủ 1,0 và không có câu hỏi mất trang liên quan;
- wrapper W7 chạy theo từng query, có checkpoint/resume và kiểm tra tương đương với cách chạy nguyên khối, đã được chuẩn bị;
- calibration CPU tổng hợp trên 1 query × 5.385 trang đã hoàn tất trong 752,800 giây; đây chỉ là bằng chứng kỹ thuật về thời gian chạy;
- audit bảy profile W7 cố định trên toàn bộ 1.142 câu hỏi đã được kiểm tra độc lập: Global đạt 0,875138 và QARF đạt 0,908268 nDCG@10; cận trên lý thuyết còn lại cho QPAF là 0,091732;
- thí nghiệm oracle W7 thăm dò trên 24 câu hỏi bổ sung đạt Global/QARF/QPAF lần lượt 0,817634/0,853845/0,903856. Mức QPAF trừ QARF là 0,050011, khoảng bootstrap 95% [0,008344; 0,101921], nhưng đây vẫn chỉ là tập con thăm dò.

Những điều **chưa được phép nói là đã hoàn thành**:

- chưa có W66 hoặc kết quả W7 toàn bộ discovery đủ để ra quyết định Phase 1 chính thức;
- chưa có learned QPAF hoặc learned QARF;
- chưa có benchmark ba seed, ablation hoặc external validation hoàn chỉnh;
- chưa có kết quả QPAF có thể triển khai thực tế;
- các con số baseline hiện có trên ViDoRe chỉ là candidate-pool validation, không phải kết quả cuối toàn corpus.

## 6. Vì sao tiến độ đang bị chặn?

Thí nghiệm gốc **P1-02** tạo tập ứng viên bằng top-K của ba retriever. Sau lần mở rộng được quy định trước, vẫn còn một câu hỏi không chứa trang liên quan trong tập ứng viên. Vì vậy P1-02 được giữ trạng thái **BLOCKED**; dự án không được xóa câu hỏi lỗi, chèn thủ công đáp án hoặc đổi ngưỡng sau khi nhìn nhãn.

P1-02R là một nhánh hậu kiểm riêng: chấm điểm toàn bộ 5.385 trang cho mỗi câu hỏi để loại bỏ lỗi thiếu ứng viên. Bundle điểm của nhánh này đã được xác minh và đã hỗ trợ các khảo sát oracle thăm dò, nhưng nó **không biến P1-02 thành PASS** và các khảo sát đó không phải kết quả Phase 1 chính thức hay hiệu năng của mô hình có thể triển khai.

Trạng thái chính xác ngày 08/09/2026:

- calibration tổng hợp một lần đã hoàn tất và quyền chạy đã được sử dụng hết; không được chạy lại;
- audit fixed-profile và exploratory-24 W7 đã hoàn tất, được kiểm tra độc lập và chỉ cung cấp bằng chứng hậu kiểm/thăm dò;
- full-discovery W7 chưa được cho phép chạy;
- P1-03/W66 và toàn bộ giai đoạn huấn luyện vẫn bị chặn.

Vì vậy, kết luận trung thực là: **QPAF có tín hiệu oracle thăm dò đáng để kiểm tra tiếp, nhưng giả thuyết chưa được chứng minh theo protocol Phase 1 chính thức và chưa có mô hình learned QPAF**.

## 7. Đoạn trình bày khoảng 60 giây

> Dạ, đề tài của em nghiên cứu cách tìm đúng trang bằng chứng trong tài liệu có nhiều bảng, biểu đồ và bố cục phức tạp. Em đề xuất QPAF để kết hợp BM25, BGE-M3 và ColQwen2.5 bằng trọng số thay đổi theo từng cặp câu hỏi–trang, thay vì chỉ thay đổi theo câu hỏi như QARF. Trên 24 câu hỏi ViDoSeek bổ sung được chọn trước, oracle W7 cho mức QPAF trừ QARF là 0,050011 nDCG@10, với khoảng bootstrap 95% từ 0,008344 đến 0,101921. Đây là tín hiệu thăm dò, chưa phải mô hình đã học hay quyết định Phase 1 chính thức. Thí nghiệm P1-02 gốc vẫn bị chặn bởi protocol ứng viên; em muốn xin Thầy/Cô góp ý về việc có nên duyệt protocol W66 trên cùng 24 câu hỏi, cập nhật mốc thời gian và sau đó mới quyết định có mở hướng learned QPAF hay không.

## 8. Các câu nên hỏi giảng viên

1. Câu hỏi nghiên cứu “thích ứng theo từng trang so với theo từng câu hỏi” có đủ rõ và có giá trị cho khóa luận không?
2. Mức khác biệt giữa QPAF với mFAR, DAT và các phương pháp fusion hiện có có đủ tạo thành đóng góp mới không?
3. Có chấp nhận kết quả W7 trên P1-02R như bằng chứng thăm dò riêng, giữ P1-02 là BLOCKED, và duyệt bước W66 trên đúng 24 câu hỏi đã cố định không?
4. Có cần cả ba tập ViDoSeek, ViMDoc và ViDoRe V3, hay nên thu hẹp để phù hợp thời gian và tài nguyên?
5. Nên đặt tiêu chí “đủ tốt để đi tiếp” ở mức nào cho nDCG@10, độ tin cậy thống kê, độ trễ và bộ nhớ?
6. Nếu QPAF không hơn QARF, kết luận chọn mô hình đơn giản hơn có được xem là một kết quả nghiên cứu hợp lệ không?
7. Giảng viên muốn sản phẩm cuối là nghiên cứu retrieval độc lập hay phải có thêm demo Visual RAG hỏi–đáp hoàn chỉnh?

## 9. Năm điều cần nhớ

- Bài toán chính là **xếp hạng trang bằng chứng**, chưa phải sinh câu trả lời cuối.
- QPAF kết hợp **BM25 + BGE-M3 + ColQwen2.5**.
- Điểm khác biệt chính là **trọng số thay đổi theo từng trang**.
- Repo đã có nền tảng và dữ liệu điểm đáng kể, nhưng **chưa có kết quả learned QPAF**.
- Mục tiêu của buổi gặp là xin quyết định về **tính mới, phạm vi và protocol tiếp tục**, không phải trình bày rằng đề tài đã thành công.

## 10. Nên đọc gì nếu còn thời gian?

- `PROJECT_OVERVIEW.md`: tổng quan chính thức về bài toán, kiến trúc và dữ liệu.
- `PROJECT_TRACKING.md`: bảng trạng thái ngắn theo từng giai đoạn.
- `docs/HUONG_DAN_HIEU_DU_AN_QPAF.md`: bản giải thích tiếng Việt chi tiết hơn.
- `Tasks.md`: nguồn chính xác nhất về dependency, trạng thái PASS/BLOCKED và điều kiện dừng; chỉ cần tra khi giảng viên hỏi sâu.
