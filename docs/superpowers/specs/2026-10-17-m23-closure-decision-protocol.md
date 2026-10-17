# M2.3 — Quy tắc hoàn tất hiệu chuẩn với bộ dữ liệu hiện có

Người dùng giao tìm nguồn gốc, đối chiếu cách làm của đồ án và hoàn thành
M2.3. Giữ nguyên 18 references đã chọn, không thêm bản chữ hoặc dùng qrels/
câu trả lời để chọn chính sách OCR. Phần review bổ sung do Codex thực hiện,
ghi rõ AI và không giả chữ ký người dùng/nhóm.

## Phát hiện từ nguồn gốc

- [ViDoRAG, Appendix A](https://arxiv.org/html/2502.18017v2#A1): thí nghiệm
  OCR của tác giả dùng PP-OCR. Đây là một lựa chọn thực nghiệm, không phải
  điều kiện bắt buộc của dataset.
- [Mã OCR tác giả](https://github.com/Alibaba-NLP/ViDoRAG/blob/main/scripts/ocr_triditional.py):
  PP-OCRv3 tiếng Anh, phân loại hướng chữ và ngưỡng score 0.6. Score này không
  đồng nhất xác suất đúng hoặc confidence của Tesseract.
- [Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html):
  chất lượng phụ thuộc ảnh, phân đoạn và hướng chữ; 300 DPI là khuyến nghị
  đầu vào, không phải bảo đảm tốt hơn cho mọi trang.
- [OCR-D](https://ocr-d.de/en/spec/ocrd_eval): đánh giá cần GT phù hợp; lỗi
  thứ tự đọc và lỗi nhận chữ cần được xem riêng. Bổ sung bag-of-words error
  giúp xem nội dung khi thứ tự bảng/cột thay đổi.
- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html): có thể
  OCR toàn trang hoặc phần ảnh, giữ text layer và cache kết quả. Đây là căn
  cứ cho phương án bảo toàn native và bổ sung OCR ngoài vùng native.

## Sửa cách diễn giải trong đồ án

Tập 18 gồm 15 development, 3 holdout, 0 regression; holdout đã được xem trong
các lượt trước, nên chỉ là kiểm tra mô tả, không còn là kiểm định độc lập
chưa từng tiếp cận. Không gọi tập này đại diện toàn corpus. Việc đổi/bổ sung
metric dưới đây là amendment hồi cứu sau khi đã thấy CER/WER, không giả vờ
đã preregister từ đầu.

1. Giữ CER/WER hiện hành để so sánh và lưu raw outputs.
2. Thêm BWE = L1 chênh lệch hai multiset token / tổng số token hai bên.
   Báo bản strict (NFC + whitespace tokens, giữ case/dấu) và bản retrieval
   (NFC, casefold, token chữ/số Unicode). Bản retrieval là chỉ số phụ trợ
   cho text retrieval, không thay tên thành CER/WER chuẩn OCR-D.
3. Chọn operating point bằng **macro retrieval-BWE trên development có chữ**;
   micro/BWE strict/CER/WER là phân tích nhạy cảm. Không dùng holdout hoặc
   regression để chọn. Nếu bằng nhau, ưu tiên DPI nhỏ hơn, confidence bổ sung
   cao hơn. Không yêu cầu kết quả hoàn hảo để có một chính sách vận hành.
4. So sánh tập ứng viên nhỏ: native; OCR150; OCR300; legacy fallback40 tại150;
   native + OCR ngoài vùng text native ở 150/300, ngưỡng word confidence60/80.
   Bounding-box overlap 0.5 là quy tắc hình học công bố trước phép so sánh này,
   không fit từ GT. Giữ toàn bộ native hợp lệ; chỉ thêm các word OCR không bị
   native che phủ và đạt confidence. Giữ raw OCR nguyên vẹn để trace.
5. Native rỗng/encoding lỗi dùng OCR toàn trang. Trang ít chữ không tự bị coi
   thất bại chỉ vì dưới40/50 ký tự. Confidence60 còn là cờ cảnh báo chất lượng,
   không diễn giải thành accuracy60%. Đầu ra rỗng là NO_TEXT_DETECTED, không
   tự khẳng định ảnh không chữ. Trang ảnh có chữ trên đồ vật có thể không được
   engine đọc; regression phải ghi rõ điều đó.
6. Chốt các caps từ lượt CPU đã đo; max_failure_fraction1% là quy tắc vận hành
   dừng job khi lỗi kỹ thuật, không phải ước lượng tỷ lệ lỗi OCR toàn corpus.
7. Review8 native còn thiếu và ghi overlay cho các PASS trước đó mâu thuẫn
   với phạm vi toàn trang của references. Giữ nguyên file nguồn/lịch sử.

Đóng M2.3 khi đã có review có nguồn, bảng ứng viên, chính sách executable và
config chốt, đầu ra mẫu121 trang, tests/verification, quyết định AI có giới hạn
và revision bất biến. Không chạy full corpus M2.6, không huấn luyện M2.4/M3 và
không gọi quyết định của Codex là chữ ký nghiệm thu độc lập của nhóm.
