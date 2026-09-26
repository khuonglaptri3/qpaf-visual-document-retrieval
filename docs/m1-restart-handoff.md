# Bàn giao M1.1/M1.2 — cập nhật ngày 26/09/2026

Đọc cùng [README](../README.md), nơi có các bước thực hiện và tiêu chí
hoàn tất riêng cho Thanh và Phát. Tài liệu này ghi trạng thái bàn giao
hiện tại, không thay thế việc nhóm review hoặc quyết định G1.

Nhánh bàn giao code: `feature/m1-1-m1-2-handoff`, đích tích hợp `develop`.
Xem [bảng đối chiếu tiêu chí và kiểm thử](m1.1-m1.2-status.md).

## Nguồn và trạng thái

- Người giữ repo xác nhận các chữ Done trong milestone cũ chưa được cập
  nhật theo đợt làm lại. Sau đó đã cung cấp báo cáo Oracle có số liệu M1.1.
- M1.1 được người phụ trách chấp nhận ở phạm vi **khảo sát khả thi Oracle**;
  tái lập từ artifact gốc và run corpus thật chưa xác minh. Đã có pipeline
  mới, config và test fixture trong repo.
- M1.2 đã hoàn thành **implementation và kiểm chứng phần mềm cục bộ**:
  13 features, gate QARF/QPAF, fusion, loss và gradient. Thành viên khác
  chạy lại/ghi nghiệm thu còn chờ. Chưa có kết quả learned trên corpus thật.
- M1.3 chưa có gói audit corpus để kiểm chứng; chưa đủ căn cứ đóng M1/G1.
- Workbook và `TIMELINE_fixed.md` được giữ nguyên để truy nguồn. Các ngày,
  trạng thái trong chúng là thông tin của bản kế hoạch/snapshot trước.
- Hai tài liệu định hướng mô tả nghiên cứu dự kiến. Đề xuất đã thêm ghi
  chú tới báo cáo Oracle: Oracle có số liệu được cung cấp; learned QPAF
  chưa có kết quả kiểm chứng ở checkout này.

## Đầu vào cần bàn giao hoặc tạo mới

| Thành phần | Hiện có | Người điều phối / bước tiếp theo |
| --- | --- | --- |
| Đề xuất và tóm tắt định hướng | Đề xuất trong `docs/GUILDLINE_OVERVIEWS_PROPOSAL/`; tóm tắt trong `docs/` | Cả nhóm đọc; Phát chốt quyết định đưa vào protocol |
| Báo cáo Oracle W7/W66 | Có file gốc và hash tại `results/m1.1/reference/` | Thanh đối chiếu và tìm artifact nguồn |
| Query IDs của Exploratory-24 | Chưa có | Thanh liên hệ người chạy; ghi hash và cách chọn tập query |
| Corpus/query/qrels/cache của run Oracle | Chưa có trong repo | Thanh xác định nguồn/revision/người giữ; Khương tiếp nhận manifest và vị trí |
| Code/config/log/output từng query của Oracle | Chưa có | Thanh nhận bản gốc hoặc tạo run mới có provenance |
| Method core QARF/QPAF và test | `src/qpaf/m12/`, 25 test M1.2 đạt; bằng chứng tại `results/m1.2/` | Phát bàn giao; thành viên khác chạy lại từ checkout sạch |
| Định nghĩa 13 features và loss | Schema `qpaf13_v1`, pairwise logistic loss trong `docs/m1.2-method-core.md` | Review lựa chọn v1 và chốt protocol cho dữ liệu thật |
| Gói audit primary corpus M1.3 | Chưa nhận được | Khương cùng Phát xác định corpus/phạm vi và nguồn hoặc phần cần tạo |
| Frozen protocol / registry | Chưa có | Phát làm M1.5; Thanh làm M1.7, nhận inventory dần từ Khương |

“Người điều phối” không có nghĩa người đó đang giữ toàn bộ file. Khi tìm
được người giữ dữ liệu, ghi tên người cung cấp và đường dẫn truy cập.

## Thứ tự phối hợp

1. Thanh đọc báo cáo, kiểm kê những artifact cần lấy lại cho M1.1. Nếu
   phải chạy mới, ghi rõ scope và cấu hình; giữ nguyên nguồn đã nhận.
2. Phát bàn giao đặc tả, code và bằng chứng M1.2 đã có; thành viên khác
   chạy lại theo README và ghi review bằng run ID mới.
3. Khương chuẩn bị/kiểm gói audit M1.3 trong phạm vi được phép và tiếp nhận
   từng phần code/data/config/output vào inventory M1.4.
4. Phát dùng inventory để chốt protocol; Thanh đồng bộ registry/naming.
   Khương dùng các đầu vào tương ứng để hoàn thiện M1.6 và M1.8.

Không coi các số M1.1 → M1.2 → M1.3 là một chuỗi bắt buộc hoàn toàn tuần tự.
Mỗi phần chờ đúng đầu vào mà phần đó cần.

## Quy ước đầu ra

- Output Oracle mới: `results/m1.1/<run-id>/`.
- Đặc tả method core: `docs/m1.2-method-core.md`; code/test/config nằm ở
  `src/qpaf/`, `tests/`, `configs/`.
- Bằng chứng method core: `results/m1.2/<run-id>/verification/<attempt-id>/`.
- Dữ liệu lớn/cache: storage dùng chung hoặc các thư mục payload được
  Git bỏ qua; commit manifest, nguồn/revision, hash và đường dẫn truy cập.
- Run ID mới cho lần chạy mới; ghi thời gian thực tế, command, commit,
  config và các hash. Không ghi đè nguồn Oracle hoặc snapshot lịch sử.
- PR vào `develop`, có kết quả kiểm tra và một thành viên khác review.

Các run cụ thể đã có được liên kết trong `results/m1.1/README.md` và
`results/m1.2/README.md`. Schema bảng từng query và tiêu chí nằm trong README.

## Những điểm cần Phát/nhóm quyết định

1. Corpus/revision cụ thể của M1.3 và quan hệ với bản ViDoSeek của Oracle.
2. Quyền sử dụng từng split/qrels; cách nhóm các query dịch; phạm vi
   chạy mới nếu artifact Oracle cũ không lấy được.
3. Chốt protocol dữ liệu thật cho 13 features, loss và shared config đã có
   ở v1; chúng chưa được chứng minh tối ưu bằng thực nghiệm. Không lấy nhãn
   Oracle/test làm feature khi suy luận.
4. Ranh giới M1.8 và M2.3: M1.8 chuẩn bị OCR/failure policy, trong khi
   milestone dành M2.3 cho calibration trên mẫu và M2.6 cho full OCR.
   Các draft yêu cầu số ngưỡng có căn cứ; giá trị chưa đo/chưa review giữ
   trạng thái dự kiến, không tự gộp full OCR vào M1.

## Snapshot của đợt bàn giao

`evidence/revisions/m1.4-002-handoff/` ghi phiên bản source/tài liệu đã
commit trước khi tạo snapshot. Snapshot được commit sau source revision;
hai commit có vai trò khác nhau.

Snapshot này mô tả đợt 25/09 trước implementation M1.1/M1.2; gap code/config
trong snapshot cũ không phải trạng thái hiện tại. Gap corpus và artifact gốc
vẫn còn. Kiểm hash lịch sử trên source revision được ghi trong metadata.
Báo cáo Word được inventory nhìn thấy là một asset ở `results/`, không
đồng nghĩa run gốc đã có đầy đủ provenance hoặc M1.1 đã được QA chấp nhận.
