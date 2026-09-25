# ĐỀ XUẤT NGHIÊN CỨU

## Adaptive Retrieval Fusion for Visually Rich Document RAG

**Tên tiếng Việt:** Dung hợp truy xuất thích ứng cho hệ thống RAG trên tài liệu giàu thông tin trực quan\
**Giảng viên hướng dẫn:** Hoàng Văn Dũng\
**Sinh viên thực hiện:**

- Trần Đình Khương — 23110035
- Trần Huỳnh Xuân Thanh — 23110060
- Bùi Trần Tấn Phát — 23110052

**Trạng thái tài liệu:** Đề xuất nghiên cứu; chưa triển khai đầy đủ và chưa có kết quả learned fusion được kiểm chứng trong repo. Các đóng góp và mức cải thiện được trình bày dưới dạng giả thuyết cần kiểm chứng.

**Cập nhật bằng chứng Oracle:** repo đã nhận [báo cáo Oracle trên ViDoSeek](../results/m1.1/README.md). Đây là số liệu được cung cấp, còn chờ đối chiếu artifact từng query; không thay thế kết quả learned QPAF.

---

## 1. Tóm tắt đề xuất

Tài liệu giàu thông tin trực quan như báo cáo, biểu mẫu, hóa đơn, slide, bảng biểu và infographic truyền tải nội dung không chỉ qua văn bản mà còn qua bố cục, hình ảnh và quan hệ không gian. Vì vậy, một hệ thống Retrieval-Augmented Generation (RAG) chỉ dựa trên một kênh truy xuất có thể bỏ sót tín hiệu hữu ích. BM25 phù hợp với truy vấn chứa từ khóa chính xác; dense-text retrieval hỗ trợ đối sánh ngữ nghĩa; còn visual retrieval có khả năng khai thác trực tiếp hình ảnh trang và các yếu tố bố cục.

Đề tài đề xuất **Query-Page-Adaptive Fusion (QPAF)**, một module dung hợp nhẹ sinh trọng số riêng cho từng cặp câu hỏi–trang ứng viên. QPAF kết hợp điểm từ ba kênh BM25, dense-text và visual retrieval sau khi chuẩn hóa, trong khi giữ cố định các retriever nền. Thiết kế này nhằm kiểm tra một giả thuyết hẹp: mức độ hữu ích của từng kênh không chỉ thay đổi giữa các câu hỏi mà còn có thể thay đổi giữa các trang ứng viên của cùng một câu hỏi.

Nghiên cứu được thực hiện theo các cổng quyết định. Trước hết, nhóm đo chất lượng và tính bổ trợ của ba retriever. Tiếp theo, nhóm dùng oracle trên tập trọng số được định nghĩa trước để đo trần tiềm năng của dung hợp ở mức toàn cục, câu hỏi, cụm ứng viên và cặp câu hỏi–trang. Chỉ khi oracle cho thấy headroom đủ rõ, nhóm mới huấn luyện bộ dự đoán trọng số. Cách tổ chức này giúp tách biệt **khả năng tồn tại của tín hiệu dung hợp** với **khả năng học và triển khai tín hiệu đó**.

## 2. Bối cảnh và động lực

ColPali cho thấy có thể biểu diễn trực tiếp ảnh trang tài liệu bằng các embedding đa vector và đối sánh truy vấn–trang bằng late interaction [1]. VisRAG tiếp tục đặt visual retrieval trong một pipeline RAG đa phương thức, giảm phụ thuộc vào việc chuyển toàn bộ tài liệu thành văn bản trước khi truy xuất [2]. Hai hướng này cho thấy kênh thị giác có giá trị riêng, nhưng không làm cho kênh lexical hoặc dense-text trở nên dư thừa trong mọi loại truy vấn.

Ở hướng dung hợp thích ứng, Multi-Field Adaptive Retrieval (mFAR) học trọng số của nhiều field và scorer dựa trên biểu diễn câu hỏi [3]. Dynamic Alpha Tuning (DAT) cũng điều chỉnh mức kết hợp dense–BM25 theo từng truy vấn [4]. Các phương pháp này tạo cơ sở cho **Query-Adaptive Retrieval Fusion (QARF)**: một câu hỏi có một bộ trọng số dùng chung cho tất cả trang ứng viên.

Khoảng trống mà đề tài kiểm tra là mức thích ứng chi tiết hơn. Với cùng một câu hỏi, một trang có thể nổi bật nhờ từ khóa OCR, một trang khác nhờ tương đồng ngữ nghĩa, và một trang khác nhờ bố cục hoặc nội dung hình ảnh. Nếu dùng một vector trọng số duy nhất cho toàn bộ câu hỏi, hệ thống có thể không phản ánh được sự khác biệt đó. Tuy nhiên, QPAF chỉ có ý nghĩa nếu headroom ở mức trang vượt rõ ràng headroom ở mức câu hỏi và nếu một bộ dự đoán không dùng nhãn tại thời điểm suy luận có thể học được sự khác biệt này.

## 3. Vấn đề nghiên cứu

Cho truy vấn $q$, tập trang $\mathcal{P}$ và ba retriever $m\in\mathcal{M}=\{B,D,V\}$ tương ứng với BM25, dense-text và visual retrieval, mỗi retriever sinh điểm thô $s_m(q,p)$. Do thang đo và phân phối điểm khác nhau, không thể cộng trực tiếp các điểm này một cách có kiểm soát.

Sau khi chuẩn hóa bằng một phép biến đổi được cố định theo protocol,

$$
\hat{s}_m(q,p)=\operatorname{Norm}_m\!\left(s_m(q,p);\mathcal{C}_q\right),
$$

trong đó $\mathcal{C}_q$ là tập ứng viên được tạo mà không sử dụng qrels, phương pháp dung hợp tính:

$$
S(q,p)=\sum_{m\in\mathcal{M}}w_m(q,p)\hat{s}_m(q,p),
\qquad
w_m(q,p)\ge 0,
\qquad
\sum_{m\in\mathcal{M}}w_m(q,p)=1.
$$

Vấn đề trung tâm là xác định mức chi tiết thích hợp của $w$:

- **Global Fusion:** $w_m$, dùng chung cho mọi câu hỏi và trang.
- **QARF:** $w_m(q)$, một bộ trọng số cho mỗi câu hỏi.
- **CARF:** $w_m(q,c)$, một bộ trọng số cho mỗi cụm trang ứng viên $c$ của câu hỏi.
- **QPAF:** $w_m(q,p)$, một bộ trọng số cho từng cặp câu hỏi–trang.

CARF được dùng như mức chẩn đoán trung gian giữa QARF và QPAF. Nó không thay thế đóng góp chính của đề tài nhưng giúp kiểm tra liệu mức thích ứng theo trang có thực sự cần thiết hay tín hiệu chủ yếu chỉ thay đổi theo các nhóm ứng viên.

## 4. Câu hỏi và giả thuyết nghiên cứu

### RQ1 — Các retriever có bổ trợ cho nhau không?

BM25, dense-text và visual retrieval có tìm đúng các trang liên quan trên những tập truy vấn khác nhau hoặc tạo ra các lỗi khác nhau hay không?

**H1:** Không có một retriever đơn lẻ thống trị trên mọi truy vấn; hợp của các tập top-$K$ tạo recall ceiling cao hơn từng kênh riêng. Nếu giả thuyết này không được hỗ trợ, nhóm dừng hướng adaptive fusion và tập trung vào retriever mạnh nhất.

### RQ2 — Thích ứng theo câu hỏi có tạo headroom so với trọng số toàn cục không?

**H2:** QARF oracle đạt mean per-query nDCG@10 cao hơn Global oracle dưới cùng candidate pool, phép chuẩn hóa và tập trọng số. Kết quả oracle chỉ là trần trên sử dụng qrels, không phải hiệu năng có thể triển khai.

### RQ3 — Mức cụm hoặc mức trang có tạo thêm headroom không?

**H3:** CARF hoặc QPAF oracle tạo headroom bổ sung so với QARF trên một tỷ lệ truy vấn đủ lớn, thay vì mức tăng trung bình chỉ đến từ một số ít ngoại lệ. Nếu QPAF không vượt QARF một cách có ý nghĩa thực tiễn, nhóm chọn QARF đơn giản hơn.

### RQ4 — Có thể học trọng số thích ứng mà không dùng qrels khi suy luận không?

**H4:** Bộ dự đoán QARF/CARF/QPAF học từ train split có thể cải thiện so với fixed fusion trên validation và test dưới protocol cố định. Hiệu quả phải được báo cáo cùng độ bất định, chi phí suy luận và số seed; oracle headroom không được dùng thay cho kết quả này.

## 5. Phương pháp đề xuất

### 5.1 Ba kênh truy xuất nền

1. **BM25:** lập chỉ mục văn bản OCR hoặc Markdown của từng trang; đây là retriever thống kê, không phải mô hình pretrained.
2. **Dense-text retriever:** mã hóa truy vấn và văn bản trang vào không gian vector để đối sánh ngữ nghĩa.
3. **Visual retriever:** mã hóa trực tiếp ảnh trang và đối sánh với truy vấn văn bản, ưu tiên một mô hình tài liệu trực quan hỗ trợ chấm điểm ở mức trang.

Ba kênh được đóng băng trong thí nghiệm learned fusion. Việc cố định retriever giảm chi phí huấn luyện và giúp quy phần thay đổi kết quả cho cơ chế fusion. Score extraction là bước ngoại tuyến riêng; sau khi ba bảng điểm được lưu và kiểm tra, oracle và module fusion có thể chạy trên score cache với chi phí thấp hơn đáng kể.

### 5.2 Tạo tập ứng viên

Với mỗi truy vấn, hệ thống lấy top-$K_c$ từ từng retriever và tạo hợp:

$$
\mathcal{C}_q=
\operatorname{Top}_{K_c}^{B}(q)
\cup
\operatorname{Top}_{K_c}^{D}(q)
\cup
\operatorname{Top}_{K_c}^{V}(q).
$$

Candidate generation không sử dụng qrels. Với trang không xuất hiện trong top-$K_c$ của một kênh, cách gán điểm thiếu phải được định nghĩa trước và áp dụng giống nhau cho mọi phương pháp. Nhóm sẽ đánh giá candidate recall để bảo đảm fusion không bị giới hạn bởi một pool quá hẹp.

### 5.3 Chuẩn hóa điểm

Phép chuẩn hóa được fit hoặc tính mà không dùng test qrels. Cấu hình ban đầu là min–max theo từng truy vấn và từng kênh trên cùng candidate pool:

$$
\hat{s}_m(q,p)=
\frac{s_m(q,p)-\min_{p'\in\mathcal{C}_q}s_m(q,p')}
{\max_{p'\in\mathcal{C}_q}s_m(q,p')-
 \min_{p'\in\mathcal{C}_q}s_m(q,p')+\varepsilon}.
$$

Nhóm phải kiểm tra trường hợp biên có range bằng không và thực hiện sensitivity analysis với ít nhất một phép chuẩn hóa thay thế. Toàn bộ baseline và biến thể adaptive phải dùng cùng một score table và cùng protocol chuẩn hóa.

### 5.4 Oracle headroom

Thí nghiệm oracle đầu tiên sử dụng tập trọng số nhỏ $W_7$ để có thể tìm kiếm vét cạn và kiểm tra chính xác:

$$
W_7=
\left\{
(1,0,0),(0,1,0),(0,0,1),
\left(\tfrac13,\tfrac13,\tfrac13\right),
\left(\tfrac12,\tfrac12,0\right),
\left(\tfrac12,0,\tfrac12\right),
\left(0,\tfrac12,\tfrac12\right)
\right\}.
$$

Nếu $W_7$ cho thấy headroom, nhóm mở rộng sang lưới simplex $W_{66}$ theo kế hoạch được tiền đăng ký. Global, QARF, CARF và QPAF phải dùng cùng tập trọng số. Qrels chỉ được dùng sau khi candidate pool, score normalization và—đối với CARF—các cụm đã được cố định. Do QPAF oracle có nhiều quyền lựa chọn hơn, quan hệ QPAF oracle $\ge$ QARF oracle $\ge$ Global oracle là hệ quả của không gian tìm kiếm; giá trị nghiên cứu nằm ở **độ lớn, độ phủ và độ ổn định của headroom**, không nằm ở riêng thứ tự này.

### 5.5 Module QPAF học được

Với vector đặc trưng $\boldsymbol{x}_{q,p}$ của cặp câu hỏi–trang, linear layer hoặc shallow MLP $g_\theta$ sinh ba logit:

$$
\boldsymbol{z}(q,p)=g_\theta(\boldsymbol{x}_{q,p})\in\mathbb{R}^{3},
$$

$$
\boldsymbol{w}(q,p)=\operatorname{softmax}\!\left(\boldsymbol{z}(q,p)\right).
$$

Điểm cuối cùng là:

$$
S_{\mathrm{QPAF}}(q,p)
=
w_B(q,p)\hat{s}_B(q,p)
+w_D(q,p)\hat{s}_D(q,p)
+w_V(q,p)\hat{s}_V(q,p).
$$

Nhóm đặc trưng ban đầu được giới hạn ở các tín hiệu sẵn có tại thời điểm suy luận:

- điểm đã chuẩn hóa và thứ hạng của từng retriever;
- score margin và độ dốc điểm trong danh sách ứng viên;
- mức đồng thuận hoặc bất đồng giữa ba retriever;
- đặc trưng độ dài và loại truy vấn;
- biểu diễn truy vấn và, nếu ngân sách cho phép, biểu diễn trang đã được cache.

Không đưa qrels, oracle profile, thống kê từ test split hoặc đặc trưng được suy ra từ nhãn vào đầu vào mô hình. Hàm mất mát xếp hạng và chiến lược negative sampling sẽ được chọn trên train/validation, ghi rõ trước khi đánh giá test, và được giữ giống nhau khi so sánh QARF, CARF và QPAF.

## 6. Thiết kế thực nghiệm

### 6.1 Trình tự dataset

Trình tự dự kiến từ nghiên cứu khám phá đến kiểm chứng ngoài miền:

1. **ViDoSeek Discovery:** thí nghiệm bổ trợ retriever và oracle ban đầu.
2. **ViMDoc Confirmation:** xác nhận trên tập truy vấn lớn hơn bằng protocol document-level của HEAVEN. Module QPAF vẫn sinh trọng số và điểm cho từng trang; sau đó bỏ đoạn cuối sau dấu gạch dưới để ánh xạ trang sang tài liệu, lấy điểm trang lớn nhất làm điểm tài liệu, và tính loss/metric trên qrels tài liệu. Mẫu phát triển 2.000 truy vấn được chọn bằng SHA-256 chỉ từ query ID, không dùng nhãn.
3. **ViDoRe V3:** benchmark ngoài để đánh giá khả năng khái quát; không dùng cùng test qrels để chọn trọng số hoặc đặc trưng.

Phạm vi thực nghiệm hiện tại chỉ gồm ba dataset trên. MMDocIR, ViOCRVQA và ReceiptVQA được giữ cho hướng mở rộng sau luận văn và không thuộc các cổng thực nghiệm hoặc bảng kết quả chính.

Dataset revision, split và quy tắc nhóm các biến thể dịch phải được cố định trước thí nghiệm. Qrels không tham gia candidate generation, normalization, clustering hoặc feature construction.

### 6.2 Baseline

- BM25 độc lập;
- dense-text retriever độc lập;
- visual retriever độc lập;
- Reciprocal Rank Fusion (RRF);
- fixed weighted fusion, trọng số chọn trên validation;
- Global fusion oracle, chỉ báo cáo như upper bound;
- QARF: một bộ trọng số học được cho mỗi câu hỏi;
- CARF: biến thể chẩn đoán theo cụm ứng viên;
- QPAF: một bộ trọng số học được cho mỗi cặp câu hỏi–trang;
- DAT, nếu có thể tái lập dưới cùng candidate pool và protocol;
- mFAR chỉ được dùng như baseline trực tiếp nếu việc chuyển đổi từ field–scorer sang ba kênh retrieval được định nghĩa và triển khai công bằng; nếu không, mFAR được giữ ở vai trò nền tảng kiến trúc.

### 6.3 Chỉ số đánh giá

**Chỉ số chính:** mean per-query nDCG@10.\
**Chỉ số phụ:** Recall@1, Recall@3 và MRR@10.\
**Chỉ số hệ thống:** latency của fusion theo truy vấn, throughput, kích thước module và bộ nhớ tăng thêm.\
**Chỉ số phân tích:** candidate recall, oracle gain coverage, tỷ lệ truy vấn được cải thiện/suy giảm và phân bố gain theo loại truy vấn.

Mọi so sánh learned fusion phải báo cáo nhiều seed hoặc nêu rõ single-seed. Chênh lệch giữa hai phương pháp được đánh giá bằng bootstrap theo truy vấn với khoảng tin cậy, bên cạnh ngưỡng hiệu quả thực tiễn $\delta$ được chốt trước khi mở kết quả test.

### 6.4 Ablation và kiểm tra độ bền

- bỏ lần lượt BM25, dense hoặc visual channel;
- chỉ dùng score/rank so với thêm query/page features;
- linear gating so với shallow MLP;
- QARF so với CARF và QPAF dưới cùng ngân sách tham số;
- $W_7$ so với $W_{66}$ trong oracle study;
- độ nhạy theo candidate depth $K_c$;
- min–max so với phép chuẩn hóa thay thế;
- chi phí online khi score cache đã có, tách khỏi chi phí offline của từng retriever.

## 7. Cổng quyết định và tiêu chí dừng

| Giai đoạn | Bằng chứng cần có | Quyết định |
|---|---|---|
| 1. Baseline | Score table hợp lệ; metric khớp kiểm tra tay; candidate recall; lỗi bổ trợ giữa ba kênh | Dừng adaptive fusion nếu một kênh thống trị và union không tăng headroom |
| 2. Oracle $W_7$ | Global, QARF và QPAF trên cùng protocol; gain, coverage và bootstrap CI | Dừng nếu không có headroom; chọn QARF nếu page-level gain không đáng kể |
| 3. CARF | QARF–CARF–QPAF oracle, qrels không tham gia clustering | Chọn mức đơn giản nhất giữ phần lớn headroom |
| 4. Learned fusion | Nhiều seed; validation/test tách biệt; latency và ablation | Chỉ tuyên bố cải thiện khi learned model, không phải oracle, vượt baseline dưới protocol giống nhau |
| 5. External/Vietnamese | Dataset và qrels được đóng băng; không tuning trên test | Giới hạn kết luận theo ngôn ngữ và miền thực sự đã đánh giá |

## 8. Đóng góp dự kiến

Nếu các giả thuyết được thực nghiệm hỗ trợ, đề tài dự kiến đóng góp:

1. Một formulation thống nhất cho dung hợp BM25, dense-text và visual retrieval ở bốn mức Global–QARF–CARF–QPAF.
2. Một oracle study có kiểm soát để đo khi nào thích ứng theo câu hỏi, cụm hoặc trang tạo headroom, tách biệt khỏi hiệu năng triển khai.
3. Một module QPAF nhẹ, giữ frozen các retriever nền và dự đoán trọng số riêng cho từng cặp câu hỏi–trang.
4. Phân tích về tính bổ trợ, độ phủ cải thiện, chi phí và điều kiện thất bại của adaptive retrieval fusion trên tài liệu giàu thông tin trực quan.
5. Một protocol đánh giá có cổng dừng, hạn chế leakage và phân biệt rõ external validation với đánh giá tài liệu tiếng Việt.

Đây là các **đóng góp dự kiến**, không phải kết quả đã được chứng minh.

## 9. Rủi ro và phương án xử lý

| Rủi ro | Ảnh hưởng | Kiểm soát |
|---|---|---|
| Candidate pool không chứa trang liên quan | Fusion không thể phục hồi tài liệu đúng | Đo candidate recall và tăng $K_c$ trước khi huấn luyện |
| QPAF oracle cao do có nhiều quyền chọn | Dễ diễn giải quá mức | Báo cáo gain coverage, bootstrap và learned performance riêng |
| Leakage từ qrels vào feature/clustering | Kết quả không triển khai được | Cố định pipeline không nhãn; audit split và feature provenance |
| Ba score có phân phối khác nhau | Trọng số khó diễn giải | Dùng cùng normalization; sensitivity analysis |
| QPAF overfit vì nhiều quyết định theo trang | Không khái quát | Module nhỏ, regularization, nhiều seed và external validation |
| Chi phí visual score extraction cao | Chậm tiến độ | Tách offline extraction khỏi fusion; cache score và manifest |
| Dataset tiếng Việt là VQA, không phải retrieval chuẩn | Kết luận sai nhiệm vụ | Xây dựng/kiểm chứng page-level qrels hoặc giới hạn phạm vi |
| DAT/mFAR không tái lập công bằng | Baseline không đáng tin | Chỉ đưa vào bảng chính khi protocol và implementation được xác minh |

## 10. Sản phẩm dự kiến

- mã nguồn tái lập cho candidate generation, normalization, oracle và learned fusion;
- score cache có phiên bản cho ba retriever;
- cấu hình và manifest bất biến cho từng run;
- bảng kết quả Global–QARF–CARF–QPAF với seed status và confidence interval;
- ablation, error analysis và báo cáo chi phí;
- tài liệu hướng dẫn tái lập từ fresh checkout;
- luận văn/bài báo mô tả đúng phạm vi bằng chứng thực nghiệm.

## 11. Kế hoạch thực hiện theo pha

1. **Pha A — Chuẩn bị dữ liệu và baseline:** cố định dataset revision, split, metric; chạy ba retriever và kiểm tra score cache.
2. **Pha B — Complementarity và oracle:** chạy individual, RRF, fixed fusion, sau đó Global/QARF/QPAF oracle với $W_7$; chỉ mở rộng $W_{66}$ nếu cần.
3. **Pha C — Kiểm tra granularity:** phân tích coverage; chạy CARF khi page-level headroom rõ; chọn granularity bằng cổng dừng.
4. **Pha D — Learned fusion:** triển khai QARF trước làm baseline học được, sau đó CARF/QPAF theo kết quả Pha C.
5. **Pha E — Xác nhận và viết báo cáo:** multi-seed, external validation, Vietnamese evaluation nếu protocol hợp lệ, ablation và error analysis.

Mốc thời gian cụ thể phụ thuộc vào tài nguyên GPU, khả năng tải mô hình/dataset và thời hạn nộp; các thông tin này cần được chốt trước khi chuyển kế hoạch pha thành lịch tuần.

## 12. Kết luận

QPAF là một mở rộng có phạm vi rõ từ adaptive fusion theo câu hỏi sang adaptive fusion theo cặp câu hỏi–trang cho Visual RAG. Điểm mạnh của đề xuất không nằm ở giả định rằng mô hình chi tiết hơn chắc chắn tốt hơn, mà ở thiết kế thực nghiệm có thể bác bỏ giả thuyết đó sớm. Bằng cách đo complementarity, oracle headroom và learned performance theo thứ tự, đề tài có thể chọn Global, QARF, CARF hoặc QPAF dựa trên bằng chứng thay vì mặc định chọn phương án phức tạp nhất.

## Tài liệu tham khảo

[1] M. Faysse, H. Sibille, T. Wu, B. Omrani, G. Viaud, C. Hudelot, and P. Colombo, “ColPali: Efficient Document Retrieval with Vision Language Models,” ICLR 2025, arXiv:2407.01449. https://arxiv.org/abs/2407.01449

[2] S. Yu et al., “VisRAG: Vision-based Retrieval-augmented Generation on Multi-modality Documents,” ICLR 2025, arXiv:2410.10594. https://arxiv.org/abs/2410.10594

[3] M. Li, T. Chen, B. Van Durme, and P. Xia, “Multi-Field Adaptive Retrieval,” ICLR 2025, arXiv:2410.20056. https://proceedings.iclr.cc/paper_files/paper/2025/hash/fc657b7fd7b9aaa462f2ef9f0362b273-Abstract-Conference.html

[4] H.-L. Hsu and J. Tzeng, “DAT: Dynamic Alpha Tuning for Hybrid Retrieval in Retrieval-Augmented Generation,” arXiv:2503.23013, 2025. https://arxiv.org/abs/2503.23013
