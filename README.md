# QPAF — Query-Page Adaptive Fusion

Repository này gom công cụ oracle trong `src/oracle_study` và các module nghiên cứu M1–M2.1 trong `src/qpaf`.

## Trạng thái sau khi tích hợp các branch

- Hồ sơ M1 đã có [biên bản đóng milestone](evidence/M1_FINAL/07_R1/M1_closure_record.md) và [quyết định G1 `CONDITIONAL_PASS`](evidence/M1_FINAL/06_G1/G1_final_decision.md), ban hành ngày 29/09/2026.
- M2.1 chọn [revision `m2.1-002`](evidence/revisions/m2.1-002/README.md), với train/validation/test **799/171/172 query** và kiểm chứng được ghi ngày 04/10/2026. Raw corpus cần được tái tạo riêng trên máy chạy.
- Các hồ sơ trên được nhập từ `khuong/develop`; việc merge không chạy lại corpus audit, huấn luyện hoặc suy luận.
- Đọc [bảng nghiệm thu và runbook M1](docs/06_handover/M1_ACCEPTANCE_SUMMARY_AND_RUNBOOK.md), [bản rà soát readiness](docs/06_handover/m1.1-m1.8-readiness-audit-2026-09-28.md) và [bản tổng quan từ repo nguồn](docs/01_overview/QPAF_PROJECT_SYNTHESIS_SOURCE.md).

Các đoạn oracle và run lịch sử bên dưới giữ phạm vi, kết quả và ranh giới của từng study. Đặc tả M1.2 hiện tại nằm ở [method core](docs/03_method/m1.2-method-core.md); phần tổng quan từ repo nguồn có ghi chú khi mô tả khác code.

## Tài liệu và milestone

Bắt đầu tại [mục lục tài liệu](docs/README.md). Các tài liệu được phân nhóm theo tổng quan, kế hoạch, phương pháp, dữ liệu, thí nghiệm và bàn giao.

- [Milestone hoàn chỉnh](docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx), sheet `Milestones`.
- [Tổng quan phối hợp](docs/GUILDLINE_OVERVIEWS_PROPOSAL/overview.md) và [timeline tham chiếu](docs/GUILDLINE_OVERVIEWS_PROPOSAL/TIMELINE_fixed.md).
- [Đề xuất nghiên cứu](docs/GUILDLINE_OVERVIEWS_PROPOSAL/DE_XUAT_NGHIEN_CUU_QPAF.md).
- [Checklist của Khương](docs/06_handover/khuong-m1-checklist.md), [báo cáo audit M1.4–M1.6](docs/06_handover/m1.4-m1.5-m1.6-audit-report.md) và [gói bằng chứng M1](evidence/M1_FINAL/README.md).

Các trạng thái trong tài liệu bàn giao là snapshot theo thời điểm của repo nguồn. Đối chiếu artifact, amendment và review trước khi cập nhật trạng thái milestone.

Package này triển khai phần **oracle analysis** của hai hướng nghiên cứu:

- QPAF: so sánh query-level fusion với candidate-conditioned fusion.
- Budget-Aware HEAVEN: đo quality–Stage-2-invocation Pareto frontier.

Package không train router/gate và không thay thế official HEAVEN retrieval. Score DSE,
ColQwen2.5, BM25 và BGE-M3 phải được tạo trong môi trường cloud/GPU rồi xuất theo
raw-score contract bên dưới. `sources/` không bị chỉnh sửa.

## Pilot ngắn ViDoRe V3 Finance EN

Notebook [vidore_v3_short_oracle.ipynb](notebooks/vidore_v3_short_oracle.ipynb) là
artifact Colab tự chứa cho feasibility pilot đã đăng ký trước:

- dataset `vidore/vidore_v3_finance_en` tại revision
  `7f432c176d82e27546501ad8064a713ac3071809`;
- toàn bộ 309 query tiếng Anh và 2.942 trang;
- Global Fusion, QARF và constrained QPAF với `W7`;
- candidate pool `DSE Top200 ∪ BM25 Top100 ∪ BGE Top100`, mở rộng đúng một lần khi
  coverage dưới 95%;
- paired bootstrap 2.000 lần và feasibility report cho riêng hai bước
  `Global → QARF` và `QARF → QPAF`.

Cách chạy:

1. Tải notebook lên Google Colab và chọn A100 hoặc GPU có ít nhất 24 GB VRAM.
2. Chạy lần lượt mọi cell và cấp quyền mount Google Drive.
3. Nếu runtime bị ngắt, mở lại và chạy từ đầu; embedding/score checkpoint trong
   `MyDrive/vidore_v3_finance_en_short_oracle/cache` sẽ được dùng lại.
4. Đọc kết quả tại thư mục `output`, đặc biệt là `pilot_feasibility.md`,
   `fusion_oracle_summary.json` và `global_qarf_qpaf_oracle.png`.

Notebook dừng thay vì kết luận nếu GPU dưới 24 GB hoặc candidate coverage vẫn dưới 95%.
Khi OOM, nó chỉ hạ batch size trong danh sách đã đóng băng; model và candidate pool
không bị thay đổi. File nguồn sinh notebook là
`notebooks/build_vidore_v3_short_oracle.py`; chạy lại file này sau khi sửa lõi oracle
để cập nhật phần implementation được nhúng vào notebook.

### Chạy trên Kaggle

Dùng [vidore_v3_short_oracle_kaggle.ipynb](notebooks/vidore_v3_short_oracle_kaggle.ipynb):

1. Tạo Kaggle Notebook, chọn **File → Import Notebook** và tải file `.ipynb` lên.
2. Bật **Internet** và chọn GPU có ít nhất 24 GB VRAM. P100/T4 16 GB sẽ bị preflight
   từ chối để không làm thay đổi protocol.
3. Chạy toàn bộ cell bằng **Save Version → Save & Run All**. Artifact cuối được ghi vào
   `/kaggle/working`; model và embedding cache lớn nằm trong `/kaggle/temp` để không làm
   Kaggle Output vượt dung lượng.
4. Chỉ xem run là hoàn tất khi `_SUCCESS.json` xuất hiện. Cell cuối kiểm tra đủ mười
   artifact bắt buộc, ghi SHA-256, tạo `artifact_manifest.json` và đóng gói
   `vidore_v3_finance_en_short_oracle_results.zip`.

Các file dễ đọc được đặt ngay ở Kaggle Output:

- `PILOT_FEASIBILITY.md` — kết luận feasibility cho Global → QARF và QARF → QPAF;
- `global_qarf_qpaf_oracle.png` — biểu đồ so sánh ba tầng;
- `fusion_oracle_summary.json` — metric tổng hợp;
- `README_RESULTS.md` — hướng dẫn đọc artifact;
- `_SUCCESS.json` — completion marker và hash của ZIP;
- `vidore_v3_finance_en_short_oracle_results.zip` — toàn bộ artifact đầy đủ.

Nếu đã lưu cache từ một lần chạy trước thành Kaggle Dataset với slug
`vidore-v3-short-oracle-cache`, attach dataset đó vào notebook. Notebook ưu tiên checkpoint
tạm của run hiện tại, sau đó mới đọc cache bất biến từ `/kaggle/input`.
File sinh phiên bản Kaggle là `notebooks/build_vidore_v3_short_oracle_kaggle.py`.

## 1. Cài đặt

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## 2. Raw-score contract

Mỗi hàng tương ứng một `(dataset, query_id, page_id)` và phải có:

```text
dataset, query_id, page_id, source, relevance,
bm25_score, dense_score, stage1_score, visual_score, full_score,
stage2_ms, stage2_flops
```

- Candidate construction chỉ dùng branch scores/ranks; `relevance` chỉ dùng để đo coverage.
- Raw table phải chứa đủ scored pages để hình thành ít nhất union Top300/Top200/Top200
  và phải chứa relevant pages để audit coverage.
- `stage1_score` là output HEAVEN Stage 1.
- `visual_score` là ColQwen2.5 score dùng cho QPAF.
- `full_score` là final HEAVEN Stage 1 + Stage 2 score.
- Latency dùng CUDA event sau 50 warm-up query, median ba lượt cùng query order.

Official HEAVEN configuration:

```text
stage1_model=dse, stage2_model=colqwen25,
reduction_factor=15, alpha=0.1, filter_ratio_stage1=0.5,
k=200, filter_ratio_stage2=0.25, beta=0.3
```

Trong official repository, Stage 1 score được cache bởi `heaven.py`; khi chạy cloud,
export `stage1_scores` và `final_scores` ngay trước lời gọi `evaluate(...)`, đồng thời
export BM25/BGE-M3/ColQwen2.5 score theo page mapping. Không dùng qrels để thêm page
vào candidate union.

Lưu ý kỹ thuật: `Stage2Retrieval.filter_and_combine()` của upstream mask score tensor tại
chỗ. Vì vậy raw ColQwen2.5 score cho QPAF phải được snapshot trước lời gọi này; chi tiết
hook nằm trong `docs/04_data_protocol/heaven_export_contract.md`.

Với benchmark thật, nên export thêm `official_query_metrics.parquet` trực tiếp từ
ranking trên **toàn bộ corpus**, theo schema `query_metrics.parquet`. Raw score table
có thể chỉ chứa union candidate và các relevant page dành cho audit; không dùng metric
tính lại trên bảng rút gọn làm kết quả chính.

## 3. Discovery workflow

```powershell
oracle-study manifest --heaven-root D:\HEAVEN `
  --dataset-file D:\data\ViDoSeek\test.json `
  --checkpoint-revision DSE=<revision> `
  --checkpoint-revision ColQwen2.5=<revision> `
  --output runs\discovery\run_manifest.yaml

oracle-study build-cache --raw runs\discovery\raw_scores.parquet `
  --query-metrics runs\discovery\official_query_metrics.parquet `
  --output-dir runs\discovery

oracle-study preflight `
  --scores runs\discovery\retrieval_scores.parquet `
  --metrics runs\discovery\query_metrics.parquet `
  --reference-means runs\discovery\paper_sample_means.json `
  --output runs\discovery\preflight.json

oracle-study qpaf --scores runs\discovery\retrieval_scores.parquet `
  --output-dir runs\discovery\qpaf

oracle-study budget --metrics runs\discovery\query_metrics.parquet `
  --output-dir runs\discovery\budget
```

`build-cache` tự thử candidate pool Top200/100/100, mở rộng đúng một lần thành
Top300/200/200 khi coverage dưới 95%, và dừng bằng lỗi nếu vẫn không đạt.
Nếu bỏ `--query-metrics`, công cụ tính metric từ raw table chỉ để smoke test; report sẽ
ghi rõ `query_metrics_source=raw_score_table`.
`candidate_audit.parquet` ghi riêng từng query thiếu/không có relevant page và từng query
không đạt coverage; `preflight.json` chứa content hash của cả score và metric cache để
đối chiếu hai lần chạy cùng manifest.
Khi metric export có các cột `recall1_*`, `recall3_*`, `mrr10_*`, Budget report cũng giữ
và báo các secondary metric này tại budget được chọn.

## 4. Confirmation workflow

Tạo sample ViMDoc cố định, không nhìn retrieval outcomes:

```powershell
oracle-study sample-vimdoc --queries data\vimdoc_queries.parquet `
  --output runs\confirmation\vimdoc_2000.parquet -n 2000
```

Query table cần `query_id`, `source` và `relevant_count` (khuyến nghị), hoặc `doc_ids`;
sampling được phân tầng theo `source × single/multi relevant page` với seed cố định.

Sau khi chạy lại score/cache/oracle cho hướng vượt Discovery, áp dụng gate cuối:

```powershell
oracle-study decide `
  --qpaf-discovery runs\discovery\qpaf\qpaf_summary.json `
  --qpaf-confirmation runs\confirmation\qpaf\qpaf_summary.json `
  --budget-discovery runs\discovery\budget\budget_summary.json `
  --budget-confirmation runs\confirmation\budget\budget_summary.json `
  --output-dir runs\decision
```

Không truyền summary của hướng không vượt Discovery. Khi thiếu Confirmation, kết luận
sẽ là `inconclusive_do_not_rewrite_proposal`, không tự động coi Discovery là kết quả cuối.

## 5. Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Các test kiểm tra metric tính tay, deterministic tie-break, candidate construction không
dùng relevance, QPAF oracle không thấp hơn QARF, Budget endpoints và sampling cố định.

Ngưỡng đăng ký trước nằm tại `configs/preregistered.yaml`. Quy trình export score chính
xác từ môi trường HEAVEN/GPU nằm tại `docs/04_data_protocol/heaven_export_contract.md`.


---

# Hồ sơ bàn giao từ repository nghiên cứu của nhóm

Phần dưới giữ nội dung README của repo nguồn tại commit `83a20c2`; các trạng thái là lịch sử bàn giao tại repo đó.

# QPAF — Query-Page Adaptive Fusion for Visual Document Retrieval

Repository nghiên cứu của **Group 01**, dùng để bàn giao công việc, lưu code
và kiểm chứng bằng chứng nghiên cứu. QPAF là phương pháp chính; QARF là đối
chứng với cùng dữ liệu, feature và cấu hình chung theo protocol.

**Trạng thái kiểm tra ngày 26/09/2026:** M1.1 đã được chấp nhận ở phạm vi
báo cáo khả thi Oracle; M1.2 đã hoàn thành implementation và kiểm chứng phần
mềm cục bộ. Chưa có bằng chứng tái lập Oracle trên corpus thật hoặc thành
viên khác chạy lại M1.2 để nghiệm thu độc lập. **Chưa đóng toàn bộ M1/G1.**

Đợt code và tài liệu này được bàn giao trên nhánh **`feature/m1-1-m1-2-handoff`**,
đích tích hợp là `develop`. Xem [bảng đối chiếu tiêu chí và kết quả kiểm tra](docs/06_handover/m1.1-m1.2-status.md).
Thanh phụ trách Oracle; Phát phụ trách method core; Khương tiếp nhận code,
config và bằng chứng vào inventory.

## Đọc trước khi bắt đầu

1. [Trạng thái và đầu vào bàn giao M1](docs/06_handover/m1-restart-handoff.md): phần đã
   có, phần còn thiếu, người phụ trách và các quyết định cần chốt.
2. [Đề xuất nghiên cứu](docs/GUILDLINE_OVERVIEWS_PROPOSAL/DE_XUAT_NGHIEN_CUU_QPAF.md) và
   [tóm tắt định hướng](docs/01_overview/Tom_tat_dinh_huong_QPAF.md): phương pháp,
   giả thuyết và phạm vi dataset.
3. [Báo cáo Oracle đã nhận](results/m1.1/README.md): số liệu được cung cấp,
   file Word gốc và giới hạn kiểm chứng hiện tại.
4. [Milestone gốc](docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx), sheet
   `Milestones`: phân công và deliverable. Các chữ `Done` trong snapshot
   cũ **không phải trạng thái đã được xác minh ở checkout này**.
5. [Quy trình Gitflow và PR](CONTRIBUTING.md).

[TIMELINE_fixed.md](docs/GUILDLINE_OVERVIEWS_PROPOSAL/TIMELINE_fixed.md) là lịch tham chiếu cũ cho M1.4–M1.10.
Lịch đó chưa phân công lại việc thực hiện M1.1/M1.2. Không dùng ngày kế
hoạch để thay cho ngày chạy thực tế. Tài liệu Word
[Nghiên Cứu Kỹ Thuật QPAF](docs/GUILDLINE_OVERVIEWS_PROPOSAL/Nghi%C3%AAn%20C%E1%BB%A9u%20K%E1%BB%B9%20Thu%E1%BA%ADt%20QPAF.docx) được giữ
để truy nguồn; khi khác phạm vi dataset hoặc diễn giải kết quả, đối chiếu
với hai tài liệu định hướng và protocol được nhóm chốt.

## Phân công và trạng thái hiện tại

| Người | Nhiệm vụ trực tiếp | Trạng thái bằng chứng trong repo |
| --- | --- | --- |
| **Thanh — Trần Huỳnh Xuân Thanh** | **M1.1:** khảo sát Oracle W7/W66; sau đó M1.7 registry và QA | Người phụ trách chấp nhận báo cáo Oracle để chốt phạm vi khả thi M1.1; tái lập số liệu gốc chưa xác minh |
| **Phát — Bùi Trần Tấn Phát** | **M1.2:** xây dựng/kiểm chứng method core QARF/QPAF; M1.5 protocol | Đã triển khai schema 13 features, gate, fusion, loss và test gradient; xem báo cáo local tại `results/m1.2/` |
| **Khương — Trần Đình Khương** | M1.3 gói audit corpus; M1.4 inventory; M1.6 collision audit; M1.8 OCR/artifact plan | Có công cụ audit và snapshot chuẩn bị; chưa có corpus thật, collision audit chưa chạy, OCR còn draft |

M1.1 đã có số liệu được báo cáo, nên Thanh bắt đầu bằng việc tìm và đối
chiếu artifact của các run đó. Nếu phải chạy lại, tạo run mới và giữ báo
cáo cũ làm nguồn tham chiếu. M1.2 đã có đặc tả và kiểm chứng bằng dữ liệu tổng
hợp; bước tiếp theo là thành viên khác chạy lại và review phần lõi đã bàn giao.

**Pipeline M1.1 mới:** đã có code và config chạy ViDoSeek trên Modal; xem
[hướng dẫn chạy và lấy bằng chứng](docs/05_oracle_experiments/modal_oracle/m1.1-modal-oracle.md). Đây là bản dựng
mới sau thử nghiệm khả thi, chưa phải artifact gốc hoặc run GPU đã được xác minh.
Theo quyết định của người phụ trách, M1.1 được chấp nhận ở phạm vi báo cáo tính
khả thi Oracle. Tái lập trên dữ liệu thật và kiểm chứng độc lập là công việc
đánh giá tiếp theo, không được suy ra từ việc chấp nhận báo cáo.

**Lõi M1.2 mới:** xem [đặc tả và lệnh kiểm chứng](docs/03_method/m1.2-method-core.md) cùng
[bằng chứng phần mềm](results/m1.2/README.md). QARF/QPAF dùng chung feature và
ngân sách tham số; khác mức điều kiện hóa query/page. Chưa có kết quả learned
fusion trên corpus thật.

## Phạm vi dữ liệu theo đề xuất hiện tại

| Dataset | Vai trò | Đơn vị qrels/đánh giá |
| --- | --- | --- |
| ViDoSeek | Discovery, bổ trợ retriever và Oracle | Trang |
| ViMDoc | Confirmation theo protocol HEAVEN; QPAF chấm điểm trang rồi lấy max theo tài liệu | Tài liệu; cần mapping trang → tài liệu |
| ViDoRe V3 | Đánh giá ngoài miền, giữ bộ đánh giá niêm phong | Trang |

Qrels là nhãn liên quan giữa câu hỏi và trang/tài liệu. Không dùng qrels để
tạo candidate pool, chuẩn hóa điểm, phân cụm hoặc tạo feature cho learned
model. Revision, split, phạm vi query và cách nhóm các bản dịch phải được
ghi lại trước khi chạy theo protocol.

MMDocIR, ViOCRVQA và ReceiptVQA nằm ngoài phạm vi thực nghiệm hiện tại.
Tên dataset trong đề xuất không xác nhận đã có dữ liệu trong repo. Với
M1.3, Khương và Phát vẫn cần xác định chính xác corpus/revision của gói audit.

## Lấy repo và kiểm tra phần mềm đang có

Nhánh tích hợp của repo là **develop**; đợt M1.1/M1.2 này dùng nhánh bên dưới.
Nếu clone báo không có
quyền, cần được chủ repo cấp quyền bằng tài khoản GitHub của mình.

```sh
git clone --branch feature/m1-1-m1-2-handoff https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git
cd qpaf-visual-document-retrieval
python -m venv .venv
# Windows PowerShell:
.venv/Scripts/Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements/m12-cpu.txt
python -m pip install -e ".[verification,method]"
python -m unittest discover -s tests -v
python scripts/verify_m12.py --config configs/m1.2/core.toml --output results/m1.2/member-check-001
```

Để kiểm đủ cả hai phần, tạo môi trường trên bằng **Python 3.11**. Output
`member-check-001` phải chưa tồn tại; đổi ID cho mỗi lần chạy. Lần kiểm tra
26/09/2026: **69 test, 68 đạt, 1 skip quyền symlink Windows; cả 25 test M1.2 đạt**.

Công cụ audit dùng Python **>=3.11** và thư viện chuẩn. Test Oracle mới cần
NumPy: cài bằng `python -m pip install -e ".[oracle]"` trước khi chạy bộ test.
Để chạy cả method core, cài thêm PyTorch CPU theo `requirements/m12-cpu.txt`
(Python 3.11). Test cần Torch sẽ báo skip nếu chưa cài; `scripts/verify_m12.py`
yêu cầu toàn bộ kiểm tra lõi đạt và không skip.
Khi bổ sung dependency cho nghiên cứu, khai báo phiên bản và hướng dẫn cài
trong PR; không suy ra môi trường nghiên cứu đã được chuẩn bị từ việc test
audit chạy thành công.

## Thanh — M1.1: Oracle W7/W66

**Mục tiêu:** xác minh kết quả Oracle ở mức từng query, thống kê mức tăng
QPAF so với QARF và giới hạn kết luận. Kết quả Oracle là headroom sử dụng
nhãn; không thay thế kết quả learned QPAF.

**Phạm vi được chấp nhận:** M1.1 đã được người phụ trách chốt dựa trên báo cáo
Oracle. Các bước đối chiếu và tiêu chí tái lập bên dưới được giữ làm checklist
cho công việc đánh giá tiếp theo; chưa có bằng chứng chúng đã hoàn thành.

### Bước 1 — Nhận và kiểm kê đầu vào

Đọc [báo cáo Oracle](results/m1.1/README.md), sau đó tìm hoặc yêu cầu người
đã chạy cung cấp:

- Dataset/revision ViDoSeek, query và qrels; danh sách đúng **24 query**
  của Exploratory-24, ID trang và ánh xạ tới corpus.
- Score cache BM25, dense-text, visual; candidate pool dùng chung và cách
  xử lý điểm thiếu/chuẩn hóa.
- Định nghĩa chính xác các tập trọng số W7 và W66 của run, code/commit,
  config, lệnh chạy, môi trường, seed và log.
- Output từng query của Global, QARF, QPAF; cấu hình bootstrap và dữ liệu
  đầu vào để tính lại confidence interval.

Ghi rõ vị trí và người giữ cho phần chưa nhận được. File Word chỉ cung
cấp bảng tổng hợp; không tạo dữ liệu từng query bằng cách suy ngược từ
các số trung bình trong báo cáo.

### Bước 2 — Đối chiếu hoặc chạy lại có truy nguồn

1. Cố định query IDs, qrels, candidate pool, score tables, normalization
   và weight sets; ghi version/hash của các đầu vào.
2. Kiểm metric nDCG@10 bằng một trường hợp nhỏ có thể tính tay.
3. Tính bảng từng query cho W7 và W66; đối chiếu cùng một tập 24 query.
4. Tính mean delta QPAF–QARF, paired bootstrap CI95 và wins/ties/losses.
   Ghi đơn vị resampling, số lần lấy mẫu, seed và tolerance phân loại hòa;
   không suy đoán cấu hình run cũ nếu chưa nhận được.
5. Đối chiếu với báo cáo đã nhận. Nếu lệch, ghi nguyên nhân hoặc phần
   chưa giải thích; giữ cả kết quả cũ và mới.
6. Tách riêng full fixed-profile W7 (1.142 query) và pilot W71 (12 query).
   Không đưa số liệu của chúng vào kết luận cho Exploratory-24.

Nếu thiếu score cache hoặc code cũ và cần tạo mới, ghi rõ người thực hiện,
cấu hình retriever, phạm vi chạy và chính sách nhãn trước khi tạo kết quả.

### Bước 3 — Bàn giao

Dùng một thư mục run mới, ví dụ `results/m1.1/<run-id>/`. Các tên dưới
đây là quy ước cho đầu ra cần tạo, chưa phải các file kết quả đã có:

| File | Nội dung |
| --- | --- |
| `query_ids.csv` | Query IDs và phạm vi/split; liên kết tới query/qrels đúng phiên bản |
| `per_query_metrics.csv` | `query_id, weight_set, global_ndcg10, qarf_ndcg10, qpaf_ndcg10, delta_qpaf_qarf` |
| `summary.json` | Số query, mean, delta, CI95, W/T/L, bootstrap config và tie tolerance |
| `review.md` | Đối chiếu báo cáo cũ, khác biệt, giới hạn Oracle và phần chưa tái lập |
| `provenance.json` | Commit, config, command, environment, dataset/query/qrels/cache hashes và vị trí output |
| `hashes.csv` | Đường dẫn tương đối, kích thước và SHA-256 của các file bàn giao |

Payload lớn nằm ngoài Git; commit manifest và liên kết để nhóm truy cập.
Báo cáo tham chiếu trong `results/m1.1/reference/` được giữ nguyên.

### Điều kiện xác minh tái lập M1.1 — còn chờ

- Có bảng từng query và đúng query set để đối chiếu W7/W66.
- Mean, delta, CI95 và W/T/L tính lại được từ dữ liệu đã bàn giao;
  tổng W+T+L khớp số query của từng study.
- Trace được kết quả về code/config/data; thiếu gì phải ghi rõ.
- Kết luận chỉ nói về Oracle và phạm vi query thực sự đã đánh giá.
- Có review của thành viên khác; không tự ghi độc lập QA chỉ vì đã tạo file.

Nhánh gợi ý cho Thanh:

```sh
git fetch origin
git switch feature/m1-1-m1-2-handoff
git pull --ff-only origin feature/m1-1-m1-2-handoff
git switch -c feature/m1-1-oracle-review
```

## Phát — M1.2: method core QARF/QPAF

Đã có implementation mới trong `src/qpaf/m12/`, cấu hình chung
`configs/m1.2/core.toml`, test `tests/test_m12*.py` và lệnh `scripts/verify_m12.py`.
[Đặc tả v1](docs/03_method/m1.2-method-core.md) ghi rõ các quyết định mới về feature,
pooling và loss; [báo cáo kiểm chứng](results/m1.2/README.md) giữ log thực tế.

**Mục tiêu:** có phần lõi feature → gate → trọng số → fusion score → loss
và bằng chứng gradient hoạt động đúng. M1.2 kiểm lõi phương pháp; pipeline
trainer/evaluator đầy đủ là công việc riêng ở M2.4.

### Bước 1 — Review đặc tả đã có

Đọc `docs/03_method/m1.2-method-core.md` và đối chiếu:

- Đầu vào/đầu ra, shape, kiểu dữ liệu và cách nhóm query/page.
- **Danh sách 13 features theo yêu cầu milestone**: tên, thứ tự, công thức,
  nguồn, normalization và xử lý thiếu/biên cho từng feature. Implementation
  hiện dùng `qpaf13_v1` trong đặc tả M1.2; đây là thiết kế mới từ các nhóm
  feature trong đề xuất, chưa phải kết quả feature selection trên dữ liệu thật.
- Gate QARF dùng trọng số chung cho các trang của cùng query; gate QPAF
  có thể tạo trọng số riêng cho từng cặp query–page.
- Softmax tạo ba trọng số không âm, tổng bằng 1; công thức fusion dùng
  ba score đã chuẩn hóa.
- Hàm loss, chính sách sử dụng nhãn, ví dụ dữ liệu kiểm thử và kỳ vọng
  gradient; ghi rõ cấu hình chung giữa QARF/QPAF.

Nếu có code cũ, ghi repo/commit và đánh giá theo đặc tả. Nếu xây mới, ghi
đây là implementation mới. Quyết định chưa chốt phải được thể hiện rõ
trong PR, không dùng trạng thái Done cũ làm bằng chứng.

### Bước 2 — Chạy lại kiểm thử method core đã triển khai

Đặt module trong `src/qpaf/`, test trong `tests/`, config nhỏ trong
`configs/`. Các kiểm tra cần bao phủ:

1. Feature có đúng 13 chiều/thứ tự, giá trị hợp lệ và xử lý dữ liệu biên.
   Feature dùng khi suy luận không đọc qrels hoặc oracle labels.
2. Trọng số gate có đúng shape, hữu hạn, không âm và tổng bằng 1.
3. QARF chia sẻ trọng số trong query; QPAF xử lý được tín hiệu khác nhau
   giữa các trang. Không ép QPAF luôn tạo trọng số khác nhau.
4. Fusion khớp phép tính tay trên score/weight đã biết; các phương pháp
   dùng cùng quy tắc normalization và missing-score.
5. Loss khớp trường hợp kiểm thử được định nghĩa; backward tạo gradient
   hữu hạn tới tham số gate trên một ví dụ có tín hiệu học. Retriever
   được giữ frozen và không nhận cập nhật.
6. Hai biến thể dùng cùng input/candidate/feature/shared config; ghi rõ
   phần khác nhau do granularity của gate.

Có thể dùng fixture tổng hợp để kiểm tính đúng của phần mềm. Ghi rõ đây
là unit test, không dùng chúng làm kết quả nghiên cứu trên corpus thật.

### Bước 3 — Bàn giao

| Thành phần | Nơi lưu / yêu cầu |
| --- | --- |
| Đặc tả method core | `docs/03_method/m1.2-method-core.md` |
| Code QARF/QPAF | `src/qpaf/`, có interface và hướng dẫn gọi rõ ràng |
| Test và fixture | `tests/`; chạy được từ fresh checkout |
| Config và dependency | `configs/`, khai báo phiên bản thư viện và lệnh cài cần thiết |
| Báo cáo kiểm chứng | `results/m1.2/<run-id>/verification/<attempt-id>/verification.md`: từng kiểm tra, lệnh, kết quả và lỗi còn lại |
| Provenance | Commit nguồn, config hash, command, environment, thời điểm thực tế và hashes của output |

Chạy bộ test của repo sau khi thêm test method core:

```sh
python -m unittest discover -s tests -v
```

Nếu cần thêm lệnh kiểm chứng, ghi rõ trong đặc tả và PR; không để người
review phải đoán script nào cần chạy.

### Điều kiện nghiệm thu M1.2

- [x] Code, đặc tả 13 features, gate/fusion/loss và các test thống nhất.
- [x] Các kiểm tra phần mềm có kết quả thực tế, gồm gradient.
- [ ] Một thành viên khác chạy được theo hướng dẫn từ checkout sạch và ghi review.
- Mọi giới hạn/chưa triển khai được ghi rõ; không tuyên bố learned QPAF
  vượt QARF chỉ từ việc unit tests pass.

Nhánh gợi ý cho Phát:

```sh
git fetch origin
git switch feature/m1-1-m1-2-handoff
git pull --ff-only origin feature/m1-1-m1-2-handoff
git switch -c feature/m1-2-method-core
```

## Phần Khương làm song song và nhận bàn giao

- **M1.3:** xác định corpus/gói audit, phạm vi kiểm chứng và hash. Không
  mặc định có gói cũ chỉ vì milestone ghi Done; giữ rõ giới hạn thực thi.
- **M1.4:** tiếp nhận code/config/artifact từ Thanh/Phát, kiểm kê vị trí,
  revision/hash và gap. Không cần chờ mọi task xong mới bàn giao inventory.
- **M1.6:** khi có corpus và policy tương ứng, chạy kiểm ID, alias,
  duplicate/collision, split leakage và qrels; gửi Thanh review.
- **M1.8:** chuẩn bị OCR checklist, failure policy và artifact namespace,
  đồng bộ naming với Thanh và protocol với Phát. Phạm vi đo calibration
  cần chốt vì milestone có task M2.3 riêng; full OCR thuộc M2.6.

Xem [checklist Khương](docs/06_handover/khuong-m1-checklist.md) và
[tổng quan phối hợp](docs/GUILDLINE_OVERVIEWS_PROPOSAL/overview.md).

## Cấu trúc và kiểm chứng snapshot

```text
src/qpaf/               Audit, pipeline Oracle M1.1 và method core QARF/QPAF M1.2
scripts/                Lệnh chạy từ checkout
tests/                  Test audit, Oracle, cache, pipeline và method core
configs/                Config nghiên cứu nhỏ có phiên bản
data/                   Hướng dẫn lấy dữ liệu; payload lớn ngoài Git
manifests/              IDs, split, hash và vị trí dữ liệu
results/m1.1/           Báo cáo Oracle tham chiếu; các run mới dùng ID riêng
results/m1.2/           Bằng chứng kiểm chứng lõi trên fixture tổng hợp
docs/                   Định hướng, đặc tả và hướng dẫn bàn giao
docs/GUILDLINE_OVERVIEWS_PROPOSAL/  Đề xuất, tổng quan, timeline, workbook và Word nguồn
evidence/M1_FINAL/      Bộ bàn giao theo timeline và snapshot ban đầu
evidence/revisions/     Các snapshot tiếp theo, không ghi đè bản cũ
```

Snapshot của đợt bàn giao:

```sh
python scripts/audit_repository.py --root . --verify evidence/revisions/m1.4-002-handoff/hash_manifest.csv
```

Sau khi thay đổi code/tài liệu hoặc nhận dữ liệu mới, dùng snapshot ID mới,
ví dụ nếu đường dẫn này chưa tồn tại:

```sh
python scripts/audit_repository.py --root . --output evidence/revisions/m1.4-003
python scripts/audit_repository.py --root . --verify evidence/revisions/m1.4-003/hash_manifest.csv
```

Hash manifest kiểm byte của phiên bản đã audit. Để kiểm snapshot lịch sử,
dùng checkout đúng commit trong `audit_metadata.json`; thay đổi có chủ ý
sau snapshot có thể làm lệnh verify trên checkout mới báo mismatch.
Giữ nguyên snapshot cũ. Exit code 0 khi tạo snapshot không phải M1/G1 PASS;
corpus ngoài root cần kiểm kê/hash riêng.

## Gửi thay đổi của mỗi thành viên

Commit trên nhánh của mình, push nhánh đó và mở PR vào **develop**:

```sh
git status
git add <cac-file-thuoc-task>
git commit -m "feat: implement task with verification evidence"
git push -u origin <ten-nhanh-cua-minh>
```

Thay các phần trong dấu `<...>` bằng file/nhánh thật; không chạy nguyên
placeholder. PR cần task/owner, file bàn giao, lệnh và kết quả kiểm tra,
commit/config/data liên quan cùng blocker. Một thành viên khác review
trước khi merge. Không commit corpus/checkpoint lớn hoặc thông tin đăng nhập.
