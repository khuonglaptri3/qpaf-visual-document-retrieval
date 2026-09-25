# Tóm tắt định hướng đề tài QPAF

Dạ em chào Thầy ạ. Nhóm em xin tóm tắt định hướng đề tài và kính mong Thầy góp ý về tính khả thi của hướng nghiên cứu này ạ.

**Tên đề tài:** Adaptive Retrieval Fusion for Visually Rich Document RAG

**Cơ sở nghiên cứu:** Đề tài kế thừa các công trình tiêu biểu về Visual RAG và Multimodal Document Retrieval như ColPali, VisRAG, với phạm vi thực nghiệm gồm ViDoSeek, ViMDoc và ViDoRe V3. Về phương pháp dung hợp thích ứng, nhóm sử dụng **Multi-Field Adaptive Retrieval (mFAR, ICLR 2025)** làm nền tảng kiến trúc chính và **Dynamic Alpha Tuning (DAT)** làm phương pháp đối chiếu gần nhất ở mức thích ứng theo câu hỏi.

mFAR kết hợp nhiều scorer bằng một module sinh trọng số nhẹ. Với mỗi câu hỏi, mô hình dùng biểu diễn của câu hỏi để tạo trọng số cho từng cặp field–scorer thông qua một phép chiếu tuyến tính và softmax:

$$
G(q,f,m)
=
\frac{
\exp\!\left(({\boldsymbol a}_{f}^{m})^{\top}{\boldsymbol e}_{q}\right)
}{
\displaystyle
\sum_{f'\in\mathcal F}
\sum_{m'\in\mathcal M}
\exp\!\left(({\boldsymbol a}_{f'}^{m'})^{\top}{\boldsymbol e}_{q}\right)
}.
$$

Điểm truy xuất cuối cùng là tổng có trọng số của các điểm lexical và dense:

$$
S(q,d)
=
\sum_{f\in\mathcal F}
\sum_{m\in\mathcal M}
G(q,f,m)\,s_f^m(q,x_f).
$$

Kiến trúc này phù hợp với đề tài vì hỗ trợ nhiều scorer, có bước xử lý sự khác biệt về thang điểm và chỉ bổ sung một module tạo trọng số nhỏ. Tuy nhiên, mFAR chỉ sinh trọng số theo câu hỏi, được thiết kế cho tài liệu bán cấu trúc gồm nhiều field và có fine-tune dense encoder trong thí nghiệm gốc. Vì vậy, nhóm không áp dụng nguyên bản mFAR mà mở rộng kiến trúc theo bài toán tài liệu trực quan ở mức từng cặp câu hỏi–trang.

**Hạn chế hiện tại:** BM25, Dense-text Retrieval và Visual Retrieval có thế mạnh khác nhau. Độ tin cậy của từng kênh không chỉ thay đổi theo câu hỏi mà còn có thể khác nhau giữa các trang ứng viên của cùng một câu hỏi. Một bộ trọng số cố định hoặc một bộ trọng số chung cho toàn bộ trang của một câu hỏi có thể chưa khai thác đầy đủ tính bổ trợ giữa các retriever.

**Đề xuất của nhóm:**

- Xây dựng phương pháp **Query-Page-Adaptive Fusion (QPAF)** bằng cách mở rộng bộ sinh trọng số của mFAR từ $G(q,f,m)$ thành $G(q,p,m)$, trong đó $p$ là một trang ứng viên và $m$ là một kênh truy xuất.
- Kết hợp ba kênh truy xuất gồm BM25, Dense-text Retriever và Visual Retriever.
- Tạo tập ứng viên bằng cách hợp nhất top-$K$ của ba retriever, sau đó áp dụng QPAF để tính lại điểm và xếp hạng các trang ứng viên.
- Chuẩn hóa điểm từ từng retriever trước khi dung hợp nhằm xử lý sự khác biệt về phân phối và thang điểm.
- Sử dụng đặc trưng câu hỏi và tín hiệu của từng trang ứng viên, chẳng hạn điểm đã chuẩn hóa, thứ hạng, score margin và mức độ bất đồng giữa các retriever.
  **Công thức QPAF:** Với vector đặc trưng $\boldsymbol x_{q,p}$ của cặp câu hỏi–trang, linear layer hoặc shallow MLP $g(\cdot)$ tạo ba logit:

$$
\boldsymbol z(q,p)
=
g\!\left(\boldsymbol x_{q,p}\right)
\in
\mathbb R^3.
$$

Ba trọng số fusion được chuẩn hóa bằng softmax:

$$
\begin{bmatrix}
w_B(q,p) \\
w_D(q,p) \\
w_V(q,p)
\end{bmatrix}
=
\operatorname{softmax}\!\left(\boldsymbol z(q,p)\right),
\qquad
w_B(q,p)+w_D(q,p)+w_V(q,p)=1.
$$

Điểm QPAF của trang $p$ đối với câu hỏi $q$ là:

$$
S_{\mathrm{QPAF}}(q,p)
=
w_B(q,p)\,\hat{s}_B(q,p)
+
w_D(q,p)\,\hat{s}_D(q,p)
+
w_V(q,p)\,\hat{s}_V(q,p).
$$

- Giữ BM25, Dense-text Retriever và Visual Retriever ở trạng thái frozen; chỉ huấn luyện module QPAF nhằm giảm chi phí tính toán và giúp xác định rõ phần cải thiện đến từ cơ chế fusion.
- So sánh QPAF với BM25, Dense, Visual, RRF, Fixed Weighted Fusion, DAT và một phương pháp Query-Adaptive Fusion dùng chung trọng số cho mọi trang của cùng câu hỏi.
- Đánh giá bằng nDCG@10, Recall@K, MRR và chi phí suy luận của module fusion.
- Thực hiện discovery ở mức trang trên ViDoSeek, confirmation theo protocol document-level của HEAVEN trên ViMDoc (QPAF vẫn tính trọng số theo trang rồi lấy điểm trang lớn nhất cho mỗi tài liệu), và đánh giá ngoài miền ở mức trang trên ViDoRe V3 đã niêm phong; MMDocIR và các tập VQA tiếng Việt nằm ngoài phạm vi thực nghiệm hiện tại.

**Đóng góp dự kiến:** Đề tài mở rộng cơ chế adaptive weighting đa scorer của mFAR từ mức câu hỏi sang mức từng cặp câu hỏi–trang, đồng thời bổ sung kênh Visual Retrieval và giữ cố định các retriever nền. Kết quả dự kiến là một module QPAF nhẹ có khả năng điều chỉnh mức đóng góp của BM25, Dense và Visual Retrieval cho từng trang ứng viên.

Nhóm em kính mong Thầy góp ý về tính khả thi, phạm vi thực nghiệm và mức độ phù hợp của hướng QPAF đối với đề tài ạ. Nhóm em cảm ơn Thầy nhiều ạ.
