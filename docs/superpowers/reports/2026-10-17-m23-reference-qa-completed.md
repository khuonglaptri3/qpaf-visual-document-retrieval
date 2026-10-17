# M2.3 — Đã sửa và xác nhận bộ 18 bản chữ

**18/18 bản chữ đã được đối chiếu ảnh và lưu bản sửa.** Người dùng xác nhận
đã kiểm tra cả 18 trang và giao Codex đọc/sửa trực tiếp. Trạng thái hiện tại:
`REFERENCE_QA_COMPLETE_NATIVE_REVIEW_PENDING`; ngưỡng chưa đóng băng.

## DRAFT nằm ở đâu?

Trong [JSON nhận lúc 12:47 UTC](../../../results/m2.3/reviews/2026-10-17T124742274Z-khuong/human_reviews.original.json),
cả 18 bản đã nhập có `pages[…].reference.status="DRAFT"`, còn
`reference.reviewer=""` và `reference.reviewed_at=null`. Đây là trạng thái
lưu/xác nhận của giao diện; không phủ nhận việc người dùng đã kiểm tra nội dung.
Nhận xét trước đó đã chưa phân biệt rõ hai điều này.

Bản sửa dùng `CONFIRMED` cho đủ 18 trang, với reviewer
`Codex (AI visual QA; user-authorized)`. Việc người dùng đã kiểm tra được ghi
trong provenance; phần sửa do Codex chịu trách nhiệm, không gán tên/chữ ký
Khuong cho nội dung vừa sửa.

## Bản dùng tiếp

- [Mở giao diện có sẵn 18 bản sửa](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/index.html#reference):
  hiển thị 18 đã xác nhận /0 chưa xác nhận, không cần nhập hay xác nhận lại.
- [JSON sửa, nhập được vào giao diện review](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/human_reviews.corrected.json).
- [Đọc cả 18 bản chữ](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/references.md),
  [chi tiết trước/sau và lý do](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/change_log.json),
  [diff](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/changes.diff).
- [Manifest đúng 18 trang](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/reference_subset.json),
  [provenance](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/provenance.json),
  [summary/chỉ số](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/summary.json),
  [54 dòng metrics CSV](../../../results/m2.3/reviews/2026-10-17-reference-qa-final/page_metrics.csv).

JSON vẫn chứa đủ 121 trang để nhập đúng namespace. Chỉ 18 reference được sửa
trạng thái, trong đó 10 trang đổi text; 103 trang khác và tất cả đánh giá
native của người dùng được giữ nguyên. Run, ảnh, native gốc, OCR và dataset
hash vẫn là nguồn đã khóa. Giao diện bản sửa dùng overlay phạm vi 18 và vùng
lưu trình duyệt riêng, tránh nháp cũ che mất bản sửa.

## Nội dung đã xử lý

| STT | Kết quả |
|---|---|
| 3 | Giữ chữ trong timeline; bổ sung ba dấu đầu dòng vuông theo ảnh |
| 6 | Bổ sung word cloud, cả chữ dọc và các từ nhỏ đọc được |
| 9 | `Michael Porsker` → `Michael Porskær` |
| 15 | Đọc bảng theo từng hàng; đặt H8/H9/H10 cạnh đúng construct |
| 22 | Bổ sung năm nhóm mốc trục 0/2000/4000/6000/8000 và số hoàn chỉnh đọc được trên thước |
| 27 | Ghi rõ quy ước toán: `_` là chỉ số dưới, ngoặc nhóm chỉ số ghép, `²` là mũ |
| 30 | Bổ sung 22 nhãn bản đồ, gồm LEONIŠČE, ČRNUČE, KRŠKO, SEŽANA |
| 35 | Bổ sung YARA trong logo; đọc trọn từng cột; dùng dấu đầu dòng vuông |
| 36 | `2030E³` → `2030E²` ở Green ammonia; thêm YARA và dấu check |
| 42 | Sửa bốn số, dấu nháy cong, dấu phẩy thêm và dấu phẩy thật ở cuối đoạn |

Bốn số STT 42 sau sửa: `556973-2034`, `5 317 (2 898)`,
`13 702 (13 409)`, `48 035 (55 378)`.
Tám trang **8, 12, 17, 32, 38, 40, 41, 46** khớp ảnh và giữ nguyên nội dung.
STT 32 tiếp tục là trang không chữ, `no_text=true`.

Chỉ chép số hoàn chỉnh đọc được trên thước, không nội suy số bị cá che hoặc
bị cắt ở mép. Phần bị khuất/khó đọc được ghi ngoài text trong change log.
Word cloud, bảng, công thức và trang nhiều cột có quy ước thứ tự đọc rõ;
CER/WER chuỗi vẫn bao gồm ảnh hưởng của thứ tự và cách biểu diễn.

## Chỉ số tính lại sau sửa

NFC + gộp khoảng trắng; giữ case/số/dấu câu. Micro = tổng phép sửa chia tổng
ký tự/từ tham chiếu; trang không chữ không nằm trong mẫu số. Phạm vi giữ đúng
18 trang do người dùng chọn: 15 development, 3 holdout, 0 regression; 12 PDF.

| Kênh | Dev CER | Dev WER | Holdout CER | Holdout WER |
|---|---:|---:|---:|---:|
| Native | 32.75% | 34.74% | 35.18% | 38.27% |
| OCR 150 DPI | 26.90% | 32.93% | 36.22% | 41.98% |
| OCR 300 DPI | 25.08% | 31.94% | 39.75% | 48.15% |

Đây là độ lệch chuỗi toàn trang theo quy ước chép đã công bố, không phải tỷ lệ
ký tự nhận sai thuần túy. Không so bảng này với bảng bản nháp như cùng một
reference: bổ sung chữ trong hình và đổi cách đọc bảng đã đổi mẫu số/thứ tự.
Kết quả development và holdout không cùng ưu thế DPI; holdout chỉ có 3 trang.
Không chọn DPI hoặc suy rộng chất lượng toàn corpus từ các số này.

## Kiểm chứng và phần M2.3 còn lại

- [Kiểm tra dữ liệu/hash/metrics PASS](../../../results/m2.3/verification/reference-qa-integrity-2026-10-17.json):
  package gốc nguyên vẹn, đúng 18 page IDs, schema chấp nhận đủ 121 trang,
  54 dòng metrics; kiểm tra WER độc lập bằng dynamic programming và các tổng
  hợp; kiểm tra toàn bộ 121 link ảnh và hash.
- [Kiểm tra Edge PASS](../../../results/m2.3/verification/reference-qa-browser-2026-10-17.json):
  mở ảnh, thấy bản sửa, bộ lọc đúng 18, export/import/reload giữ nguyên dữ liệu,
  không có lỗi JavaScript.

**Không còn tồn đọng nhập/sửa/xác nhận của bộ 18 trong gói mới.** Còn:

1. Chốt 8 kết luận native: STT **37, 49, 50, 67, 93, 104, 109, 112**;
   trạng thái người dùng lưu vẫn là 107 PASS /6 HAS_ERRORS /7 PENDING /1 UNSURE.
2. Hoàn thiện phân tích lỗi và đề xuất cấu hình/ngưỡng, xử lý ý nghĩa PASS
   khi native thiếu chữ trong hình. 18 trang được chọn đều có nhãn native
   PASS, không chứa 6 ca HAS_ERRORS đã biết và không có reference regression;
   phải công bố các giới hạn này trong quyết định.
3. Review quyết định và tạo revision ngưỡng chính thức. `thresholds_frozen=false`.

Các báo cáo nhận xét/diagnostic lúc 12:47 được giữ làm lịch sử. Không yêu cầu
người dùng làm lại 18 trang hoặc tăng về 41 trang.

Tái tạo sang thư mục mới bằng:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/repair_m23_references.py `
  --output results/m2.3/reviews/<id-moi>
```

Patch có nội dung chép tay và lý do sửa ở
`configs/m2.3/reference_qa_18.json`; script từ chối ghi đè package đã tồn tại.
