# M3.6 — Cơ sở phương pháp và giới hạn bằng chứng

Ngày tra cứu: 22/10/2026. Owner: Khương. Phạm vi hiện tại: independent integrity
review của hai pilot đã chạy; chuẩn bị protocol GPU để review, chưa chạy GPU.

## 1. Cách tìm và kiểm chứng nguồn

Đã thực hiện deep research qua TinyFish, run
`01a163df-57d7-72cc-83c1-a86514360b1a`, hoàn tất sau 720 giây, công cụ báo đã đọc
56 nguồn. Số nguồn tìm được không thay cho kiểm chứng. Bảng dưới chỉ sử dụng
nguồn gốc đã mở lại trực tiếp: bài của tác giả, JMLR/arXiv và tài liệu PyTorch.
Các nguồn gần đây hoặc mô tả thuật ngữ chưa kiểm chứng không được dùng để ra gate.

## 2. Công trình trước và phần được áp dụng

| Nguồn gốc | Công trình đã làm gì | Áp dụng và giới hạn trong QPAF |
| --- | --- | --- |
| Kennedy, Chang & Natsev, **Query-Adaptive Fusion for Multimodal Search**, Proceedings of the IEEE 96(4), 2008, DOI 10.1109/JPROC.2008.916345. [Bản tác giả](https://www.ee.columbia.edu/~lyndon/pubs/pieee2008-queryadaptive.pdf), abstract và §I | Tổng hợp cách điều chỉnh chiến lược/kết hợp modality theo query; phân tích sự thay đổi hiệu quả giữa các loại query. | Cơ sở cho việc so sánh adaptive fusion với weighting cố định. Đây không phải bằng chứng xác nhận công thức linear query-page 13-feature của repo, cũng không chứng minh tính mới của nó. |
| Wang, Zheng & Wang, **Query Adaptive Late Fusion for Image Retrieval**, 2018. [arXiv:1810.13103](https://arxiv.org/abs/1810.13103), abstract | Dùng dạng đường phân bố score để ước lượng hiệu quả feature theo query; có biến thể hand-crafted và neural trainable. | Tiền lệ về query-adaptive score fusion trong image retrieval. Khác nhiệm vụ, modality, features và loss; không được gọi là implementation QPAF tương đương. |
| Santhanam et al., **Moving Beyond Downstream Task Accuracy for Information Retrieval Benchmarking**, 2022. [arXiv:2212.01340](https://arxiv.org/abs/2212.01340), abstract | Đề nghị đánh giá retrieval cùng query latency, hardware và cost budget có thể tái tạo, thay vì chỉ accuracy. | Cơ sở để báo đúng hardware/runtime/cost và tách quality khỏi resource. Bài không đặt ngưỡng 10 ms hoặc 1,50 GiB cho dự án này. |
| Cawley & Talbot, **On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation**, JMLR 11:2079–2107, 2010. [Bản gốc](https://www.jmlr.org/papers/v11/cawley10a.html), abstract và bài đầy đủ được trang này liên kết | Phân tích overfitting vào criterion chọn model trên một mẫu hữu hạn và selection bias của ước lượng performance. | Cả hai checkpoint được chọn trên chính validation đang báo cáo. M3.5 là một-seed development comparison, chưa phải held-out confirmation; M3.6 không khắc phục được bias bằng việc reload. |
| PyTorch **Serialization semantics**, [2.11](https://docs.pytorch.org/docs/2.11/notes/serialization.html), lưu/nạp state dictionaries và `weights_only` | Mô tả cách nạp state và giới hạn của pickle/checkpoint loading. | Kiểm hash trước `load_checkpoint`; loader hiện có dùng `torch.load(..., weights_only=True)`. SHA-256 là binding của artifact, không chứng minh model có chất lượng. |
| PyTorch **Reproducibility**, [2.11](https://docs.pytorch.org/docs/2.11/notes/randomness.html) | Nêu giới hạn tái tạo giữa release/platform và cách bật deterministic algorithms. | Replay trong interpreter mới với đúng phiên bản CPU đã duyệt, source path trong checkout, float64/1 thread. CPU PASS không được chuyển thành GPU PASS. |
| PyTorch **Benchmark Utils**, [API](https://docs.pytorch.org/docs/main/utils/benchmark.html), phần Timer; [tutorial](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html) | Kiểm soát warm-up, thread pool, replicate và synchronization; blocked autorange giảm timer overhead. | Cơ sở kỹ thuật để kiểm soát những yếu tố này. Không coi p95 của block-averaged timings là request-tail p95, và không coi ví dụ `min_run_time=1` là ngưỡng bắt buộc từ literature. |
| PyTorch **CUDA Event**, [2.11](https://docs.pytorch.org/docs/2.11/generated/torch.cuda.Event.html) | CUDA events đo khoảng thời gian trên device; CUDA thực thi bất đồng bộ. | Gói GPU đề xuất dùng event cho gate/fusion, synchronized wall timer cho toàn đường fusion; báo H2D/D2H riêng. Đây mới là protocol đề xuất, chưa có kết quả. |

## 3. Quyết định nào đến từ protocol dự án

Nguồn có hiệu lực cho operational gates là
[`metric_policy.md` §5](../../M1_FINAL/02_protocol/metric_policy.md), đối chiếu
với [`shared_base.toml`](../../../configs/m2.7/shared_base.toml) và authorization
M3.2/M3.4. Các số sau là **ngưỡng dự án**, không phải các bài trên quy định:

- Reload score absolute tolerance `1e-7`.
- 20 warm-up và ít nhất 1.000 query label-free được đo.
- Median added fusion latency `<= 10.0 ms/query`.
- Peak learned-fusion CUDA allocation `< 1.50 GiB`.

Không thay threshold sau khi thấy kết quả. M3.5 đã dùng paired query bootstrap
10.000 lần theo protocol; M3.6 không thêm Wilcoxon/t-test hoặc điều chỉnh alpha
hậu nghiệm. Có hai method không tự động có nghĩa là có hai statistical comparisons.

## 4. Audit CPU thực hiện như thế nào

1. Kiểm external authorization/prediction pins và replay M3.1 seal bằng manifest
   SHA-256 đã được chốt ngoài payload.
2. Kiểm supervisor markers, receipt và đủ 16 output của mỗi run; kiểm source
   commit/provenance, input hashes, method/seed/config và test boundary.
3. Kiểm epoch/step CSV: loss, gradient norm và counters hữu hạn; coverage của
   steps phải khớp `train_steps` từng epoch. Kiểm model/optimizer tensors và số
   trong best/last checkpoint. Gradient tensor của từng step không được lưu,
   nên không tuyên bố đã kiểm lại từng gradient; source trainer có finite guard.
4. Mỗi method chạy trong Python child process mới. Nạp checkpoint đã kiểm hash,
   dùng source từ checkout, dựng lại validation records, scores và weights.
   Kiểm NaN/Inf trước khi tính max difference, so sánh theo query/page order,
   ghi riêng ranking disagreements và tính lại metrics từ development qrels.
5. Đối chiếu telemetry CPU với giới hạn run đã duyệt. Phase seconds và CPU RSS
   chỉ là telemetry của run đó; CUDA allocation bằng 0 trong CPU run không là
   phép đo gate GPU.

Audit không chạy optimizer, không sửa các run cũ, không deserialize test qrels,
không chọn lại checkpoint và không quyết định G2 thay owner.

## 5. Vướng mắc cần review trước phép đo GPU

**Workload:** train + validation chỉ có 799 + 171 = 970 query. Đề xuất dùng toàn
bộ 1.142 ID đã seal, chọn 20 warm-up và 1.122 measured bằng SHA-256 có namespace
cố định. Hai nhóm không giao nhau, selection không có labels/model outputs.
Workload chứa 172 held-out test ID. Việc đọc text/score label-free của các ID này
vẫn cần được chấp nhận rõ; chưa được thực thi từ preparation này. Không gọi
query repetitions là query mới. Nếu nhóm muốn giữ cả text/score test hoàn toàn
untouched, phải chọn workload khác hoặc có amendment; không tự hạ ngưỡng 1.000.

**Scope latency:** đề xuất đo toàn bộ fusion online sau khi raw retriever scores
đã nằm trong RAM: tensorization/features, transfer, gate/fusion và ranking;
ghi riêng từng stage. Đồng thời báo delta QPAF−QARF. Không chỉ dùng delta này để
thay cho tổng overhead fusion. Cold start/load và retriever extraction báo riêng.
`p95 across per-query medians` là độ phân tán theo query, không phải service-tail
latency dưới tải đồng thời. Cần owner chốt cách hiểu 10 ms trước execution.

**Page/document:** active pilot là ViDoSeek page-level theo A002/A003 và run
authorization. Metric policy gốc còn mô tả ViMDoc document-level. Gói mới giữ
page ranking của pilot và đề nghị ghi rõ phạm vi này trong review; không tự
thêm document aggregation vào run cũ.

**Hardware/runtime:** máy local được phát hiện có RTX 2050 4 GiB, driver 546.18,
nhưng interpreter pilot là Torch CPU. Chưa thử CUDA, cài CUDA wheel hoặc sửa
driver. Đề xuất Modal A10, một GPU, FP64, CPU 1 thread cho xử lý feature, tối đa
900 giây, một invocation, không retry. CUDA Torch 2.11.0 có build cu126 chính
thức theo [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/).
Image identity và GPU executor phải được hoàn thiện/review trước xin execution.

**Budget:** giá niêm yết [Modal](https://modal.com/pricing) kiểm ngày 22/10/2026:
A10 `0.000306 USD/s`, CPU `0.0000131 USD/core/s`, RAM `0.00000222 USD/GiB/s`.
Với 2 physical CPU cores, 4 GiB RAM và 900 giây, phần allocated compute ước tính
`0.306972 USD`. Đề nghị budget 0,50 USD; đây chưa là hard bound cho image build
và lifecycle. Phải bổ sung bound/cost policy trước approval. Chưa phát sinh GPU
run từ task này.

Ba passes, batch size 1, namespace hash và lựa chọn A10 là **engineering choices
đang đề xuất để review**. Literature hỗ trợ nguyên tắc warm-up/repeat/control,
không bắt buộc chính xác những lựa chọn này.

## 6. Giới hạn của tra cứu

Tra cứu này không chứng minh chưa từng có công trình query-document adaptive
fusion. Các tên QARF/QPAF/CARF trong repo không đủ để nhận diện hay phân biệt
algorithm của một bài báo khác. Cần so sánh công thức, input, training objective,
candidate/evaluation protocol và code khi viết related work; không suy novelty
từ việc không tìm thấy một acronym. Nguồn không xác minh được không được dùng
để đổi phương pháp hoặc điều kiện nghiệm thu.
