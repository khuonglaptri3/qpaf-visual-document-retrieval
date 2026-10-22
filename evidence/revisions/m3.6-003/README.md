# M3.6 — Kết quả benchmark GPU và điểm cần giải quyết

**Latency, peak CUDA và CPU/GPU parity: PASS. Overall M3.6 review: BLOCKED bởi
CPU memory telemetry chưa đối chiếu được; owner acceptance/G2 chưa ghi nhận.**

Run `RUN-QPAF-M3_6-SYS-001-20261022T154348Z-A02` hoàn tất một GPU invocation.
Modal request `A10`, hardware thực tế **NVIDIA A10G**, driver610.57.04,
Python3.13.7/Torch2.11.0+cu126/CUDA12.6, FP64 eager, batch1, Torch threads1.
Image `im-XOLHqxG4nHp2fmqZ5DDCpy`; source
`6e2b93e3f3de93d9d9161ae556996f5289029737`.
App đã dừng, không còn task đang chạy.

## Số đo thực tế

| Đại lượng | QARF | QPAF | Gate |
| --- | ---: | ---: | --- |
| Median toàn đường fusion online | 3,043815 ms | 2,9618795 ms | <=10ms: PASS |
| p95 trên per-query medians | 3,1220565 ms | 3,036602 ms | Báo cáo, không phải gate |
| Peak CUDA allocated | 0,03244019 GiB | 0,03245258 GiB | <1,50GiB: PASS |
| Peak CUDA reserved | 34 MiB | 34 MiB | Báo riêng |
| Max score difference với CPU validation | 4,44089e-16 | 3,33067e-16 | <=1e-7: PASS |
| Max weight difference với CPU validation | 3,33067e-16 | 7,77156e-16 | <=1e-7: PASS |
| Query validation / candidates | 171 / 82.255 | 171 / 82.255 | Đủ coverage |
| Query đổi thứ hạng | 0 | 0 | Báo cáo |
| Dedicated warm-up queries | 20 | 20 | PASS |
| Unique measured queries × passes | 1.122 × 3 | 1.122 × 3 | >=1.000 unique: PASS |

Mỗi phương pháp có3.366 dòng timing, tổng6.732 dòng. Workload có20 warm-up
disjoint với1.122 measured IDs; gồm172 held-out IDs chỉ dùng text/raw cached
scores. Không deserialize/upload qrels, không training, không quality evaluation
hoặc checkpoint selection trên test.

Primary statistic là median trên1.122 per-query medians của3 passes. P95 là
query-distribution statistic, không phải service tail latency dưới tải.
Timing bao gồm instrumentation/synchronization và release tensors. Model CPU
feature code và gate khớp hashes của audit CPU trước đó. Peak allocator reset
trước load model, bao gồm parity, warm-up và measured inference; retrievers nằm
ngoài scope. Validation parity chạy trước dedicated warm-up và làm nóng thêm GPU.

| Median công đoạn, ms | QARF | QPAF |
| --- | ---: | ---: |
| CPU tensorization +13 features | 1,092779 | 1,088343 |
| H2D wall | 0,112532 | 0,111792 |
| Gate/fusion wall | 1,529925 | 1,4520795 |
| CUDA event interval | 1,497088 | 1,418240 |
| D2H + chuyển scores/weights sang Python | 0,130652 | 0,1301025 |
| Deterministic page ranking | 0,1610425 | 0,1610275 |

Median của các công đoạn không cộng thành median tổng. CUDA event interval chứa
cả khoảng trống do host/model validation đồng bộ, không gọi là kernel-only time.
Đây là page-level ViDoSeek pilot; document aggregation là NOT_APPLICABLE cho run
này, chưa thiết lập latency cho pipeline document-level ViMDoc.
Paired median QPAF−QARF là−0,0828365ms. QARF chạy trước QPAF trên cùng instance;
không counterbalance order và không lặp independent GPU instances, vì vậy không
khẳng định lợi thế tốc độ tổng quát từ chênh lệch nhỏ này.

## Vướng mắc cần giải quyết

`resource.getrusage(RUSAGE_SELF).ru_maxrss` báo5.111.088KiB cho QARF và
5.092.192KiB cho QPAF, tương ứng4,8743/4,8563GiB. Container được cấu hình request
và hard limit4.096MiB; run vẫn hoàn tất, không có OOM. Vì chưa có host/cgroup peak
hoặc provider telemetry tương ứng, **không kết luận đã chứng minh CPU RAM<4GiB**.

[Modal resource documentation](https://modal.com/docs/guide/resources) xác nhận
memory tuple có hard limit. [gVisor resource model](https://gvisor.dev/docs/architecture_guide/resources/)
giải thích thống kê trong sandbox có thể là xấp xỉ và khuyến nghị host/cgroup
accounting. Backend/version cụ thể của deployment này chưa được ghi nhận, nên
đây chỉ là cơ sở cho một khả năng, không chứng minh nguyên nhân của số đo này.
Giữ nguyên raw result; không sửa RSS thành
số mong muốn hoặc tự tăng limit để công nhận run.

Cần đối chiếu retrospective CPU-memory telemetry của provider/cgroup cho app
`ap-8PpAIo6k3BjeodZjRvdCTD`. Nếu dữ liệu không còn, một diagnostic có cgroup peak,
`/proc` và process RSS samples cần package/authorization mới; chưa chạy diagnostic
hoặc benchmark thứ hai. Chi tiết ở[telemetry_issue.json](telemetry_issue.json).

Do đó,[`_SUCCESS.json`](../../../../results/m3.6/RUN-QPAF-M3_6-SYS-001-20261022T154348Z-A02/_SUCCESS.json)
chỉ xác nhận execution và các gate latency/CUDA đã tính. Nó không thay thế
overall review, CPU memory reconciliation hoặc human acceptance. Giữ overall
review BLOCKED cho tới khi issue được giải quyết; chưa mở G2, remaining seeds,
confirmation hoặc external labels.

## Cơ sở nghiên cứu, kiểm chứng và provenance

Deepsearch hoàn tất trước GPU run; synthesis và primary references tại
[pre_execution_methodology_vi.md](../m3.6-002/pre_execution_methodology_vi.md).
Tiền lệ gồm[query-adaptive late fusion2018](https://arxiv.org/abs/1810.13103),
[hybrid fusion analysis](https://arxiv.org/abs/2210.11934),
[QuARI2025](https://arxiv.org/abs/2505.21647) và
[IR efficiency benchmarking](https://arxiv.org/abs/2212.01340).
Các paper có cơ chế/task khác; không dùng chúng làm bằng chứng QPAF đạt chất
lượng hoặc là phương pháp mới. Ngưỡng dự án không được gán cho paper.

- Full suite trên final executor: **439 tests OK,2 skipped**,215,907s.
- Focused M3.6:22 tests PASS; reviewer độc lập chạy10 focused tests và kiểm lại
 111 bundle hashes, coverage, arithmetic, parity và authorization/image bindings.
- Offline verifier độc lập tính median/p95 bằng NumPy; kết quả khớp trong1e-12.
  Receipt:[offline_verification.json](offline_verification.json).
- Raw[GPU result](../../../../results/m3.6/RUN-QPAF-M3_6-SYS-001-20261022T154348Z-A02/gpu_result.json)
  SHA256:`76ed5466b4c4202c551c31c55fd24a580d8d6273e65c1221a19d56134dd66943`.
- Namespace A01 giữ nguyên lỗi Windows cp1252 khi Modal in checkmark; zero GPU
  invocations, app đã dừng. Sau console fix được review, A02 tiếp tục thủ công
  bằng standing user instruction, source/bundle/auth mới. Không có auto retry.
- Remote function45,6475s; toàn app gồm build201,5215s. Allocated-rate estimate
  cho riêng45,6475s là khoảng0,01557USD, chưa gồm startup/build/lifecycle. Đây
  không phải invoice; actual billed total chưa được truy xuất, budget mục tiêu
 0,50USD không được gọi là provider hard dollar cap.
- Báo cáo CPU M3.6-001, các run/checkpoint M3.2/M3.4 và ledger cũ byte-stable.
  13 tracked deletions có sẵn tại workspace gốc được giữ nguyên.

Exact invocation nằm trong[execution_request.json](execution_request.json),
external authorization SHA trong cùng record; image/source/input binding được
ghi trước `.remote()` tại[runtime_binding.json](../../../../results/m3.6/RUN-QPAF-M3_6-SYS-001-20261022T154348Z-A02/runtime_binding.json).
