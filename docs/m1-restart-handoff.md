# Bàn giao M1.1/M1.2 — trạng thái quan sát ngày 25/09/2026

Đọc cùng [README](../README.md), nơi có các bước thực hiện và tiêu chí
hoàn tất riêng cho Thanh và Phát. Tài liệu này ghi trạng thái bàn giao
hiện tại, không thay thế việc nhóm review hoặc quyết định G1.

## Nguồn và trạng thái

- Người giữ repo xác nhận các chữ Done trong milestone cũ chưa được cập
  nhật theo đợt làm lại. Sau đó đã cung cấp báo cáo Oracle có số liệu M1.1.
- Vì vậy M1.1 được ghi **REPORT AVAILABLE / RAW EVIDENCE PENDING**:
  có báo cáo, chưa tái lập từ artifact gốc trong repo.
- M1.2 chưa có method core/test nghiên cứu trong repo. M1.3 chưa có gói
  audit corpus để kiểm chứng. Không suy ra chưa từng có code/file ở nơi khác.
- Workbook và `TIMELINE_fixed.md` được giữ nguyên để truy nguồn. Các ngày,
  trạng thái trong chúng là thông tin của bản kế hoạch/snapshot trước.
- Hai tài liệu định hướng mô tả nghiên cứu dự kiến. Đề xuất đã thêm ghi
  chú tới báo cáo Oracle: Oracle có số liệu được cung cấp; learned QPAF
  chưa có kết quả kiểm chứng ở checkout này.

## Đầu vào cần bàn giao hoặc tạo mới

| Thành phần | Hiện có | Người điều phối / bước tiếp theo |
| --- | --- | --- |
| Đề xuất và tóm tắt định hướng | Có trong `docs/` | Cả nhóm đọc; Phát chốt quyết định đưa vào protocol |
| Báo cáo Oracle W7/W66 | Có file gốc và hash tại `results/m1.1/reference/` | Thanh đối chiếu và tìm artifact nguồn |
| Query IDs của Exploratory-24 | Chưa có | Thanh liên hệ người chạy; ghi hash và cách chọn tập query |
| Corpus/query/qrels/cache của run Oracle | Chưa có trong repo | Thanh xác định nguồn/revision/người giữ; Khương tiếp nhận manifest và vị trí |
| Code/config/log/output từng query của Oracle | Chưa có | Thanh nhận bản gốc hoặc tạo run mới có provenance |
| Method core QARF/QPAF và test | Chưa có | Phát xác định code cũ hoặc triển khai mới cho M1.2 |
| Định nghĩa 13 features và loss | Milestone nêu yêu cầu; chưa có đặc tả đủ chi tiết | Phát viết `docs/m1.2-method-core.md` và kiểm chứng |
| Gói audit primary corpus M1.3 | Chưa nhận được | Khương cùng Phát xác định corpus/phạm vi và nguồn hoặc phần cần tạo |
| Frozen protocol / registry | Chưa có | Phát làm M1.5; Thanh làm M1.7, nhận inventory dần từ Khương |

“Người điều phối” không có nghĩa người đó đang giữ toàn bộ file. Khi tìm
được người giữ dữ liệu, ghi tên người cung cấp và đường dẫn truy cập.

## Thứ tự phối hợp

1. Thanh đọc báo cáo, kiểm kê những artifact cần lấy lại cho M1.1. Nếu
   phải chạy mới, ghi rõ scope và cấu hình; giữ nguyên nguồn đã nhận.
2. Phát bắt đầu đặc tả và kiểm method core M1.2 bằng fixture phù hợp,
   song song với Thanh; không chờ kết quả Oracle đầy đủ để viết unit test.
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
- Bằng chứng method core: `results/m1.2/<run-id>/`.
- Dữ liệu lớn/cache: storage dùng chung hoặc các thư mục payload được
  Git bỏ qua; commit manifest, nguồn/revision, hash và đường dẫn truy cập.
- Run ID mới cho lần chạy mới; ghi thời gian thực tế, command, commit,
  config và các hash. Không ghi đè nguồn Oracle hoặc snapshot lịch sử.
- PR vào `develop`, có kết quả kiểm tra và một thành viên khác review.

Các đường dẫn output mô tả nơi cần bàn giao, không xác nhận file đã tồn
tại. Schema bảng từng query và tiêu chí M1.1/M1.2 nằm trong README.

## Những điểm cần Phát/nhóm quyết định

1. Corpus/revision cụ thể của M1.3 và quan hệ với bản ViDoSeek của Oracle.
2. Quyền sử dụng từng split/qrels; cách nhóm các query dịch; phạm vi
   chạy mới nếu artifact Oracle cũ không lấy được.
3. Định nghĩa 13 features, loss và shared config QARF/QPAF. Không lấy nhãn
   Oracle/test làm feature khi suy luận.
4. Ranh giới M1.8 và M2.3: M1.8 chuẩn bị OCR/failure policy, trong khi
   milestone dành M2.3 cho calibration trên mẫu và M2.6 cho full OCR.
   Các draft yêu cầu số ngưỡng có căn cứ; giá trị chưa đo/chưa review giữ
   trạng thái dự kiến, không tự gộp full OCR vào M1.

## Snapshot của đợt bàn giao

`evidence/revisions/m1.4-002-handoff/` ghi phiên bản source/tài liệu đã
commit trước khi tạo snapshot. Snapshot được commit sau source revision;
hai commit có vai trò khác nhau.

Các gap research code/data/config và thiếu artifact gốc vẫn được giữ rõ.
Báo cáo Word được inventory nhìn thấy là một asset ở `results/`, không
đồng nghĩa run gốc đã có đầy đủ provenance hoặc M1.1 đã được QA chấp nhận.
