# Bộ công cụ Jev cho nhóm QPAF

Ba nhánh nghiên cứu dùng chung CLI Jev để chuẩn bị pool F9, chấm điểm, đánh giá theo query và xuất dữ liệu huấn luyện Kev. Demo offline đã chạy với Python 3.11. Số liệu demo chỉ kiểm tra luồng trên dữ liệu tổng hợp. Chấm điểm dữ liệu đầy đủ, đo chất lượng mô hình và chạy GPU vẫn đang chờ.

[Đặc tả](superpowers/spec.md) · [Kế hoạch](superpowers/plan.md) · [Quy trình và quyền thực thi](evidence/workflow.md) · [Báo cáo triển khai và kiểm chứng](evidence/sdd/task-3-report.md)

## Chạy thử từ clone sạch

Clone nhánh được giao ở thư mục mới. Dùng URL origin mà nhóm cấp quyền. Thay tên nhánh trong lệnh clone theo bảng.

| Thành viên | Nhánh | Script |
| --- | --- | --- |
| Tấn Phát | `research/jev-phat-data-infra` | `scripts/run_jev_phat.py` |
| Thanh | `research/jev-thanh-baselines` | `scripts/run_jev_thanh.py` |
| Khương | `research/jev-khuong-model` | `scripts/run_jev_khuong.py` |

~~~powershell
git clone --branch research/jev-phat-data-infra https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git qpaf-jev
Set-Location qpaf-jev
py -3.11 -I -S scripts/run_jev_phat.py
py -3.11 -I -S scripts/run_jev_thanh.py
py -3.11 -I -S scripts/run_jev_khuong.py
~~~

~~~bash
git clone --branch research/jev-phat-data-infra https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git qpaf-jev
cd qpaf-jev
python3.11 -I -S scripts/run_jev_phat.py
python3.11 -I -S scripts/run_jev_thanh.py
python3.11 -I -S scripts/run_jev_khuong.py
~~~

Python 3.11 trở lên là đủ. Trên Windows có thể dùng `python` nếu lệnh này trỏ đúng bản Python. Demo chỉ dùng thư viện chuẩn, không tải model và không dùng mạng. Mỗi lệnh in thư mục run mới dưới `evidence/runs/<owner>/synthetic-*`, được Git bỏ qua. Dùng `--out DIR` với thư mục chưa tồn tại để chỉ định vị trí.

| Demo | Artifact cần kiểm tra |
| --- | --- |
| Phát | `splits.json`, `prepared/pairs.json`, `prepared/manifest.json`, `prepared/base_scores.json`. Doctor xác minh số điểm, giá trị hữu hạn và SHA-256 của pairs. |
| Thanh | `baseline.json`, `evaluation.json`, `comparison.json` và CSV tương ứng. Baseline dùng điểm có sẵn, lexical dùng đếm từ trùng để thử pipeline. |
| Khương | `train.jsonl`, sidecar `train.jsonl.manifest.json`, `kev-plan.json`, `base-plan.json`. Hai plan dùng cùng bản xuất nhãn trang train và không sinh checkpoint. |

Các wrapper cũng nhận lệnh CLI chung kèm đối số, chẳng hạn `python scripts/run_jev_phat.py doctor --help`. Các bước dưới đây dùng `scripts/run_jev.py` để cùng một lệnh chạy được trên mọi nhánh.

## Phát — chuẩn bị dữ liệu có quyền truy cập

Đặt đầu vào và kết quả thật ngoài clone. Ví dụ bên dưới dùng `$priv` trỏ tới thư mục riêng và `$run` tới một thư mục dành cho một lần chạy. Tạo một thư mục mới cho mỗi dataset/cohort. Các lệnh sau phần thiết lập dùng được trong cả PowerShell và Bash với `python` trên PATH.

~~~powershell
$priv = 'D:/qpaf-private'
$run = "$priv/runs/validation-01"
New-Item -ItemType Directory -Force "$run" | Out-Null
~~~

~~~bash
priv="$HOME/qpaf-private"
run="$priv/runs/validation-01"
mkdir -p "$run"
~~~

Chuẩn bị các file sau theo nguồn được nhóm chia sẻ.

- **Cache F9 đã chốt** cần `f9_pairs.json` hoặc `test_pairs.json` và tùy chọn score cache cùng cặp byte. JSON chứa `dataset`, `top_k`, `queries`, `pages`, `pairs` và có thể có `base_scores`, `units`. `pairs` giữ thứ tự trang F9. `base_scores` là điểm đã cung cấp theo đúng thứ tự pairs. Cache chỉ có danh sách trang vẫn chấm reranker được, nhưng baseline và blend cần `base_scores` tường minh.
- **Nguồn thô ViDoSeek** cần `raw_scores.parquet`, `queries.json`, OCR và manifest split. **Nguồn thô ViMDoc** cần `candidate_scores.parquet`, `queries.jsonl`, OCR và manifest split. Parquet ViMDoc có `document_id` để gom nhiều trang theo tài liệu. OCR đọc mapping JSON `{"page_id":"text"}` hoặc JSONL từng dòng `{"page_id":"...","text":"..."}`. Ghi chuỗi rỗng cho trang đã xác nhận thiếu OCR. Mỗi query cần cả văn bản lẫn hàng ứng viên.
- **Manifest split** dùng `{"splits":{"qid":"train"},"groups":{"qid":"group-id"}}`. Mỗi query có một split và một group, một group chỉ thuộc một split. Có thể dùng `--query-ids FILE` với danh sách ID mỗi dòng để giới hạn một pilot trong split đã chọn.
- **Nhãn development** dùng file riêng có quyền truy cập. Đánh giá flat cần `{"qid":{"page-or-document-id":1}}`, gồm cả positive ngoài candidate pool. ViMDoc native dùng `dev_qrels.json` dạng `{"train":{"qid":["document-id"]},"validation":{"qid2":["document-id"]}}`. Huấn luyện cần nhãn **trang** ViDoSeek và chỉ split train. Tách file nhãn khỏi dữ liệu chấm điểm và lưu ngoài Git.

Mỗi lệnh `prepare` cần một thư mục `--out` chưa tồn tại. Khi chạy lại với score cache hoặc cohort khác, hãy chọn tên thư mục mới. Pairs đã ghi `partition` chỉ cho phép lấy tập con trong chính partition đó. Với dữ liệu thô, cần đủ dung lượng tạm cho bản sao của các file đầu vào để SHA-256 khớp với dữ liệu đã đọc.

Nhập pairs F9 nguyên byte rồi kiểm tra baseline cache nếu pairs có `base_scores`.

~~~sh
python scripts/run_jev.py doctor --f9-pairs "$priv/f9_pairs.json"
python scripts/run_jev.py prepare --f9-pairs "$priv/f9_pairs.json" --out "$run/prepared"
python scripts/run_jev.py doctor --pairs "$run/prepared/pairs.json" --scores "$run/prepared/base_scores.json"
~~~

Nếu đã có cache theo định dạng Jev, dùng `--import-scores "$priv/reranker-scores.json"` cùng lệnh `prepare` để kiểm tra và xuất lại `prepared/scores.json`. Khi thêm `--splits "$priv/splits.json" --partition validation`, CLI giữ thứ tự tương đối, trích đúng các phần tử score và ghi hash theo JSON đã cắt. Cache cũ vẫn gắn với file pairs cũ. Để nhập cả thư mục cache, dùng `--f9-cache DIR` khi thư mục chỉ có một trong hai tên pairs nhận diện được.

Khi chuẩn bị từ dữ liệu thô, cài `pyarrow` vào venv dữ liệu riêng nếu đọc Parquet. Với CSV, JSON hoặc JSONL dùng Python thư viện chuẩn và `--raw-scores FILE --queries FILE`. Hàng thô cần `query_id`, `page_id`, cộng `base_score` hoặc ba kênh `bm25`, `dense`, `visual` và trọng số công khai. Native ViDoSeek dùng tên cột kênh với hậu tố `_score`.

~~~powershell
py -3.13 -m venv .venv-jev-data
.\.venv-jev-data\Scripts\python.exe -m pip install pyarrow
. .\.venv-jev-data\Scripts\Activate.ps1
~~~

~~~bash
python3.13 -m venv .venv-jev-data
. .venv-jev-data/bin/activate
python -m pip install pyarrow
~~~

Ví dụ native ViMDoc với trọng số minh họa đều nhau. Dùng đúng trọng số đã ghi nhận của nghiên cứu khi cần tái lập một pool cụ thể.

~~~sh
python scripts/run_jev.py doctor --dataset vimdoc --f9-bundle "$priv/vimdoc" --page-text "$priv/vimdoc-ocr.jsonl" --query-ids "$priv/validation_ids.txt"
python scripts/run_jev.py prepare --dataset vimdoc --f9-bundle "$priv/vimdoc" --page-text "$priv/vimdoc-ocr.jsonl" --splits "$priv/vimdoc-splits.json" --partition validation --weights 0.3333333333333333 0.3333333333333333 0.3333333333333333 --top-k 20 --out "$run/vimdoc"
~~~

Với ViDoSeek native, đổi sang `--dataset vidoseek`, folder bundle ViDoSeek và OCR/split đúng dataset. Dùng `--splits` cùng `--partition` cho run development để chỉ chọn cohort được giao. `doctor` báo file thiếu. Dữ liệu ViMDoc, OCR đúng phiên bản, split/group của pilot và cache tư nhân cần lấy từ người phụ trách trước khi chạy.

## Môi trường GPU tùy chọn

Chọn một trong hai bộ requirements cho từng venv Python **3.13**. BGE/Qwen dùng `requirements/jev-baselines.txt`, Kev inference/train dùng `requirements/jev-kev.txt`. Cần Git để cài nguồn Kev, driver NVIDIA tương thích và GPU đủ VRAM. Lần nạp model đầu tiên cần truy cập các revision đã pin trên Hugging Face hoặc `--checkpoint` trỏ tới model local phù hợp. Ví dụ CUDA 12.8 dưới đây tạo venv baseline. Để tạo venv Kev, mở shell riêng và thay cả đường dẫn `.venv-jev-baselines` lẫn tên file requirements thành `.venv-jev-kev` và `requirements/jev-kev.txt`. [Wheel PyTorch 2.8.0 chính thức](https://pytorch.org/get-started/previous-versions/#v280)

~~~powershell
py -3.13 -m venv .venv-jev-baselines
. .\.venv-jev-baselines\Scripts\Activate.ps1
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements/jev-baselines.txt
python -c "import torch; print(torch.__version__); assert torch.cuda.is_available()"
~~~

~~~bash
python3.13 -m venv .venv-jev-baselines
. .venv-jev-baselines/bin/activate
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements/jev-baselines.txt
python -c "import torch; print(torch.__version__); assert torch.cuda.is_available()"
~~~

Nếu PowerShell chặn `Activate.ps1`, gọi trực tiếp `.\.venv-jev-baselines\Scripts\python.exe` hoặc Python tương ứng của venv Kev. Các package và trọng số được pin trong [requirements baseline](../../../../requirements/jev-baselines.txt), [requirements Kev](../../../../requirements/jev-kev.txt) và [cấu hình models](../../../../configs/jev/models.json). Backbone là `Qwen/Qwen3.5-4B-Base@1001bb4d826a52d1f399e183466143f4da7b741b`, checkpoint gốc là `jaredpalmer/kev-4b@6cfce5c2fa4b4bd64026336ab649c5ca78857d52`, nguồn trainer là `jaredpalmer/kev@5e22da2be8ecb2f38790d81d87bb55b0be61a6e2`.

## Thanh — chấm điểm và so sánh có đối chứng

Scores được lưu theo thứ tự pairs, đúng số phần tử, dùng giá trị hữu hạn và SHA-256 của bytes JSON. Chạy lại cùng lệnh model để dùng chunk đã xác minh. Giữ nguyên pairs, checkpoint, cấu hình và môi trường khi resume. Khi đổi một trong các yếu tố đó, dùng đường dẫn `--chunks` và output mới.

~~~sh
python scripts/run_jev.py score --backend baseline --pairs "$run/prepared/pairs.json" --out "$run/base.json"
python scripts/run_jev.py doctor --pairs "$run/prepared/pairs.json" --scores "$run/base.json"
python scripts/run_jev.py score --backend bge --pairs "$run/prepared/pairs.json" --out "$run/bge.json" --chunks "$run/bge-chunks" --device cuda --precision fp16 --input-cap 1024 --batch-size 4
python scripts/run_jev.py score --backend qwen --pairs "$run/prepared/pairs.json" --out "$run/qwen.json" --chunks "$run/qwen-chunks" --device cuda --precision bf16 --input-cap 1024 --batch-size 4
python scripts/run_jev.py doctor --pairs "$run/prepared/pairs.json" --scores "$run/bge.json"
~~~

Dùng lại cache đã kiểm tra bằng `--scores` với đúng pairs. Chạy pure rerank và blend thành các báo cáo riêng. Chọn `--lambda` từ quy trình development đã thống nhất. Báo cáo dưới đây dùng cùng qrels, cohort và k.

~~~sh
python scripts/run_jev.py evaluate --pairs "$run/prepared/pairs.json" --baseline --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/baseline-eval.json"
python scripts/run_jev.py evaluate --pairs "$run/prepared/pairs.json" --scores "$run/bge.json" --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/bge-pure.json" --csv "$run/bge-pure.csv"
python scripts/run_jev.py evaluate --pairs "$run/prepared/pairs.json" --scores "$run/bge.json" --lambda 0.5 --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/bge-blend.json"
python scripts/run_jev.py compare --left "$run/baseline-eval.json" --right "$run/bge-pure.json" --groups "$priv/splits.json" --seed 20260820 --resamples 10000 --out "$run/paired.json" --csv "$run/paired.csv"
~~~

Dùng `--baseline` cho báo cáo baseline đối chứng để JSON ghi `score_mode: baseline`. Lệnh `doctor` kiểm tra cache `base.json` với đúng file pairs. Khi tái sử dụng cache bằng `--scores "$run/base.json"`, JSON ghi `score_mode: pure`. Với ViMDoc native, sử dụng `--qrels-format vimdoc-dev`. CLI kiểm tra hai role development, phát hiện query trùng giữa các role và tài liệu trùng trong cùng query, giữ positive ngoài pool và lấy điểm trang cao nhất cho mỗi tài liệu. Lệnh dưới đây đọc map `units` nhúng từ Parquet. Nếu dùng pairs import chưa có map, thêm `--units "$priv/vimdoc-page-to-doc.json"` (JSON `{"page-id":"document-id"}`) ở mọi lần đánh giá. Khi cả hai báo cáo ghi hash sidecar, compare yêu cầu hash giống nhau.

~~~sh
python scripts/run_jev.py evaluate --pairs "$run/vimdoc/pairs.json" --baseline --qrels "$priv/vimdoc/dev_qrels.json" --qrels-format vimdoc-dev --k 10 --out "$run/vimdoc-baseline.json"
~~~

Các metric áp dụng trên pool đã cấp. Group bootstrap và delta phải dùng cùng cohort; báo cáo JSON/CSV lưu `ranking_scope`, `label_unit` và `synthetic`.

## Khương — xuất nhãn trang và lập hai kế hoạch train

Tạo pairs train từ bundle ViDoSeek. Trọng số dưới đây minh họa cho cú pháp. Thay bằng protocol train đã thống nhất. Export chỉ lấy nhãn trang đã khai báo cho các query train. Chỉ dùng `--unjudged-as-negative` khi protocol đã chấp nhận giả định này.

~~~sh
python scripts/run_jev.py prepare --dataset vidoseek --f9-bundle "$priv/vidoseek" --page-text "$priv/vidoseek-ocr.jsonl" --splits "$priv/vidoseek-splits.json" --partition train --weights 0.3333333333333333 0.3333333333333333 0.3333333333333333 --top-k 20 --out "$run/train-pairs"
python scripts/run_jev.py export-train --pairs "$run/train-pairs/pairs.json" --splits "$priv/vidoseek-splits.json" --qrels "$priv/train-page-qrels.json" --out "$run/train.jsonl"
python scripts/run_jev.py train --init kev --data "$run/train.jsonl" --out "$run/kev-init" --max-steps 1
python scripts/run_jev.py train --init base --data "$run/train.jsonl" --out "$run/base-init" --max-steps 1
~~~

Đọc hai plan trước. Dùng venv Kev cho hai lệnh thực thi. Export JSONL đi cùng `train.jsonl.manifest.json`. Mỗi `--out` của trainer phải mới. Seed, data, LoRA, kiến trúc head, giá trị `max-state`, batch, accumulation và budget phải giống nhau giữa hai run.

~~~sh
python scripts/run_jev.py train --init kev --data "$run/train.jsonl" --out "$run/kev-init" --max-steps 1 --execute
python scripts/run_jev.py train --init base --data "$run/train.jsonl" --out "$run/base-init" --max-steps 1 --execute
python scripts/run_jev.py score --backend kev --pairs "$run/prepared/pairs.json" --out "$run/kev-original-scores.json" --device cuda --precision fp32 --input-cap 1024
python scripts/run_jev.py score --backend kev --checkpoint "$run/kev-init" --pairs "$run/prepared/pairs.json" --out "$run/kev-init-scores.json" --device cuda --precision fp32 --input-cap 1024
python scripts/run_jev.py score --backend kev --checkpoint "$run/base-init" --pairs "$run/prepared/pairs.json" --out "$run/base-init-scores.json" --device cuda --precision fp32 --input-cap 1024
python scripts/run_jev.py evaluate --scores "$run/kev-init-scores.json" --pairs "$run/prepared/pairs.json" --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/kev-init-eval.json"
python scripts/run_jev.py evaluate --scores "$run/base-init-scores.json" --pairs "$run/prepared/pairs.json" --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/base-init-eval.json"
python scripts/run_jev.py compare --left "$run/base-init-eval.json" --right "$run/kev-init-eval.json" --groups "$priv/vidoseek-splits.json" --out "$run/train-controls.json"
~~~

Dùng cùng pool validation cho checkpoint gốc, hai checkpoint huấn luyện và các baseline của Thanh. Đánh giá/so sánh trên cùng đơn vị nhãn và cùng qrels. `jev-run.json` lưu hash checkpoint, số record admitted, số lượt đọc thật và số bước optimizer. Smoke tích hợp trước đó dùng `--max-steps 1` với model nhỏ trên CPU. Trainer upstream tại pin trên có lỗi chia cho 0 trong `OneCycleLR` khi lịch có đúng **10 bước optimizer hiệu dụng**. Trước khi tăng budget, kiểm tra số bước hiệu dụng sau lọc context và điều chỉnh batch, accumulation, epoch hoặc step budget giống nhau cho hai nhánh nếu gặp đúng ngưỡng. Full model và budget khác vẫn cần kiểm chứng. [Trainer đã pin](https://github.com/jaredpalmer/kev/blob/5e22da2be8ecb2f38790d81d87bb55b0be61a6e2/kev/train.py#L588)

## Modal tùy chọn — chạy thực khi đã có quyền dùng GPU và upload dữ liệu

Dùng venv Python 3.13 riêng cho máy gửi job, cài `modal==1.5.5` và cấu hình profile của bản thân. Worker tự cài một trong hai bộ requirements theo model. Lệnh preview thiếu `--execute` chạy offline, in JSON kế hoạch. `--execute` trước `score` hoặc `train` gửi job thật. Mọi đường dẫn bên trong lệnh worker dùng đường dẫn tương đối theo Volume và dấu `/`.

~~~powershell
py -3.13 -m venv .venv-jev-modal
. .\.venv-jev-modal\Scripts\Activate.ps1
python -m pip install modal==1.5.5
~~~

~~~bash
python3.13 -m venv .venv-jev-modal
. .venv-jev-modal/bin/activate
python -m pip install modal==1.5.5
~~~

Dùng Volume riêng cho các job đang chạy đồng thời. Ví dụ Thanh dùng `jev-thanh`, Khương dùng `jev-khuong` và chạy tuần tự hai lần train của mình. Nếu cần hai job train cùng lúc, dùng hai Volume và chép input sang cả hai. Mỗi worker ghi cả chunk/output lẫn cache `HF_HOME` trên Volume. Modal dùng last-write-wins khi ghi đè cùng file từ nhiều container, nên tách thư mục `--chunks` trong một Volume chưa đủ. [Modal Volumes](https://modal.com/docs/guide/volumes)

~~~sh
modal setup
python scripts/modal_jev_rerank.py --volume jev-thanh score --backend bge --pairs inputs/pairs.json --out runs/validation-01/bge.json
modal volume create jev-thanh
modal volume put jev-thanh "$run/prepared/pairs.json" inputs/pairs.json
python scripts/modal_jev_rerank.py --volume jev-thanh --gpu A100-80GB --execute score --backend bge --pairs inputs/pairs.json --out runs/validation-01/bge.json --chunks runs/validation-01/bge-chunks
modal volume get jev-thanh runs/validation-01/bge.json "$run/modal-bge.json"

python scripts/modal_jev_rerank.py --volume jev-khuong train --init kev --data inputs/train.jsonl --out runs/pilot-01/kev-init --max-steps 1
modal volume create jev-khuong
modal volume put jev-khuong "$run/train.jsonl" inputs/train.jsonl
modal volume put jev-khuong "$run/train.jsonl.manifest.json" inputs/train.jsonl.manifest.json
python scripts/modal_jev_rerank.py --volume jev-khuong --gpu A100-80GB --execute train --init kev --data inputs/train.jsonl --out runs/pilot-01/kev-init --max-steps 1
python scripts/modal_jev_rerank.py --volume jev-khuong --gpu A100-80GB --execute train --init base --data inputs/train.jsonl --out runs/pilot-01/base-init --max-steps 1
modal volume get jev-khuong runs/pilot-01 "$run/modal-training"
~~~

Để chấm checkpoint trên Volume Khương, stage thêm `inputs/eval-pairs.json` từ validation rồi gọi worker `score --backend kev --checkpoint runs/pilot-01/kev-init --pairs inputs/eval-pairs.json --out runs/pilot-01/kev-init-scores.json`. Khi tải scores về, dùng local pairs có cùng bytes để chạy `doctor` và `evaluate`. [CLI Volume](https://modal.com/docs/reference/cli/volume)

## Kiểm chứng

Chạy `python -I -S -m unittest discover -s tests -p "test_jev_*.py"`. Bản sau review chạy 76 test trên Python3.11 cô lập:71 qua/5 bỏ qua có lý do; cả3 test Parquet qua riêng với PyArrow. [RED/GREEN và suite](evidence/final-fix-green.log) · [Parquet](evidence/final-fix-parquet.log) · [ba demo thực tế](evidence/final-fix-demos.log). Nhánh publication trên WSL/Python3.14.4 chạy12 test:11 qua/1 bỏ qua vì thiếu PyArrow. [WSL](evidence/final-fix-wsl.json)

[Review toàn bộ](evidence/sdd/final-review.md) tìm thấy sáu lỗi ranh giới dữ liệu/artifact; [re-review đợt sửa](evidence/sdd/final-fix-review.md) xác nhận cả sáu đã xử lý và không còn Critical/Important trong đợt sửa. Phạm vi, các lưu ý nhỏ còn lại và nguồn hash có trong [báo cáo sửa](evidence/sdd/final-fix-report.md), [workflow](evidence/workflow.md), [kiểm chứng cấu trúc/inventory](evidence/validation.json), [SHA-256](evidence/hashes.json) và [các quyết định/đánh đổi](evidence/rulings.md).

Tích hợp CPU nhỏ trước đó đã xác nhận BGE/Qwen forward, trainer Kev một bước và checkpoint/head reload; Modal mới kiểm tra preview/SDK. [Báo cáo adapters/trainer](evidence/sdd/task-2-report.md). Dữ liệu tư nhân, model4B đầy đủ, GPU local/Modal và chất lượng reranker vẫn chờ chạy. Suite lịch sử toàn repo có14 failure/72 error/44 skip trên635 test; danh sách và giới hạn môi trường ở [Task1](evidence/sdd/task-1-report.md), không được mô tả là toàn repo đã xanh.
