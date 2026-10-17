# M2.3 — Nhật ký thực hiện

## 2026-10-17 — Khóa protocol và preflight

- Người dùng giao triển khai M2.3, chạy lấy dữ liệu và trả về HTML để tự review;
  giữ cách viết/lưu specs, plans, progress, reports, run IDs và hashes như M2.2.
- Dùng skill Modal trong repo, kiểm tra SDK/CLI và docs chính thức. Không dùng
  GPU; job preflight CPU ở app `ap-S33BnEil3T4XDMrWW7VVQx` đã kết thúc.
- Đã đọc engine thật: Tesseract 5.3.0, Leptonica 1.82.0, language package
  1:4.1.0-2; SHA eng.traineddata
  `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
- Implement CPU-only worker, 2 subprocess x1 thread, paired 150/300 DPI,
  TSV/txt, timeout, source verification và báo cáo RSS gồm subprocess.
- Đợt test đầu phát hiện local chưa có psutil; cài đúng lock CPU-only rồi test
  lại. Không sửa môi trường PyTorch. 12 test M2.3 PASS, gồm 300 random cases
  so Levenshtein với DP độc lập và timeout dừng subprocess thật.
- Prototype browser cũ vẫn đạt 9 nhóm kiểm tra sau khi mở rộng template cho
  dữ liệu thật. Dữ liệu demo và dữ liệu calibration dùng namespace riêng.

## 2026-10-17 10:10–10:12 UTC — Chuẩn bị và bắt đầu run thật

- Prepare-only đầu: `RUN-QPAF-M2_3-CAL-001-20261017T101052Z-A01`. Không gọi
  inference cho run này; sau đó chuẩn hóa metric backend cho khớp whitespace
  của browser, tạo run mới để giữ đúng source snapshot.
- Run chọn để thực thi: `RUN-QPAF-M2_3-CAL-001-20261017T101215Z-A01`.
- Xác minh M2.1 và page manifest M1.6; 30 PDF / 120 trang + 1 regression page,
  tổng 121 trang / 31 PDF. Input khoảng 78.25 MiB.
- 80 development pages / 40 holdout pages / 1 regression; 41 references bắt buộc.
  Native có 99 trang text_present, 16 short, 6 empty. Đây là phân loại tự động,
  chưa phải kết luận chất lượng hoặc xác nhận trang không chữ.
- App thực thi: `ap-orUcQupV7t3JA4PEiTa6Ly`; CPU 4 cores /4096 MiB, không GPU,
  planning budget tối đa 1 USD, chưa thay workspace spend limit.
- Đang chạy paired OCR; cập nhật kết quả, hash và link review sau khi tải về.

## 2026-10-17 10:18–10:23 UTC — Giới hạn ảnh và protocol v2

- Lượt đầu hoàn tất: DATA_READY_WITH_ERRORS_REVIEW_PENDING, 226 OCR attempts,
  8 lỗi render do cap 32M pixels ở 300 DPI. Cả 8 trang đều giữ nguyên ID và
  còn ảnh 150 DPI; không coi là trang không chữ hoặc bỏ khỏi mẫu.
- Tài nguyên lượt đầu: wall 240.852 s, render 111.780 s, peak Python + children
  RSS 1092.676 MiB, output 285,583,303 bytes; không OOM, không GPU.
- Xác định 8 trang vuông của 2 PDF cần 36.0–36.013M pixels ở 300 DPI. Ghi
  protocol_revision m23-ocr-v2: nâng cap lên 40M, giữ 4096 MiB RAM và budget,
  thêm projected-pixel check trước cloud. Không đổi ngưỡng chất lượng, DPI,
  model, command, IDs, native text hoặc reference subset.
- Test v2: 13 tests PASS; receipt `results/m2.3/verification/tests-v2-2026-10-17.json`.
  Xác nhận source khớp run v2 và sample rows/native/PDF hashes/splits giống hệt parent.
- Run v2: `RUN-QPAF-M2_3-CAL-001-20261017T101949Z-A01`,
  app `ap-vKEqqDwHtAarWxn7LDUC24`. Lượt đầu được giữ nguyên, app đã stopped/tasks=0.
- Lượt v2 render đủ ảnh cho 121 trang và bắt đầu 242 OCR jobs (121 x 2 DPI).
- HTML dữ liệu thật của lượt đầu đã tải về và đạt 6 nhóm browser checks. Đây
  là kiểm tra chức năng bằng profile tạm, không đưa quyết định fixture vào human
  evidence. Giao diện cuối sẽ trỏ sang run v2 sau khi tải và verify xong.

## 2026-10-17 sau 10:27 UTC — Dữ liệu về local, kiểm tra và bàn giao

- Worker v2 kết thúc 10:27:22 UTC: DATA_READY_REVIEW_PENDING, đủ 242/242
  attempts, 0 lỗi kỹ thuật, không OOM/timeout/GPU. 118 OK +3 NO_TEXT_DETECTED
  cho mỗi DPI; trạng thái chất lượng ba trang empty vẫn chờ human review.
- Wall worker 285.917 s, render 131.058 s, RSS Python + descendants peak
  1281.484 MiB, output khoảng 301.16 MiB. Chi tiết percentile trong báo cáo.
- Đã tải toàn bộ về local, verify root/remote/input hashes và IDs thành công.
  Remote manifest SHA-256:
  `1f4a3de4a9bfd1aa5d1caba855b4be4943d951dc4dad9e789159aba0100761cf`.
- Client có cảnh báo timeout khi chờ final logs, nhưng worker đã hoàn tất và
  dữ liệu đã fetch/verify đầy đủ; không tính thành OCR timeout.
- HTML dữ liệu thật ở `results/m2.3/review/index.html`. Sau run sửa riêng
  presentation: filter tự chọn trang khớp, pagination đi trong bộ lọc, bước 4
  mặc định 41 references. Không thay OCR/sample/dataset hash. Template lúc run
  giữ trong source snapshot; UI bàn giao có hash riêng trong workspace.
- Browser real-data checks 6 nhóm PASS; backend xác nhận export đúng namespace,
  121 native pending /41 required references pending. Không dùng dữ liệu nhập
  trong profile test làm nhãn người review. Link HTML demo cũ chuyển đến dữ liệu thật.
- Ba app M2.3 stopped/tasks=0. Billing đọc được 0.08859549 USD gross trước credit,
  gồm cả preflight và lượt có cap errors; receipt scope M2.3 nằm ngoài revision.
- Báo cáo, runbook và checklist đã cập nhật. Chờ người dùng review;
  không nghiệm thu M2.3 hoặc freeze ngưỡng thay người dùng.
- Tạo revision dữ liệu `evidence/revisions/m2.3-001/` và điểm tra cứu
  `evidence/M2_FINAL/03_ocr_calibration/README.md`, ghi rõ engineering-only /
  human review pending. Đã verify hash revision, source Python, template bàn
  giao, liên kết tài liệu và redirect link HTML cũ sang workspace 121 trang.

## 2026-10-17 — Nhận và tổng hợp JSON review của Khuong

- Nhận `m23-review-2026-10-17T11-07-38-920Z.json` từ Downloads; xác minh đúng
  dataset/run, remote manifest, ảnh và 121 page IDs bằng summarizer local.
- Kết quả: 107 PASS, 6 HAS_ERRORS (đều `missing`), 7 PENDING, 1 UNSURE;
  113/121 native đã chốt, còn 8 trang. Không tự chuyển nháp thành đánh giá.
- Toàn bộ reference còn DRAFT/text rỗng; 0/41 full-page references bắt buộc
  được xác nhận. Chưa tính CER/WER, chưa chọn DPI hoặc freeze ngưỡng.
- Output bất biến mới: `results/m2.3/reviews/2026-10-17T110738920Z-khuong/`;
  summarizer exit 0, status `HUMAN_REVIEW_INCOMPLETE`.
- [Báo cáo tổng hợp và các trang còn thiếu](../reports/2026-10-17-m23-human-review-summary.md).
  Không sửa run hoặc revision dữ liệu `m2.3-001`.

## 2026-10-17 — Người dùng giảm phạm vi bản chữ đối chiếu xuống 18

- Người dùng nói "thôi 18 cái là được rồi" và xác nhận "Giữ 18 trang tôi đã làm".
- Ghi nhận yêu cầu 18 references thay cho 41 ban đầu; giữ đúng trang người dùng
  đã làm ở bước 4. Native vẫn có 121 trang; chưa có yêu cầu đổi phạm vi này.
- Chưa nhận JSON mới chứa 18 references. File trong Downloads vẫn là export
  `11-07-38-920Z` đã tổng hợp trước đó; không dùng thông báo tiến độ để tự tạo
  CONFIRMED labels hoặc suy ra page IDs.
- Đã cập nhật spec/kế hoạch. Cần export mới để khóa manifest 18 trang, kiểm tra
  phân bố split và tổng hợp CER/WER thực tế. HTML/summarizer còn tập 41 ban đầu.
- Các số đếm của summary cũ vẫn mô tả đúng export cũ; chưa đóng M2.3 hoặc freeze.

## 2026-10-17 12:47 UTC — Tự lấy 18 bản chữ và nhận xét theo yêu cầu

- Người dùng giao tự tải review đang làm trong browser và nhận xét. Đã tìm
  đúng dataset trong localStorage Edge Default, xuất bằng giao diện trong bản
  sao profile tạm; kiểm tra export giữ nguyên mọi page/nhãn của bản lưu browser.
- File Downloads: `m23-review-2026-10-17T12-47-42-274Z.json`. SHA-256:
  `3b6ca8f0beabede2c4c75396c6c97976a388a0d3687be63a5edc9bda02e1b69e`.
- Nhận đúng 18 trang: 17 bản có chữ, 1 no-text; toàn bộ còn DRAFT. Phân bố
  15 development /3 holdout /0 regression, thuộc 12 PDF. Native vẫn còn 8 trang
  chưa chốt; 18 references được chọn đều có nhãn native PASS.
- Backend import/hash verification thành công. Lưu kết quả protocol cũ ở
  `raw_validation/`; manifest 18 và 54 dòng metrics sơ bộ ở `diagnostic/`.
  Không đổi chữ ký, reference, native review hoặc dữ liệu OCR.
- Đã xem ảnh cả 18 trang: phát hiện thiếu word cloud/bản đồ/số trên trục,
  ký tự tên riêng, một số chú thích và bốn số tại STT 42. Chưa dùng CER/WER
  với bản nháp này để chọn DPI hoặc freeze ngưỡng.
- [Nhận xét đầy đủ](../reports/2026-10-17-m23-18-page-review.md).
- Thao tác xóa thư mục profile tạm bị tool policy chặn; thư mục
  `.superpowers/m23-review-browser/recovery-2026-10-17T12-47-41-439Z/` vẫn còn.

## 2026-10-17 13:13–13:20 UTC — Sửa và xác nhận bộ 18 theo chỉ dẫn người dùng

- Người dùng xác nhận đã kiểm tra 18 bản và giao Codex đọc/sửa trực tiếp.
  Giải thích DRAFT là trường reference.status trong file browser, không phải
  bằng chứng người dùng chưa kiểm tra. Không yêu cầu người dùng làm lại.
- Xem lại đủ 18 ảnh; bổ sung chữ trong word cloud/bản đồ/trục biểu đồ, sửa
  Porskær, chú thích 2030E², bốn số và dấu câu ở trang tài chính. Quy định rõ
  thứ tự bảng/cột, biểu diễn công thức và xử lý chữ số bị che/cắt trên thước.
- Lưu patch có lý do theo từng trang tại configs/m2.3/reference_qa_18.json;
  script scripts/repair_m23_references.py tạo package mới, từ chối ghi đè.
- Gói bàn giao: results/m2.3/reviews/2026-10-17-reference-qa-final/.
  Đủ 18 CONFIRMED dưới tên Codex (AI visual QA; user-authorized), 10 trang
  đổi text/cách đọc, 8 giữ nguyên, gồm một no-text. Giữ mọi native decision
  và 103 trang không thuộc phạm vi, không sửa run/OCR/revision m2.3-001.
- HTML có sẵn bản sửa, bộ lọc 18 và namespace lưu riêng. Lượt kiểm tra đầu
  phát hiện mở thẳng #reference còn liệt kê 121 trang; đã sửa khởi tạo filter
  và kiểm chứng lại. Một assertion Unicode truyền qua PowerShell→Node bị
  đổi æ thành ?; dùng Unicode escape để kiểm tra đúng ký tự, dữ liệu không lỗi.
- Kiểm chứng dữ liệu/hash và 54 metric rows PASS; WER kiểm tra độc lập bằng
  dynamic programming, mọi ảnh/link/hash khớp. Edge export/import/reload
  giữ đúng 121 record, giao diện 18 confirmed/0 pending, không lỗi JavaScript.
- Tính lại CER/WER riêng dev/holdout; chưa chọn DPI hoặc freeze. 8 kết luận
  native còn nguyên, cùng phân tích/đề xuất và quyết định revision ngưỡng.
- [Báo cáo QA hoàn tất và đường dẫn dùng tiếp](../reports/2026-10-17-m23-reference-qa-completed.md).

## 2026-10-17 — Deep research và đóng M2.3 theo yêu cầu người dùng

- Đọc nguồn gốc ViDoSeek/ViDoRAG và code PP-OCRv3 tác giả; tài liệu chính thức
  Tesseract, OCR-D và PyMuPDF. Đồ án giữ engine Tesseract đã pin, không tự đổi
  thành PP-OCR hoặc gọi VLM/GPU. Lưu protocol amendment hồi cứu trước bảng ứng viên.
- Xem ảnh8 native chưa chốt; thêm overlay 13 nhãn cũ mâu thuẫn phạm vi toàn trang.
  Kết quả95 PASS/25 HAS_ERRORS/1 NO_TEXT, không còn pending/unsure.100 quyết định
  gốc giữ nguyên,21 sửa/bổ sung mang tên Codex AI. Không thêm/sửa18 references.
- Phát hiện parser TSV coi dấu nháy là CSV quoting, ghép nhiều dòng vào token.
  Sửa QUOTE_NONE, test regression; tính lại242 confidence summaries,11 lượt đổi.
- So 8 ứng viên, chọn mixed300_c60 bằng macro retrieval-BWE development. Kết quả
  dev 11.32%, holdout mô tả8.46%; công bố CER/WER và micro/BWE strict để thấy đánh đổi.
- Implement policy bảo toàn native, bổ sung OCR không chồng native bằng union
  diện tích, crop-origin/rotation geometry, cảnh báo confidence và phân biệt
  NO_TEXT_DETECTED với lỗi kỹ thuật. Chốt timeout 15s/caps và operational stop 1%.
- Kiểm chéo phát hiện hash TOML tính trênLF nhưng Windows ghi CRLF; sửa ghi byte
  UTF-8 rõ ràng. Gói dùng tiếp: results/m2.3/closure/2026-10-17-closed/.
- 23 tests PASS; tái lập121 outputs, kiểm144 metric records, 17 WER độc lập bằng DP,
  BWE độc lập bằng sorted multisets và hash byte config trong mọi record. Edge
  kiểm121 native/18 refs, policy dropdown, export/import/reload đều PASS.
- Tạo config đã chốt và revision m2.3-002, cập nhật checklist 16/16 và hợp đồng
  M2.4/M2.6/M2.8. Không gọi full OCR/cache/training; quyết định đóng có giới hạn,
  reviewer Codex theo yêu cầu người dùng, không giả chữ ký nhóm/accuracy corpus.
