# A005-R1: refined training cho QPAF-SA / QARF-SA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train lại QPAF-SA-v2 và QARF-SA-v2 với một cấu hình đã chốt trước (ε nhỏ, 40 epoch với cosine LR, trung bình trọng số epoch 20–40, ensemble 3 seed). Có ablation trên validation, và chạy confirmation **một lần** cho cấu hình đầy đủ, ghi rõ là post-hoc.

**Architecture:** Toàn bộ code mới nằm trong file mới. Các file A005 hiện có **không được sửa**, vì record Stage 2–6 ghim hash của chúng. Code dùng lại `AnchoredFusionGate(..., epsilon=...)`, `trainer.document_listwise_loss`, `trainer.validation_metric`, `stage2.split_inputs`, `stage4.validation_scores`, `stage4.per_query_ndcg`, `stage5.confirmation_inputs` và `qpaf.m25.statistics.paired_report`.

**Tech Stack:** Python (`.venv/Scripts/python.exe`), PyTorch CPU float64, 1 thread mỗi process, deterministic; `unittest`.

**Spec:** quyết định của người dùng ngày 2026-10-29 (bên dưới). Kết quả gốc: [`a005-result-report.md`](../../06_handover/a005-result-report.md).

## Cấu hình đã chốt (không đổi sau khi xem kết quả)

| Thành phần | Giá trị |
| --- | --- |
| Anchor `w̄` | `stage4_anchor_weights` trong `evidence/revisions/a005-s3-001/baselines.json` (`[0.1, 0.2, 0.7]`) |
| `epsilon` | `1e-6` (A005 dùng `1e-3`) |
| Epoch | 40 |
| LR | Adam, 0.01, cosine theo epoch: `lr_e = 0.01 · 0.5 · (1 + cos(π · (e−1)/40))` cho epoch e = 1..40 |
| Còn lại | Giữ như A005: weight decay 0, clip 5.0, batch 16, `QUERY_LENGTH_CAP` 64, 13 feature, loss listwise trên document với `τ` học được |
| Trung bình trọng số | Trung bình đều state_dict (mọi parameter, kể cả `log_tau`) sau mỗi epoch 20, 21, …, 40, tức 21 checkpoint. **Không chọn epoch theo validation** |
| Seed | `20260820`, `20260821`, `20260822` |
| Ensemble | Trung bình điểm fused page của 3 model đã trung bình trọng số, sau đó lấy max theo document như cũ |
| Granularity | `query` (QARF-SA-R1) và `page` (QPAF-SA-R1), áp **y hệt** nhau |

**Kết quả chính đã chốt trước:** ensemble QPAF-SA-R1 so với `train_fitted_static`, và ensemble QPAF-SA-R1 so với ensemble QARF-SA-R1, trên confirmation.

## Global Constraints

- `git pull` trước khi bắt đầu; nếu fail hoặc conflict thì dừng và báo. Nhánh `feature/a005-qpaf-sa`. Không push.
- Không sửa bất kỳ file nào đã có trong `src/qpaf/a005/`, `scripts/`, `tests/`. Chỉ thêm file mới.
- Commit theo dạng `feat(a005-r1): …` / `docs(a005-r1): …`, **không** có `Co-Authored-By` hay attribution AI. Không add `.claude/`, `AGENTS.md`, `MergeM*.md`.
- Mỗi run ghi create-once (từ chối nếu đã có `result.json`), cần tracked tree sạch, ghi `source_commit`.
- Cache: `C:/Users/HP/qpaf-cache/a005-s1-001/`. File confirmation sealed `confirmation_qrels.sealed.json` nằm cùng thư mục, **chỉ được đọc ở Task 4**.
- Nếu một bước đòi đổi cấu hình đã chốt thì dừng và báo. Không tự đổi.

---

### Task 1: Trainer và runner R1

**Files:**
- Create: `src/qpaf/a005/refine.py`, `scripts/train_a005_refine.py`
- Test: `tests/test_a005_refine.py`

**Interfaces:**
- `CONFIG`: dict chứa các giá trị trong bảng trên. `VARIANTS = ('full', 'eps1e3', 'constlr')`. `eps1e3` dùng `epsilon=1e-3`; `constlr` giữ LR 0.01 cố định. Mọi giá trị khác giống `full`.
- `cosine_lr(epoch: int) -> float`.
- `train_refined(anchor, granularity, seed, train_records, validation_records, *, query_length_cap, train_relevant_documents, validation_relevant_documents, variant='full', log=print) -> dict`. Trả về:
  - `averaged_model`: model đã trung bình trọng số epoch 20–40;
  - `best_epoch_model` và `best_epoch`: model và epoch tốt nhất trên validation trong 0–40, chỉ dùng cho ablation "chọn epoch";
  - `history`: list có `epoch`, `lr`, `train_loss`, `validation_ndcg_at_10`, `tau`.
  Vòng train viết theo `trainer.train`, dùng lại `document_listwise_loss`, `validation_metric` và `build_features`. Dùng `build_model` hoặc `AnchoredFusionGate(anchor, granularity, epsilon=...)` trong `torch.random.fork_rng` giống `trainer.build_model`.
- `run_dir(root, variant, granularity, seed) -> Path` = `evidence/revisions/a005-r1-001/runs/<variant>-<qarf|qpaf>-sa-r1-<seed>/`.
- `create_run(root, cache, variant, granularity, seed) -> dict`: lưu `averaged.pt` và `best_epoch.pt`, ghi `result.json` gồm `variant`, `granularity`, `seed`, `config`, `history`, `best_epoch`, nDCG validation của `averaged` và `best_epoch` kèm per-query, sha của checkpoint, `inputs_sha256`, `stage3_sha256`, `source_commit`. Tạo một lần; cần tree sạch.
- CLI: `scripts/train_a005_refine.py --cache DIR --variant full|eps1e3|constlr --granularity query|page --seed N`.

- [ ] **Step 1: Viết test trước** (dữ liệu tổng hợp nhỏ, theo fixture `tests/test_a005_trainer.py` / `tests/test_a005_stage4.py`):
  - `test_cosine_lr_endpoints`: `cosine_lr(1) == 0.01`; `cosine_lr(40)` > 0 và < 1e-4; dãy giảm dần.
  - `test_epoch0_equals_anchor_with_small_epsilon`: với `epsilon=1e-6`, trọng số ở epoch 0 lệch so với anchor không quá 1e-5.
  - `test_average_is_mean_of_epoch_states`: với 3 epoch và `average_from` nhỏ dùng cho test, tham số của `averaged_model` bằng trung bình các state đã lưu (sai số 1e-12). Cho phép override `epochs` và `average_from` qua kwargs chỉ dùng trong test.
  - `test_variants_differ_only_in_declared_field`: `CONFIG` của từng variant chỉ khác `full` ở `epsilon` hoặc `lr_schedule`.
  - `test_create_run_is_create_once` và `test_create_run_requires_clean_tree`.
- [ ] **Step 2: Chạy test, phải FAIL. Viết code. Chạy test, phải PASS.** Chạy kèm `tests.test_a005_trainer tests.test_a005_stage4` để chắc không hỏng gì.
- [ ] **Step 3: Commit.**

### Task 2: Chạy train

Mỗi run chạy 1 thread nên có thể chạy song song nhiều process. Chạy tối đa `min(4, số core − 1)` process cùng lúc, bằng `run_in_background`, và chờ thông báo, không poll bằng sleep. Mọi run phải xuất phát từ cùng một commit sạch. Commit tất cả `result.json` và `*.pt` (dùng `git add -f`, mỗi file vài KB) sau khi **toàn bộ** batch xong, không commit giữa chừng khi các process khác còn đang chạy.

- [ ] **Step 1: `full`**: 2 granularity × 3 seed, tổng 6 run.
- [ ] **Step 2: Ablation `eps1e3` và `constlr`**: 2 granularity, chỉ seed `20260820`, tổng 4 run.
- [ ] **Step 3: Commit** `feat(a005-r1): record the refined-training runs`.

### Task 3: Bảng validation

**Files:** Create `src/qpaf/a005/refine_eval.py`, `scripts/evaluate_a005_refine.py`, `tests/test_a005_refine_eval.py`.

**Interfaces:**
- `ensemble_scores(models, records) -> {query_id: [page scores]}`: trung bình điểm fused page của các model.
- `validation_table(root, cache) -> dict`, ghi create-once `evidence/revisions/a005-r1-001/validation.json`. Mỗi granularity có các dòng:
  1. A005 gốc (trung bình 3 seed, đọc từ `a005-s4-001/runs/*/result.json`);
  2. `full`, ensemble;
  3. `full`, trung bình 3 seed không ensemble;
  4. `full`, ensemble của các `best_epoch` model, tức "chọn epoch thay vì trung bình";
  5. `eps1e3` seed 20260820, `averaged`;
  6. `constlr` seed 20260820, `averaged`;
  7. `full` seed 20260820, `averaged`, để so trực tiếp với dòng 5 và 6.

  Kèm static 0.956878 và các delta so với static.
- [ ] Test: `test_ensemble_of_identical_models_equals_single`; `test_table_rows_cover_both_granularities`.
- [ ] Viết code, chạy, commit `validation.json`.

### Task 4: Confirmation một lần (chỉ cấu hình `full`)

**Files:** Thêm hàm vào `src/qpaf/a005/refine_eval.py`: `confirmation_record(root, cache, sealed_path) -> dict`, ghi create-once `evidence/revisions/a005-r1-001/confirmation.json`.

- Dùng `stage5.confirmation_inputs` (hàm này kiểm hash trước khi đọc). Chấm ensemble `full` của QPAF-SA-R1 và QARF-SA-R1, cùng 3 model averaged của từng loại. Baseline `train_fitted_static` lấy per-query từ `evidence/revisions/a005-s5-001/confirmation.json`; không chấm lại.
- Thống kê bằng `paired_report`. Với ensemble là một model duy nhất, truyền cùng một dict cho cả 3 seed key (giống cách Stage 6 làm với baseline). Các so sánh:
  - (a) ensemble QPAF-R1 so với static;
  - (b) ensemble QPAF-R1 so với ensemble QARF-R1;
  - (c) ensemble QPAF-R1 so với QPAF-SA-v2 gốc. Gốc lấy trung bình 3 seed per-query từ Stage 5; truyền theo seed thật cho phía gốc và lặp dict ensemble cho phía R1.
- Ghi `post_hoc: true` và `note: "configuration fixed before evaluation; confirmation split already opened once by A005 Stage 5"`.
- [ ] Test: hash sealed sai thì từ chối (dùng lại fixture Stage 5); create-once.
- [ ] Chạy **một lần** trên dữ liệu thật. Lỗi xảy ra trước khi ghi file thì chỉ được sửa vấn đề môi trường hoặc đường dẫn. Đã ghi file thì không chạy lại. Commit.

### Task 5: Báo cáo

- [ ] Viết `evidence/revisions/a005-r1-001/README.md` (ngắn, theo mẫu `a005-s4-001/README.md`).
- [ ] Thêm phần **"6. A005-R1: training tinh chỉnh (post-hoc)"** vào cuối `docs/06_handover/a005-result-report.md`, bằng tiếng Việt, gồm:
  - cấu hình;
  - bảng validation có ablation;
  - bảng confirmation và các so sánh (a), (b), (c);
  - một đoạn giải thích từng thành phần giúp bao nhiêu;
  - câu nói rõ con số này là post-hoc, còn kết quả sạch vẫn là A005.

  Không sửa các phần 1–5 đã có. Thêm một dòng R1 vào `docs/06_handover/a005-exploration-log.md`. Commit.
