# Khi nào QPAF có thể vượt một bộ trọng số static?

Nghiên cứu ngày 31/10/2026. **Trường hợp đáng thử nhất là một tập có lỗi bổ trợ giữa các kênh,
và loại kênh đáng tin thay đổi giữa các trang của cùng query, với tín hiệu mà gate có thể quan sát khi suy luận.**
Độ khó hoặc nhiều hình ảnh chưa đủ: một visual retriever mạnh vẫn có thể thắng gần như mọi nhóm.

Khuyến nghị thực tế: chẩn đoán phần headroom đã có trên ViDoSeek, sau đó dùng một portfolio ViDoRe V3
Industrial + Finance EN + Computer Science làm ứng viên nghiên cứu có kiểm soát. UniDoc-Bench cho bằng chứng
định hướng rõ hơn về đảo chiều text/image; MMDocIR là lựa chọn mở rộng để kiểm tra nhiều trang bằng chứng.
Đây là đề xuất thí nghiệm, chưa phải kết quả QPAF mới và chưa thay đổi protocol đang dùng.

**1. Phải tách ba câu hỏi.**

| Mức | Điều cần chứng minh | Điều không đủ |
| --- | --- | --- |
| Global → QARF | Các query cần mức phối hợp kênh khác nhau và sự khác nhau đó dự đoán được | Chỉ chứng minh oracle đổi trọng số tốt hơn |
| QARF → QPAF | Trong cùng query, đặc điểm từng trang giúp xử lý những xung đột mà một vector chung không xử lý tốt | Chỉ trộn query văn bản với query hình ảnh |
| QPAF có nội dung → score-only | Thông tin query/trang ngoài ba score có giá trị sau khi kiểm soát số tham số và calibration | Một gate nhiều tham số hơn hoặc phép trộn phi tuyến hơn |

[mFAR](https://arxiv.org/html/2410.20056) và [DAT](https://arxiv.org/html/2503.23013v1) cho cơ sở về thích ứng theo query.
mFAR còn fine-tune encoder; DAT dùng LLM đánh giá top-1 rồi sinh một alpha cho cả query.
Chúng không phải bằng chứng đã có cho lợi thế riêng của QPAF với retriever đóng băng.

**2. Bằng chứng ngay trong repo: không cần mặc định ViDoSeek là dataset sai.**

Đọc lại M4.4 trên **171 query validation**, cùng W66 và candidate pool:

| Cách chọn trọng số dùng nhãn | nDCG@10 |
| --- | ---: |
| Global oracle | 0.871743 |
| Query oracle | 0.911900 |
| Page oracle đã tìm được | 0.940125 |

Query oracle tăng 0.040157 so với global; page oracle tăng thêm 0.028225 trên 20/171 query, 151 hòa.
[Số đã tính lại từ metric từng query](evidence/local-evidence.json).
Đây là tìm kiếm dùng nhãn, với hai lượt cập nhật theo candidate, không bảo đảm tối ưu toàn cục.
Thứ tự không gian lựa chọn lồng nhau không tự chứng minh một gate học được sẽ cải thiện.

Không so trực tiếp các mức trên với 0.865492 của [F3 CV 970 query](../lab-f3-objective-20261030/README.md):
hai phạm vi đánh giá khác nhau. Kết quả này chỉ cho thấy có hành vi xếp hạng để nghiên cứu trong dataset hiện có.
Không lấy riêng 20 query được cải thiện làm một “test set” mới.

[Code feature hiện tại](../../../../src/qpaf/m12/features.py) có 12/13 input từ score/rank/gap/disagreement;
input còn lại là độ dài query. [Gate](../../../../src/qpaf/lab/model.py) không trực tiếp đọc OCR, bố cục hay
ngữ nghĩa đầy đủ của query. F3 đổi loss, không bổ sung những tín hiệu này.
[F1](../../../feature_lab/F1_content_features.md) và [F4](../../../feature_lab/F4_query_embedding.md)
đề xuất hướng bổ sung phù hợp, nhưng chưa được kiểm chứng bởi lượt chạy F3.

**3. Trường hợp một vector không đủ — ví dụ toán học, không phải số liệu benchmark.**

Giản lược còn hai kênh, score đã chuẩn hóa; cùng một query cần hai trang:

| Trang | Text | Visual | Liên quan |
| --- | ---: | ---: | --- |
| A: đoạn giải thích | 1 | 0 | Có |
| B: sơ đồ | 0 | 1 | Có |
| C: trang nhiễu | 0.625 | 0.625 | Không |

Với một trọng số text w chung, điểm là A=w, B=1−w, C=0.625.
Muốn cả A và B trên C phải có w>0.625 và w<0.375, điều không thể đồng thời đúng.
QPAF có thể cho A ưu tiên text, B ưu tiên visual: cả hai đạt 1, trên C.

Ví dụ chỉ chứng minh khác biệt về khả năng biểu diễn; gate thật phải học routing từ dữ liệu train và
đặc trưng hợp lệ, không được nhìn nhãn của trang đang chấm. Một nonlinear combiner như max-score cũng
giải được ví dụ này, nên không thể coi toy là đóng góp độc quyền của QPAF.
[Kiểm tra số học](evidence/toy-example.json).

**4. Trường hợp thực tế nên đưa vào giả thuyết.**

| Trường hợp được định nghĩa trước | Tín hiệu hợp lệ khi suy luận | Mức thích ứng cần kiểm tra |
| --- | --- | --- |
| Query hỏi mã/tên riêng/số chính xác, xen query diễn đạt lại ý | IDF, số, overlap, query embedding | QARF có thể đã đủ |
| Cùng query cần trang giải thích và trang bảng/sơ đồ | Query–page coverage, bố cục, text/image ratio | QPAF so với QARF |
| Trang OCR tốt xen trang OCR lỗi/rỗng | OCR quality/confidence, token count, khả năng khớp query | Page-aware; cần text thật sự thắng ở một phần trang khác |
| Hard negative gần giống chủ đề nhưng sai chi tiết | Khớp thực thể/số/đơn vị kết hợp ngữ nghĩa và cấu trúc | QPAF hoặc reranker phi tuyến; phải đối chứng |

Các mô tả trên là giả thuyết, không phải quy luật “có số thì BM25 thắng” hay “có bảng thì visual thắng”.
Kênh nào có lợi phải được đo trên development data. Gold modality tags của qrels chỉ dùng phân tích;
không đưa chúng làm input gate lúc test.

**5. Những benchmark đáng cân nhắc.**

| Ưu tiên thực tế | Dataset | Cơ hội nghiên cứu | Giới hạn phải giữ rõ |
| --- | --- | --- | --- |
| 1 | ViDoRe V3 Industrial + Finance EN + Computer Science | Trang kỹ thuật, báo cáo số liệu, sách có text/code/hình; page qrels và Markdown có sẵn | Hiện thuộc vai trò external; nếu dùng nhãn để phát triển thì phải đổi vai trò và giữ tập external khác |
| 2 | MMDocIR page-level | Nhiều tài liệu, law/government/text lẫn hình/bảng, nhiều trang bằng chứng | Mở rộng ngoài protocol; task gốc biết document, không phải search global toàn corpus |
| 3 | UniDoc-Bench | Có kết quả công bố text/image đảo chiều theo loại evidence | Mở rộng; metric evidence khác page nDCG, corpus lớn và có điều kiện sử dụng |
| 4 | REAL-MM-RAG | BM25/BGE-M3 OCR và các mức paraphrase sát với ba kênh của dự án | Mạnh cho chẩn đoán query adaptation; thường một trang đúng nên chưa nhắm riêng QPAF |

ViDoRe V3: [Industrial](https://huggingface.co/datasets/vidore/vidore_v3_industrial) có 5.244 trang/27 tài liệu/283 query gốc;
[Finance EN](https://huggingface.co/datasets/vidore/vidore_v3_finance_en) 2.942/6/309;
[Computer Science](https://huggingface.co/datasets/vidore/vidore_v3_computer_science) 1.360/2/215.
Tổng ba corpus là **9.546 trang và 807 query gốc**; chọn tiếng Anh trước để không nhân giả số mẫu bằng bản dịch.
Hai sách CS không đủ để mặc định tạo CV độc lập theo tài liệu. Query nhiều tài liệu có thể làm các
connected component quá lớn; cần kiểm kê trước khi hứa một cách chia fold cụ thể.

[UniDoc Table 7](https://arxiv.org/html/2510.03663v2) báo Recall@10:
text-required: text 0.821, image 0.774; image-required: text 0.751, image 0.922.
Đây là đảo chiều đã đo, với OpenAI text embedding và ColQwen; nó chưa chứng minh một static được tuning tốt
không thể tận dụng cả hai. Chuyển metric evidence sang page cần định nghĩa riêng.

[MMDocIR release](https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset) có 20.395 trang/313 tài liệu/1.658 query.
Tên loader “train” của release evaluation không biến nó thành tập train.
[Paper](https://arxiv.org/html/2501.08828v3) dùng Recall@k trong tài liệu biết trước và vẫn cho thấy visual mạnh.
Không quảng bá benchmark này như bằng chứng text và visual chắc chắn cân bằng.

[REAL-MM-RAG](https://arxiv.org/html/2502.12342v1) hữu ích để kiểm tra ảnh hưởng của paraphrase; các biến thể cùng
query phải cùng nhóm. [MultiDocR](https://arxiv.org/html/2605.30027v1) bổ sung graded relevance/cross-page
nhưng dùng lại 313 tài liệu của MMDocIR; không coi chúng là hai lần xác nhận độc lập.

Có bằng chứng khác về bổ trợ: [MIDR App.L/M](https://arxiv.org/html/2609.01316v1) ghi 351 query nghiêng
về enriched text, 362 nghiêng về visual trong 1.489 query Anh; oracle chọn theo query đạt 0.7042 so với visual 0.6300.
Đây là enriched text bằng MLLM và oracle dùng nhãn, không phải ba kênh OCR hiện tại hoặc learned QPAF.

**6. Thí nghiệm đáng làm tiếp, theo thứ tự.**

1. **Dùng development score cache hiện có để chẩn đoán.** Đo per-channel metric, strict wins, candidate recall,
   gain coverage và regret. Không diễn giải entropy của một trọng số oracle được chọn tùy ý: nhiều vector
   có thể tạo cùng ranking, tie-breaking không phải “kênh đúng”.
2. **Kiểm tra khả năng học từ tín hiệu có thật.** F1/F4 là lựa chọn phát triển trên ViDoSeek:
   query semantics, overlap/IDF, OCR quality và page layout. Fit mọi thống kê học được trên fold train;
   khi đánh giá inductive, PCA/scaler cũng fit train, không mặc định dùng toàn dev.
3. **Chọn trước portfolio và vai trò.** Giữ V3 external: freeze cả model và global static từ source dev rồi đánh giá zero-shot.
   Hoặc tuyên bố rõ một phần V3 là development, chia theo document/query family, tuning công bằng cả static và learned,
   giữ phần/domain chưa chạm nhãn làm xác nhận. Không gọi kết quả đã fine-tune trên official test là zero-shot.
4. **Chạy ma trận đối chứng.** Best single channel; global tuned convex fusion; tuned RRF; query-aware QARF có embedding
   query; page-only routing; QPAF đầy đủ; score-only MLP/calibration cùng ngân sách; layout heuristic.
   Một mixture đa miền còn cần per-corpus static khi thông tin corpus có sẵn lúc phục vụ, để không nhầm nhận biết miền với tương tác query–page.
5. **Báo cáo đủ toàn tập và strata đã định nghĩa.** nDCG@10 theo benchmark thích hợp, evidence Recall@k cho multi-page,
   W/T/L, macro theo miền và query mean, nhiều seed, CI resample theo nhóm tài liệu/query family.
   Các bản dịch/paraphrase và query liên quan nhiều tài liệu không được coi là mẫu độc lập.
6. **Dừng ở mức đơn giản nếu dữ liệu không hỗ trợ.** Nếu query oracle không có mức tăng thực tiễn thì không đầu tư router;
   nếu page oracle không thêm đáng kể thì ưu tiên QARF; nếu có oracle gain nhưng tín hiệu không khái quát thì chưa chuyển thành learned gain.
   Nhóm cần chốt trước mức tăng thực tiễn và quy tắc thử nhiều cấu hình, không chọn ngưỡng sau khi nhìn test.

Giữ candidate union, normalization, điểm thiếu, retriever, text representation và ngân sách tuning giống nhau giữa các
phương pháp. Nếu đổi OCR sang VLM-enriched text, áp dụng cùng thay đổi cho static và learned rồi gọi đó là một thí nghiệm
representation riêng. Dense bị cắt nội dung trong khi BM25 nhìn toàn trang cũng là một so sánh lệch cần kiểm tra.

Một stress test OCR chất lượng hỗn hợp có thể hữu ích, nhưng mức lỗi phải gán theo quy tắc độc lập qrels,
giữ bản clean và so sánh mọi phương pháp trên cùng hai điều kiện. Nó đo robustness có kiểm soát, không thay thế xác nhận tự nhiên.

**7. Những giới hạn và cập nhật tài liệu liên quan.**

- [Fusion analysis](https://arxiv.org/html/2210.11934) và [GQR Table3](https://arxiv.org/html/2510.05038v3)
  củng cố yêu cầu dùng static đã tuning; thắng uniform/default RRF chưa đủ.
- [DRAG §3.3](https://www.mdpi.com/2079-9292/15/4/843) đã dùng tỷ lệ diện tích hình/bảng để điều chỉnh
  weighted Borda theo trang. Đây là precedent heuristic cần đối chứng; không tuyên bố page-aware fusion chưa ai làm.
  Publisher trực tiếp trả 429 trong lượt kiểm tra; không dùng các con số ablation chưa đối chiếu đầy đủ.
- Unveil adaptive weighting là trọng số mẫu trong distillation; ViDoRAG GMM điều chỉnh depth rồi union,
  không phải bằng chứng learned query×page fusion. Xem [ledger nguồn](evidence/sources.md).
- Nghiên cứu mới về [oracle weights dạng interval](https://arxiv.org/html/2610.24341) và
  [giới hạn router tài chính](https://arxiv.org/html/2608.00183) củng cố việc tách oracle khỏi learnability;
  đây là bằng chứng bổ sung có giới hạn, không phải kết quả cho hệ hiện tại.
- Scope hiện hành chỉ ViDoSeek, ViMDoc, ViDoRe V3 theo [đề xuất](../../../GUILDLINE_OVERVIEWS_PROPOSAL/DE_XUAT_NGHIEN_CUU_QPAF.md).
  MMDocIR/UniDoc/REAL-MM-RAG/MultiDocR cần amendment trước khi chạy như thí nghiệm dự án.
- Finance EN đã có metadata materialize và notebook pilot trong repo. Metadata không chứng minh đã tuning,
  cũng không chứng minh chưa ai mở nhãn; kiểm kê lịch sử trước khi gọi là tập xác nhận sạch.
  TEST-172 và ViMDoc confirmation đã có exposure theo tài liệu lab.
- ViDoRe có giấy phép annotation riêng với tài liệu nguồn. MMDocIR có chênh lệch thông tin license giữa
  Hub và paper/repo. UniDoc repo ghi CC-BY-NC và thêm model-use notice; kiểm tra đúng intended use trước khi nhận làm benchmark.

**Hồ sơ nghiên cứu:** [spec](superpowers/spec.md), [plan](superpowers/plan.md),
[21 source cards](evidence/sources.md), [nguồn có cấu trúc](evidence/sources.json),
[bằng chứng local](evidence/local-evidence.json), [toy](evidence/toy-example.json),
[quy trình](evidence/workflow.md), [phân công và đối chiếu](evidence/parallel-investigations.md),
[rà soát dataset/protocol](evidence/domain-review.md).

Không có training, tải model/corpus, compute cloud hay mở nhãn test mới trong nghiên cứu này.
Hồ sơ được kiểm tra bằng [validation](evidence/validation.json) và [manifest SHA-256](evidence/hashes.json).
