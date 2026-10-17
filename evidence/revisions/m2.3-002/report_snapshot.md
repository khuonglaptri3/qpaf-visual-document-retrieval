# M2.3 — Nghiên cứu nguồn gốc và quyết định hoàn tất

**Kết quả: COMPLETE_BOUNDED_CALIBRATION.** Hoàn tất review 121 trang và18
references người dùng đã chọn; chốt cấu hình `m23-native-preserving-v1`:
giữ native hợp lệ, bổ sung OCR Tesseract 300 DPI ngoài vùng native, word
confidence bổ sung từ60. Không còn PENDING/UNSURE hoặc reference chờ xử lý
trong phạm vi18. Đây là quyết định kỹ thuật của Codex theo yêu cầu hoàn thành
của người dùng; không tạo chữ ký độc lập của Thanh/Tấn Phát.

## 1. Người ta làm như thế nào với ViDoSeek?

Không có một bộ ngưỡng OCR bắt buộc đi kèm ViDoSeek. [Dataset card của tác giả](https://huggingface.co/datasets/Qiuchen-Wang/ViDoSeek/blob/main/README.md)
cung cấp PDF, query và trang tham chiếu; phân biệt Text/Table/Chart/Layout,
và dẫn tới code tiền xử lý tùy chọn.

[ViDoRAG, Appendix A](https://arxiv.org/html/2502.18017v2#A1) dùng PP-OCR cho
nhánh văn bản. [Code OCR chính thức](https://github.com/Alibaba-NLP/ViDoRAG/blob/main/scripts/ocr_triditional.py)
cụ thể hóa PP-OCRv3 tiếng Anh, có bộ phân loại hướng chữ, lọc score 0.6 rồi ghép
text boxes theo vị trí. Đó là cấu hình thí nghiệm của họ; không phải bằng chứng
rằng Tesseract confidence 60 tương đương score 0.6, hay rằng phải đổi engine để
hoàn thành hiệu chuẩn hiện tại.

[Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) khuyến
nghị ảnh khoảng300 DPI trở lên, đồng thời nhấn mạnh ảnh đầu vào, hướng chữ và
phân đoạn trang. Vì vậy phải đo trên đúng dữ liệu, không suy ra DPI cao hơn
luôn tốt hơn.

[OCR-D](https://ocr-d.de/en/spec/ocrd_eval) đánh giá bằng ground truth, xem
riêng lỗi nội dung và bố cục. Ghép toàn trang sai thứ tự có thể làm edit
distance lớn dù nhiều từ vẫn đúng; bag-of-words error giúp kiểm tra phần
nội dung không phụ thuộc thứ tự. [Tài liệu PyMuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)
mô tả OCR toàn trang hoặc vùng ảnh và lưu kết quả để dùng lại. Đây là căn cứ
cho ứng viên giữ native và chỉ bổ sung OCR tại vùng chưa có native.

## 2. Đồ án đang làm gì và đã sửa gì?

Đồ án cố định PDFium 4.30.0, Tesseract 5.3.0, traineddata tiếng Anh có SHA-256,
OEM 3/PSM 3, không tiền xử lý, CPU 4 cores/4GiB/2 subprocess. Mẫu đã khóa gồm
120 trang chính +1 regression; mỗi trang có hai lượt150/300 DPI, txt/TSV/ảnh,
hash và số đo tài nguyên. Đây là pipeline có kiểm soát của đồ án, không gọi
là tái lập nguyên xi PP-OCR của ViDoRAG.

Ba vấn đề đã xử lý trước khi chốt:

1. **Chỉ dùng độ dài native bỏ sót chữ trong hình.** Một trang có title đủ40
   ký tự vẫn có thể thiếu cả chart/map. Cũng có trang chỉ vài từ nhưng native
   đúng và OCR kém. Chính sách mới bảo toàn native hợp lệ, OCR toàn trang
   trong bước tiền xử lý và bổ sung words nằm ngoài vùng native. Nếu native
   rỗng hoặc không dùng được thì lấy OCR toàn trang.
2. **CER/WER lẫn nhận dạng với thứ tự đọc.** Giữ số cũ, thêm strict BWE và
   retrieval BWE; không đổi tên hai chỉ số này thành CER/WER. Bản retrieval
   dùng NFC, casefold, token chữ/số Unicode; BWE là L1 chênh lệch multiset
   chia tổng số token hai bên. Macro cho mỗi trang có trọng số bằng nhau.
3. **Parser TSV xử lý sai dấu nháy kép.** Tesseract TSV không quote kiểuCSV.
   Đã dùng `QUOTE_NONE`, có test cho token bắt đầu bằng dấu nháy. Tính lại242
   confidence summaries từ raw TSV; 11 lượt thay đổi. Word cloud 300 DPI có171
   word thật thay vì55 word của parser cũ. Raw OCR/txt/TSV không bị sửa.

Ở bước đóng gói, kiểm tra hash phát hiện Windows đổiLF thànhCRLF. Config
được ghi bằng byte UTF-8 rõ ràng; hash policy trong121 page records phải khớp
đúng file config thực. Các package chuẩn bị trước kiểm chứng được giữ làm
lịch sử; gói dùng tiếp duy nhất là `closure/2026-10-17-closed/`.

## 3. Quy tắc chọn và kết quả thực tế

[Amendment đã lưu](../../../docs/superpowers/specs/2026-10-17-m23-closure-decision-protocol.md) công bố
8 ứng viên và tiêu chí chọn **macro retrieval-BWE trên development có chữ**.
Việc bổ sung metric diễn ra sau khi đã thấy CER/WER: đây là hiệu chuẩn hồi
cứu có công bố, không giả là preregistration. Holdout đã xem trước chỉ là
kiểm tra mô tả; không dùng holdout/regression để chọn.

| Ứng viên | Dev macro BWE | Holdout macro BWE |
|---|---:|---:|
| Native | 22.72% | 9.42% |
| OCR 150 toàn trang | 16.77% | 15.51% |
| OCR 300 toàn trang | 18.24% | 17.30% |
| Fallback40 ký tự/OCR 150 cũ | 14.00% | 9.42% |
| Native + vùng OCR 150, conf60 | 12.33% | 8.98% |
| Native + vùng OCR 150, conf80 | 12.71% | 8.98% |
| **Native + vùng OCR 300, conf60 — chọn** | **11.32%** | **8.46%** |
| Native + vùng OCR 300, conf80 | 11.43% | 8.78% |

Dev có14 trang chữ +1 no-text; holdout có3 trang chữ. So với fallback cũ,
ứng viên chọn giảm macro BWE 2.68 điểm phần trăm trên development. Các chỉ số
còn lại của cấu hình chọn:

| Chỉ số | Development | Holdout |
|---|---:|---:|
| Micro retrieval-BWE | 8.47% | 10.44% |
| Micro strict BWE | 8.90% | 12.46% |
| CER chuỗi toàn trang | 30.22% | 36.70% |
| WER chuỗi toàn trang | 34.08% | 39.51% |

CER/WER của cấu hình ghép vẫn chịu ảnh hưởng thứ tự bổ sung vùng OCR; không
tối ưu thứ tự đọc trong milestone này. Bản OCR 300 toàn trang có CER dev thấp
hơn25.08%, nhưng bỏ native làm mất một số từ đúng. Việc chọn chỉ số nội dung
cho retrieval có đánh đổi được công bố; chưa đo cải thiện nDCG/Recall thật.

## 4. Cấu hình đã chốt và bằng chứng review

- Tesseract 5.3.0, eng, traineddata đã pin; **300 DPI, OEM 3, PSM 3**, không tiền xử lý.
- Native có nội dung dùng được được giữ; không loại trang ngắn chỉ vì dưới40/50
  ký tự. Tỷ lệ printable tính trên ký tự không phải whitespace, loại PUA và
  replacement khỏi số hợp lệ; ngưỡng0.85.
- OCR word ngoài native được bổ sung khi confidence >= 60 và phần diện tích
  đã có native nhỏ hơn0.5. Tính union diện tích để không đếm vùng chồng hai lần.
- Mean confidence < 60 là cảnh báo; không xem là accuracy 60% và không xóa cả trang.
- OCR rỗng được ghi `NO_TEXT_DETECTED`, giữ trang cho kênh visual. Không suy ra
  ảnh không có chữ. Regression 109 có chữ nhỏ trên đồ vật/áo nhưng engine không
  đọc được; đây là giới hạn chất lượng đã ghi rõ, không tạo reference rỗng giả.
- Timeout OCR 15s: max300 DPI đã đo7.329s, p99 6.611s; đây là cap OCR subprocess,
  không phải deadline cho render+cả trang. RAM 4096 MiB, 2 workers,1 thread/worker,
  cap 40M pixels,0 retry. Peak job đã đo1281.48MiB; max OCR child 433.80 MiB.
- Max lỗi kỹ thuật1% là quy tắc dừng job trên tất cả trang đã lên lịch, gồm
  render/parse/timeout/engine lỗi. Không tính successful no-text/quality warning
  là lỗi kỹ thuật; không gọi1% là ước lượng lỗi nhận dạng toàn corpus.

Đã chốt8 native còn thiếu bằng xem ảnh. Đồng thời sửa13 nhãn PASS trước đó
mâu thuẫn phạm vi toàn trang: 12 thành HAS_ERRORS,1 thành NO_TEXT. Tổng cuối:
**95 PASS /25 HAS_ERRORS /1 NO_TEXT;0 PENDING/UNSURE**. Giữ100 quyết định gốc
của người dùng và21 review sửa/bổ sung ghi tên Codex AI, không giả121 human
reviews. 18 references và toàn bộ text của chúng được giữ nguyên trong lượt này.

Áp dụng policy cho 121 trang: **45 native  /70 native+OCR  /6 OCR**, trong 6 OCR
có2 NO_TEXT_DETECTED. Không có lỗi kỹ thuật;23 trang có cảnh báo chất lượng.
Con số25 native có lỗi không đồng nghĩa25 trang sau ghép vẫn có cùng lỗi,
cũng không có bằng chứng rằng tất cả lỗi đã biến mất.

## 5. Bàn giao M2.4, M2.6, M2.8

- [Config đã chốt](../../../configs/m2.3/ocr_policy_frozen.toml).
- [Implementation và loader kiểm hash](../../../src/qpaf/m23/policy.py).
- [Revision bất biến m2.3-002](../../../evidence/revisions/m2.3-002/README.md),
  gồm decision, policy, manifest dữ liệu và báo cáo chụp.
- [121 page records đã resolve](../../../results/m2.3/closure/2026-10-17-closed/resolved_pages.json),
  [JSON review cuối](../../../results/m2.3/closure/2026-10-17-closed/human_reviews.final.json),
  [HTML xem cả text theo policy](../../../results/m2.3/closure/2026-10-17-closed/index.html#reference).
- [Bảng8 ứng viên CSV](../../../results/m2.3/closure/2026-10-17-closed/candidate_aggregates.csv),
  [decision/giới hạn](../../../results/m2.3/closure/2026-10-17-closed/decision.json).

M2.4 nạp `page_id`, `text`, `text_sha256`, `text_source`, `extraction_status`,
`warnings`, `policy_sha256`; dùng text này cho đặc trưng trang và tương tác.
18 references chỉ để kiểm định OCR, không phải nhãn relevance huấn luyện gate.
M2.6 triển khai toàn corpus theo policy/engine/caps đã chốt; thư viện đã có
helper lấy native geometry đúng crop origin và quy đổi rotation. M2.8 phải
tạo cache text theo policy hash mới; QARF/QPAF dùng chung preprocessing/cache.
Kết quả smoke M2.2 cũ là lịch sử và không tự trở thành cache mới.

**Đã kiểm chứng:**23 tests PASS; 121 outputs tái lập từ raw TSV/native geometry;
144 candidate metric records; hash config/source/package; giao diện121 review/
18 references, xem policy text và export/import/reload. Receipts ở
`results/m2.3/verification/closure-*-2026-10-17.json`.

**Giới hạn được chấp nhận khi hoàn tất:** chỉ18 references thuộc12 PDF,
3 holdout đã xem trước, không có regression GT; còn ca chữ xoay/scene text và
word cloud khó. `FROZEN` là cấu hình vận hành của đồ án; không chứng nhận OCR
toàn corpus đạt một accuracy cụ thể. Không chạy full OCR, cache hoặc learned
training trong lần hoàn tất này.
