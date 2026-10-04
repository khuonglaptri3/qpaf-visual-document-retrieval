# M1.1 — Oracle reference and reproduction

**Owner: Thanh. Status: ACCEPTED FOR ORACLE FEASIBILITY / REPRODUCTION UNVERIFIED.**

Xem [đối chiếu M1.1/M1.2 ngày 26/09/2026](../../docs/m1.1-m1.2-status.md)
cho kết quả kiểm tra phần mềm và phần nghiệm thu còn chờ.

Người phụ trách đã chấp nhận báo cáo Word này làm đầu ra đủ cho phạm vi M1.1
khảo sát tính khả thi và cho phép tiếp tục M1.2. Quyết định chấp nhận không xác
nhận đã nhận được raw evidence, tái lập số liệu hay review độc lập. Các bước
đối chiếu bên dưới được giữ cho công việc đánh giá tiếp theo.

Đã bổ sung [pipeline chạy mới trên Modal](../../docs/m1.1-modal-oracle.md), gồm
ViDoSeek adapter, BM25/dense/visual score cache, Oracle, config và provenance.
Đây là implementation mới; chưa thay thế artifact của báo cáo cũ. Chưa có run
nghiên cứu mới trên Modal được xác minh trong checkout này. Xem
[báo cáo kiểm phần mềm](implementation-check/README.md) để phân biệt log kiểm
phần mềm với kết quả corpus thật.

Đã nhận [báo cáo Word gốc](reference/oracle-progress-report.docx), tên file
nguồn `BÁO CÁO TIẾN ĐỘ ORACLE STUDY.docx`. Bản trong repo được copy nguyên
byte; thông tin import, kích thước và SHA-256 nằm trong
[source_manifest.csv](reference/source_manifest.csv).

Thời điểm import là thời điểm tiếp nhận tài liệu, không phải ngày chạy
thí nghiệm. File không đính kèm dữ liệu từng query, code/config/log hoặc
liên kết tới artifact nguồn. Hash này xác nhận tính toàn vẹn của báo cáo
được nhận, không xác nhận tính đúng của các số liệu thí nghiệm.

## Số liệu được báo cáo

Nguồn nêu dataset ViDoSeek và metric nDCG@10. Các giá trị dưới đây được
chép từ báo cáo, chưa được tính lại trong repo.

| Study | Phạm vi | Global | QARF | QPAF | QPAF − QARF | CI95 |
| --- | --- | --- | --- | --- | --- | --- |
| Full fixed-profile W7 audit | 1.142 query; 6.149.670 pair | 0.875138 | 0.908268 | Không báo cáo | Không báo cáo | Không báo cáo |
| Exploratory-24 W7 | 24 query; 129.240 pair | 0.817634 | 0.853845 | 0.903856 | +0.050011 | [0.008344, 0.101921] |
| Exploratory-24 W66 | Cùng 24 query; 66 bộ trọng số | 0.829678 | 0.853845 | 0.885911 | +0.032066 | [0.002888, 0.071165] |
| Pilot exploratory-12 W71 | 12 query; 64.620 pair | 0.952556 | 0.958333 | 1.0000 | +0.041667 | [0, 0.125] |

Báo cáo nêu không có query bị giảm điểm trong so sánh Exploratory-24,
nhưng chưa cung cấp bảng từng query hoặc số W/T/L đầy đủ. Cận dưới CI
của pilot W71 bằng 0; không gộp pilot vào nhận định CI dương của W7/W66.
Full fixed-profile 1.142 query không cung cấp QPAF, nên không mở rộng kết
luận QPAF của 24 query sang toàn bộ tập đó.

Kết luận trong nguồn chỉ nói QPAF Oracle có tiềm năng để nghiên cứu tiếp;
chưa chứng minh learned QPAF vượt QARF hoặc hiệu quả triển khai thực tế.

## Việc Thanh tiếp tục

Làm theo phần M1.1 trong [README chính](../../README.md):

- Nhận query IDs, corpus/query/qrels revision, score cache và candidate pool.
- Nhận code/commit, config, weight sets W7/W66, bootstrap config, log và
  output từng query; ghi người giữ/vị trí cho phần thiếu.
- Đối chiếu metric, delta, CI95 và W/T/L; lập báo cáo sai khác nếu có.
- Nếu tạo run mới, dùng `results/m1.1/<run-id>/` và bàn giao đủ provenance.
  Không sửa số liệu hoặc file trong `reference/` để khớp kết quả mới.

Payload lớn lưu ngoài Git cùng manifest và đường dẫn truy cập dùng chung.
