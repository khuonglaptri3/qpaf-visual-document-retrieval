# Tổng quan phối hợp M1

**Cập nhật bàn giao ngày 25/09/2026:** nhóm bắt đầu bàn giao lại từ M1.1/M1.2.
M1.1 đã có [báo cáo Oracle](../results/m1.1/README.md), còn thiếu artifact gốc
để đối chiếu. M1.2 chưa có method core trong repo; M1.3 chưa có gói audit
để kiểm chứng. Xem [README](../README.md) và
[trạng thái bàn giao](m1-restart-handoff.md) cho phạm vi hiện tại.

Các bảng ngày dưới đây giữ lịch tham chiếu M1.4–M1.10 của
`TIMELINE_fixed.md`; không chứng minh các công việc trước đó đã Done.
Phạm vi calibration M1.8/M2.3 cần nhóm chốt như ghi trong tài liệu bàn giao.

Theo timeline của Khương (`TIMELINE_fixed.md:71`), công việc cụ thể và phụ thuộc như sau:

| Ngày | 23/9 – M1.4 |
| :--- | :--- |
| **Khương cần làm trong repo** | Tập hợp code, corpus, config, output/log cũ; kiểm kê vị trí, phiên bản, commit và hash; ghi rõ những gì thiếu hoặc chưa truy được nguồn. |
| **Cần nhận gì từ người khác?** | **Phát**: code và bằng chứng kiểm tra method core M1.2. **Thanh/người giữ run**: dữ liệu kết quả Oracle W7/W66, config/log liên quan. **Khương**: xác định/chuẩn bị gói primary-corpus audit M1.3; chưa có căn cứ giả định gói cũ đã được bàn giao. |
| **Đầu ra để kết thúc ngày** | Bộ `01_repository_audit/` phản ánh tài sản nghiên cứu thực tế; gap có nguyên nhân và người xử lý. Gửi inventory cho **Phát** và **Thanh**. |

| Ngày | 24/9 – M1.6 + nháp M1.8 |
| :--- | :--- |
| **Khương cần làm trong repo** | Lập page/alias manifest; chạy kiểm trùng nội dung, xung đột ID, alias lỗi, leakage giữa split và qrels trỏ sai. Song song soạn quy tắc OCR và nơi lưu output. |
| **Cần nhận gì từ người khác?** | **Phát**: dataset/split policy và quy tắc dùng qrels để chốt kiểm leakage. Có corpus là có thể bắt đầu kiểm ID/hash/duplicate. |
| **Đầu ra để kết thúc ngày** | Page manifest, alias manifest, duplicate report và collision report có kết quả thật; vấn đề nghiêm trọng được xử lý. Gửi **Thanh** review, **Phát** tổng hợp G1. |

| Ngày | 25/9 – M1.8 + G1 lần 1 |
| :--- | :--- |
| **Khương cần làm trong repo** | Chốt native text/OCR fallback, engine/version/config, tiêu chí chất lượng, timeout/ngưỡng lỗi có căn cứ; chốt cách đặt tên và lưu artifact. Đóng một revision evidence để review. |
| **Cần nhận gì từ người khác?** | **Phát**: frozen protocol và tiêu chí chấp nhận. **Thanh**: registry/naming đã freeze. Nhận findings từ QA của **Thanh**. |
| **Đầu ra để kết thúc ngày** | `ocr_checklist.md`, `ocr_failure_threshold.md`, `artifact_namespace.md` hoàn chỉnh; bàn giao M1.4/M1.6/M1.8 để nhóm review G1. |

| Ngày | 26/9 – sửa blocker |
| :--- | :--- |
| **Khương cần làm trong repo** | Sửa manifest/hash/collision/provenance/OCR bị phát hiện; tạo snapshot mới; chạy lại đúng phần kiểm tra bị ảnh hưởng. |
| **Cần nhận gì từ người khác?** | **Phát**: G1 blocker list, mức ưu tiên và điều kiện đóng issue. **Thanh**: kết quả audit và kiểm lại sau sửa. |
| **Đầu ra để kết thúc ngày** | Blocker kỹ thuật quan trọng được đóng bằng evidence; gửi kết quả cho G1 recheck. |

| Ngày | 27/9 – technical freeze |
| :--- | :--- |
| **Khương cần làm trong repo** | Kiểm lần cuối repo, data, hash, collision và OCR policy; chốt revision bàn giao; hoàn thành `technical_signoff.md`. |
| **Cần nhận gì từ người khác?** | Nhận kết quả xử lý/review các issue còn lại. **Thanh** thực hiện QA cuối song song. |
| **Đầu ra để kết thúc ngày** | Khương gửi **Technical Sign-off** cho **Phát**. **Phát** nhận thêm **QA Sign-off** của **Thanh**, rồi chốt Final G1, R1 và M1 closure. |

---

Với repo hiện tại, bạn cần bổ sung ba phần sau.

### 1. Hoàn tất đầu vào và kiểm kê M1.4.

Repo đã có công cụ audit, nhưng đang thiếu tài sản nghiên cứu để kiểm kê. Cần đưa vào đúng vị trí:

| Nội dung | Vị trí trong repo |
| :--- | :--- |
| Code nghiên cứu và lệnh chạy thực tế | `src/`, `scripts/` |
| Config đã dùng cho các run cũ | `configs/` |
| Nguồn/version dữ liệu, page IDs, split, qrels và hash | `manifests/` |
| Corpus thực tế | `data/` hoặc storage ngoài repo có đường dẫn rõ |
| Bảng kết quả nhỏ và liên kết tới output/log lớn | `results/` và inventory |

**File Word Oracle mới cung cấp bảng tổng hợp.** Để hoàn tất audit lịch sử, cần thêm output từng query, config, code/commit và dữ liệu đã dùng. Phần chưa lấy được phải giữ trong gap log.

Sau khi bổ sung asset, chạy snapshot mới từ thư mục gốc repo:

```bash
python scripts/audit_repository.py --root . --output evidence/revisions/m1.4-003
python scripts/audit_repository.py --root . --verify evidence/revisions/m1.4-003/hash_manifest.csv
```

Snapshot của đợt bàn giao nằm tại `evidence/revisions/m1.4-002-handoff/`; ví dụ trên dùng ID mới `m1.4-003` nếu chưa tồn tại. Snapshot cũ được giữ lại. Nếu corpus nằm ngoài repo, cần kiểm kê/hash riêng vì công cụ hiện tại chỉ quét bên trong repo. M1.4 được chốt sau khi review các gap và liên kết nguồn gốc.

---

### 2. Bổ sung công cụ và kết quả M1.6.

Repo hiện chưa có script collision audit; cần đưa công cụ cũ vào hoặc triển khai phần kiểm tra đã được giao. Kết quả phải điền vào:

```text
evidence/M1_FINAL/03_collision_audit/
├── page_manifest.csv
├── alias_manifest.csv
├── duplicate_report.csv
└── collision_report.md
```

Cần kiểm trên corpus thật, ghi số trang đã kiểm, từng vấn đề và cách giải quyết. Hash toàn PDF và hash nội dung từng trang phải được phân biệt.

---

### 3. Hoàn thiện M1.8 từ các bản nháp đang có.

Trong `05_ocr_artifacts/`, bạn cần bổ sung engine/version, cách chọn native text hay OCR, kết quả kiểm tra mẫu làm căn cứ cho ngưỡng, và namespace khớp với registry của Thanh. Theo lịch sửa, phần này phải đủ để review ngày 25/9. `technical_signoff.md` được hoàn tất ở bước bàn giao ngày 27/9.

Các kết quả cần chủ động lấy từ Phát và Thanh có thứ tự rõ ràng:

| Người | Bạn cần nhận | Việc của Khương phụ thuộc vào đó |
| :--- | :--- | :--- |
| **Phát** | Code/commit và bằng chứng M1.2 | Kiểm kê source và xác nhận trạng thái method core trong M1.4 |
| **Thanh/người giữ run** | Artifact gốc của Oracle W7/W66 và liên kết config–data–output | Hoàn tất run inventory và provenance M1.4 |
| **Phát** | `frozen_protocol.md`, dataset/split policy, run policy và tiêu chí chấp nhận | Chốt kiểm leakage, cách sử dụng dữ liệu và policy OCR |
| **Thanh** | Registry, naming rules, trường metadata bắt buộc, test classification | Chốt `artifact_namespace.md` |
| **Thanh** | Evidence audit và issue list | Sửa thiếu sót kỹ thuật ngày 26/9 |
| **Phát** | G1 blocker log và điều kiện đóng từng blocker | Xác định thứ tự sửa và phạm vi recheck |

Bạn có thể **làm ngay** phần tập hợp asset, kiểm kê, hash, kiểm ID/duplicate và soạn checklist OCR. Phần phải chờ đầu vào cụ thể là chốt leakage theo split của Phát và chốt namespace theo naming của Thanh. Phát cũng cần inventory của bạn để freeze protocol, nên nên bàn giao từng phần đã đủ sớm.

Với đợt bàn giao lại từ M1.1/M1.2, thứ tự phối hợp hiện tại là:

- **Trước hết**: Thanh xác định artifact của báo cáo Oracle; Phát bắt đầu method core và đặc tả còn thiếu. Khương ghi người cung cấp, vị trí và gap của từng đầu vào.
- **Khi nhận được đầu vào tương ứng**: kiểm gói M1.3 trong phạm vi cho phép, bổ sung M1.4, chạy M1.6 và chuẩn bị M1.8 theo phạm vi nhóm chốt. Bàn giao từng phần đã có cho review.
- **Khi đủ evidence**: chốt revision, technical review và QA, rồi chuyển Phát xem xét gate/report.

Các mốc 25–27/9 ở lịch cũ là mốc tham chiếu. Phát và cả nhóm cần đối chiếu
lại lịch với đầu vào và tiến độ thực tế của đợt làm lại; chưa có căn cứ
cam kết đóng M1 chỉ từ báo cáo Word hoặc từ số file đã tạo trong repo.
