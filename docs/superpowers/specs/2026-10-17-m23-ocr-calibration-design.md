# M2.3 — Hiệu chuẩn OCR có kiểm soát và review thủ công

**Trạng thái ban đầu:** IMPLEMENTING / HUMAN_REVIEW_PENDING.
**Phạm vi người dùng giao:** triển khai, chạy lấy dữ liệu, đưa lên HTML để người
dùng review; sau đó mới tổng hợp chất lượng và quyết định ngưỡng.

**Kết quả cuối:** người dùng giao Codex deep research và hoàn thành M2.3.
Đã có COMPLETE_BOUNDED_CALIBRATION và operating config FROZEN; amendment về
metric/phương án giữ native ở [protocol hoàn tất](2026-10-17-m23-closure-decision-protocol.md),
quyết định tại [báo cáo cuối](../reports/2026-10-17-m23-research-and-final-decision.md).
Các trạng thái ban đầu/nhận/chờ review phía dưới được giữ làm lịch sử.

## Điều chỉnh phạm vi review theo người dùng — 2026-10-17

**Cập nhật QA mới nhất:** người dùng xác nhận đã kiểm tra 18 trang và giao
Codex đọc/sửa. Đã sửa theo ảnh, lưu đủ 18 CONFIRMED dưới reviewer Codex, kèm
provenance và diff; không còn chờ reference trong phạm vi 18. Còn 8 kết luận
native và quyết định ngưỡng. Xem [báo cáo QA hoàn tất](../reports/2026-10-17-m23-reference-qa-completed.md).
Giao diện bản sửa áp dụng overlay 18, giữ dataset/hash 41-target ban đầu làm
nguồn; các đoạn nhận/chờ dữ liệu dưới đây là lịch sử của thời điểm tương ứng.

**Cập nhật sau khi nhận:** đã tự lấy đúng 18 bản từ Edge lúc 12:47 UTC,
17 có chữ +1 no-text, đều DRAFT; đã lưu manifest và phân tích sơ bộ, chưa
freeze. Xem [nhận xét 18 trang](../reports/2026-10-17-m23-18-page-review.md).
Phần dưới ghi nhận quyết định và công việc dự kiến tại thời điểm đổi phạm vi.

Người dùng yêu cầu giảm bản chữ đối chiếu từ 41 xuống **18 trang** và xác nhận
**giữ 18 trang đã làm ở bước 4**. Yêu cầu mới thay thế số lượng 41 references
trong protocol ban đầu bên dưới; tập native vẫn là 121 trang.

Chờ JSON export mới để xác định đúng 18 page IDs và kiểm tra reference đã
CONFIRMED/full_page, reviewer, thời gian và hash. Chưa nhận bằng chứng mới nên
chưa ghi nhận 18 references hoàn tất trong kết quả máy. Không chọn một tập 18
khác hoặc tự xác nhận bản nháp thay người dùng.

Khi nhận JSON, lưu manifest tập review 18 trang riêng, gắn với dataset/run và
hash file xuất. Tổng hợp đúng các trang này, báo số trang/PDF và phân bố
development/holdout/regression thực tế; split không có reference ghi thiếu
coverage. Việc giảm số lượng không tự chứng minh đủ dữ liệu để freeze ngưỡng.
Ghi rõ đây là thay đổi phạm vi sau khi người dùng đã review, không coi tập 18
là mẫu ngẫu nhiên hoặc giữ nguyên độ bao phủ 41 trang ban đầu.

Run, sample IDs và hash dataset đã khóa vẫn làm nguồn đối chiếu. HTML và
summarizer hiện còn dùng tập 41 cũ; bộ lọc này chưa phản ánh yêu cầu giảm xuống
18. Khi có export mới, áp dụng tập 18 bằng manifest riêng cho lần tổng hợp
mới; không ghi đè summary/revision cũ để thay đổi lịch sử.

## Mục tiêu và giới hạn

Chuẩn bị mẫu, paired OCR 150/300 DPI, text/ảnh/TSV có hash, số đo tài nguyên và
giao diện review thật. Chưa coi bản nháp hoặc kết quả tự động là nhãn đúng.
Không huấn luyện QARF/QPAF, không chạy OCR toàn corpus M2.6 hoặc cache M2.8.

Ngưỡng M1.8/M2.2 giữ trạng thái provisional. Chỉ có engineering data ready sau
run; M2.3 còn chờ review thủ công, phân tích dev/holdout và review quyết định.

## Cấu hình và môi trường

- `configs/m2.3/ocr_calibration.toml`: seed 2026, PDFium 4.30.0, Tesseract 5.3.0,
  Debian package 5.3.0-2, language package 1:4.1.0-2; eng, OEM 3, PSM 3.
- Hash `eng.traineddata`:
  `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
  Hash được đọc từ preflight thật trước run và kiểm tra lại trên worker.
- Hai cấu hình chỉ khác DPI 150/300; không tiền xử lý hoặc retry ngầm.
- Runtime Python 3.11; Pillow 11.3.0, pypdfium2 4.30.0, psutil 7.0.0.
  Ghi đầy đủ Python patch, PDFium build, Leptonica, packages và source hashes.
- Một Modal container CPU 4 cores / 4096 MiB; 2 OCR subprocess cùng lúc,
  mỗi subprocess `OMP_THREAD_LIMIT=1`; không cấp GPU, không import Torch.
- 120 s/OCR attempt; 1800 s budget làm việc, platform timeout thêm 30 s để kết
  thúc/ghi lỗi; không tự chạy lại. Có kiểm tra cap ảnh 40 triệu pixels.
  Revision v2 nâng từ 32M sau khi lượt đầu ghi nhận 8 trang cần khoảng 36M;
  giữ mẫu và cấu hình chất lượng, lưu nguyên lượt đầu, không downsample ngầm.
- Input <=384 MiB, output worker <=1024 MiB; các giới hạn RSS/artifact là kiểm
  tra chấp nhận, không phải tất cả đều là hard stop của allocator/filesystem.

## Chọn mẫu

1. Xác minh revision M2.1, archive nguồn và page manifest M1.6 theo hash.
2. Chỉ dùng ID, số trang và native-text probe để chọn mẫu. Không dùng qrels,
   nội dung câu hỏi hoặc test queries để chọn/thay cấu hình. Tài liệu thuộc
   corpus dùng chung giữa các query split, không giả định document split của M2.1.
3. 30 PDF: 6 PDF <=10 trang, 12 PDF 11–18 trang, 12 PDF >=19 trang. Đây là
   phân tầng theo độ dài, chưa phải nhãn nội dung/bố cục đã được con người xác nhận.
4. Chia PDF theo hash thành 20 development và 10 holdout, không trùng tài liệu.
5. Probe tối đa 8 trang/PDF, tổng <=240 trang; chọn 4 trang gồm đầu/cuối,
   sparse/rich native, bù bằng hash nếu trùng. Mẫu chính 120 trang.
6. Thêm ca no-text đã biết của M2.2 nếu chưa có trong mẫu; ghi riêng regression,
   không gộp vào thống kê tỷ lệ lỗi mẫu đại diện. Tối đa 121 trang / 31 PDF.
7. Gán 40 trang tham chiếu bắt buộc của mẫu chính: mỗi PDF ít nhất một trang,
   thêm trang thứ hai của 10 development PDF; ca regression cũng cần tham chiếu.

Mẫu chủ động tăng số tài liệu ngắn và chọn trang sparse/rich. Không gọi tỷ lệ
lỗi gộp là ước lượng không chệch của toàn corpus; không dùng 120 trang để tuyên
bố chứng minh tỷ lệ lỗi corpus <1%. Tên lĩnh vực/multicol/table phải được review
thực tế, không suy diễn từ độ dài hoặc native char count.

## Luồng thực thi và artifact

```text
run_m23_calibration.py
  -> sample.py: verify M2.1/M1.6, bounded probes, PDFs/native/IDs/hashes
  -> worker.build_app: CPU image, source snapshot identity, Volume
  -> worker.execute: render 150/300, Tesseract txt+tsv, timings/RSS/failures
  -> fetch: tải artifact về results/m2.3/<run-id>/remote/
  -> review.build_review: HTML + ảnh 300 DPI local, chờ người review
  -> summarize_m23_reviews.py: nhập JSON người dùng xuất, tổng hợp riêng split
```

- `src/qpaf/m23/config.py`: validate contract/caps.
- `sample.py`: chọn và khóa mẫu, native text gốc; provenance môi trường local.
- `worker.py`: OCR thực, command mỗi attempt, runtime identity, failure evidence.
- `review.py`: build HTML, validate human exports, CER/WER, tổng hợp coverage.
- `review_template.html`: hai màn hình đã được người dùng yêu cầu thiết kế.
- `scripts/run_m23_calibration.py`: CLI điều phối, verify, rebuild review.
- `scripts/summarize_m23_reviews.py`: tổng hợp human review; output mới mỗi lần.

Mỗi run là thư mục mới, không ghi đè; source snapshot gồm source/config/template.
Input PDFs, ảnh, raw TSV/txt và HTML được sinh không đưa vào Git; metadata,
source ZIP, hashes, logs và báo cáo nhỏ được quản lý bằng Git như M2.2.
Volume `qpaf-m23-ocr-artifacts` giữ remote artifact. Lệnh `--verify` local không
gọi Modal. Human export và kết quả tổng hợp nằm ngoài dữ liệu run đã khóa.

## Review và số đo

Bước 2 review native tất cả trang. Bước 4 ưu tiên filter Cần bản chữ đối chiếu
cho tập bắt buộc, giữ người review/time/hash/phạm vi. Bản nháp không tính CER/WER;
sửa bản xác nhận phải hủy xác nhận. Không so đoạn chọn với output toàn trang.
Trang không chữ cần xác nhận riêng; không chia CER cho reference rỗng.

Chuẩn hóa metric: NFC + collapse whitespace, giữ case/dấu/số/punctuation; WER
tách whitespace. Ghi edit counts, micro và macro CER, missing output, false
positive chars ở trang không chữ, riêng dev/holdout/regression. Mọi tổng hợp
đều ghi `thresholds_frozen=false` cho đến khi có quyết định review riêng.

TSV giữ word bbox/block/paragraph/line/confidence; txt của Tesseract giữ dòng.
Confidence trung bình/weighted chỉ là tín hiệu engine, không phải accuracy.
Lưu cả printable ratio lịch sử và ratio không tính whitespace để phân biệt
newline với ký tự lỗi. RSS gồm Python + subprocess, đo 20 ms; RSS từng OCR
subprocess báo riêng. Đo render, từng OCR attempt và wall-time toàn job.

## Ngân sách

Giữ planning budget <=1 USD cho đợt đầu; không đổi workspace billing 30 USD.
4 CPU +4 GiB theo giá công bố có compute tối đa khoảng 0.111 USD/1800 s,
chưa gồm build/start/fetch/network. Đây là dự toán, không phải spend limit của
Modal; đọc billing thực sau chạy. Không dùng GPU.

Nguồn kỹ thuật:
[Tesseract commands/TSV](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html),
[Modal images](https://modal.com/docs/guide/images),
[Modal Volumes](https://modal.com/docs/guide/volumes),
[Modal pricing](https://modal.com/pricing).
