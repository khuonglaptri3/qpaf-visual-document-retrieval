# M1.5 Experiment Protocol — Final Freeze

> **Trạng thái:** `FROZEN_M1_5_V1_EXECUTION_CLOSED`  
> **Protocol ID:** `QPAF-M1.5-v1`  
> **Owner:** Tấn Phát — Research Lead / Protocol & Gate Owner  
> **Ngày lập:** 25/09/2026  
> **Frozen at:** `2026-09-25T20:43:27.4530745+07:00`  
> **Cho phép execution:** **Không**

File này nằm trong cấu trúc bàn giao `M1_FINAL` lấy từ `main` và tuân theo
`TIMELINE_fixed.md`. M1.5 đã freeze **protocol semantics** ở version nêu trên sau khi
đối chiếu trực tiếp với repository, configs, dataset identity receipts và M1.7 Draft
hiện có. Freeze này không thay thế deliverable M1.4, không xác nhận data readiness,
không phải independent QA/G1 sign-off, và không cho phép OCR, extraction, oracle,
optimizer step, training, Modal/GPU hay sealed external evaluation.

## 1. Mục tiêu và câu hỏi nghiên cứu

Mục tiêu chính là kiểm tra liệu **learned Query-Page-Adaptive Fusion (QPAF)** có cải
thiện ổn định so với **matched learned Query-Adaptive Retrieval Fusion (QARF)** và
strongest deployable baseline khi ba retriever BM25, BGE-M3 và ColQwen2.5 được giữ
frozen hay không.

| ID | Câu hỏi | Evidence bắt buộc |
|---|---|---|
| RQ1 | Learned QPAF có vượt matched learned QARF không? | Cùng candidate rows/order, split, features, loss, optimizer, budget, seeds và evaluation; paired document nDCG@10 |
| RQ2 | Learned QPAF có vượt strongest deployable non-oracle baseline không? | Baseline roster cố định; fitting/selection chỉ dùng development data |
| RQ3 | Gain có ổn định qua seed và không tập trung vào nhóm query rất nhỏ không? | Ba seed, per-query deltas, CI95, W/T/L và gain concentration |
| RQ4 | Page-level adaptation có cần thiết so với query/cluster-level adaptation không? | QARF, bounded CARF diagnostic và QPAF; CARF cluster label-free, freeze trước qrels |
| RQ5 | Chi phí fusion có nằm trong operational envelope không? | Latency, CUDA allocation, finite outputs và checkpoint reload parity |
| RQ6 | Phương pháp frozen có generalize ngoài ViMDoc không? | ViDoRe V3 sealed evaluation, chỉ sau core method/config/checkpoint freeze |

Một negative result hợp lệ vẫn hoàn thành mục tiêu khoa học: khi QPAF không qua gate,
nhóm chọn QARF hoặc baseline đơn giản mạnh nhất và báo cáo kết quả âm.

## 2. Phạm vi protocol

### Trong phạm vi

- ViDoSeek cho discovery và bounded oracle diagnostics đã có.
- ViMDoc cho learned development và untouched confirmation.
- ViDoRe V3 Finance EN cho optional sealed external validation.
- Ba frozen retrieval channels: BM25, BGE-M3 và ColQwen2.5.
- Linear QARF/QPAF gates, 13 label-free features và masked listwise loss.
- Required deployable baselines, ba seed, paired statistics, latency, memory,
  checkpoint reload và independent verification.

### Ngoài phạm vi

- Fine-tune retriever, OCR hoặc encoder.
- Unrestricted hyperparameter search, broad W7/W66 sweep mới hoặc result shopping.
- Dùng qrels/oracle assignment trong candidate construction, normalization,
  feature construction, clustering hoặc inference.
- Tuyên bố answer-generation quality, production readiness hoặc general Visual RAG.

## 3. Quyết định đã freeze

| Hạng mục | Quyết định đã khóa | File chi tiết | Trạng thái |
|---|---|---|---|
| Dataset roles và split | ViDoSeek discovery; ViMDoc development/confirmation; ViDoRe V3 sealed external; ViMDoc 1.600/400/8.904 query-disjoint bằng frozen hash-order algorithm | [dataset_split_policy.md](dataset_split_policy.md) | Semantics frozen; exact ID files/hashes là downstream activation evidence |
| Primary metric | Mean per-query ViMDoc **document nDCG@10** | [metric_policy.md](metric_policy.md) | Frozen |
| Secondary metrics | Recall@1, Recall@3, MRR@10; latency, memory, reload parity là operational gates | [metric_policy.md](metric_policy.md) | Frozen |
| Seeds | `20260820`, `20260821`, `20260822`; bootstrap seed `20260820` | [seed_policy.md](seed_policy.md) | Frozen |
| Baselines | BM25, BGE-M3, ColQwen2.5, uniform CombSUM, RRF k=60, train-fitted static fusion, learned QARF | [baseline_policy.md](baseline_policy.md) | Roster/rule frozen; run evidence chưa có |
| Candidates | Top 200/kênh, qrels-free union, tối đa 600 page/query, đủ ba raw scores | [candidate_policy.md](candidate_policy.md) | Semantics frozen; real cache chưa verified |
| Statistics | Paired query bootstrap 10.000 resamples, percentile CI95, W/T/L, concentration | [statistical_policy.md](statistical_policy.md) | Frozen |
| Run/change control | Preparation → authorization → execution → independent verification tách biệt | [run_policy.md](run_policy.md) | Frozen và đã reconcile với M1.7 Draft |
| Amendments | Mọi thay đổi sau freeze phải append-only, có approval và impact analysis | [protocol_amendments.md](protocol_amendments.md) | Ledger active; chưa có amendment |

### 3.1 Reconciliation với M1.7 Draft

Protocol này đã đối chiếu với các artifact được merge từ `main`:

- [experiment_registry.csv](../04_experiment_registry/experiment_registry.csv);
- [experiment_naming_rules.md](../04_experiment_registry/experiment_naming_rules.md);
- [test_classification.md](../04_experiment_registry/test_classification.md);
- [append_only_policy.md](../04_experiment_registry/append_only_policy.md).

M1.5 đã freeze trước; sau đó Thanh dùng exact protocol version/hash để chốt M1.7 Final.
M1.7 Final **không** là prerequisite của M1.5. Registry Draft chỉ cần chứng minh schema,
naming, taxonomy và append-only rules tương thích với protocol trước khi M1.5 freeze.

Mọi protocol/amendment/gate record dùng `experiment_class=governance` và
`evidence_class=governance_record`. Registry là evidence ledger, không cấp execution
authority và không được tự relabel task khoa học.

## 4. Matched QARF/QPAF comparison rule

QARF và QPAF phải dùng chung:

- exact candidate rows và deterministic order;
- train/validation/confirmation IDs và qrels;
- 13 features, score normalization và evaluation-unit aggregation;
- loss, optimizer, learning rate, weight decay, batch size, gradient clip, maximum
  epochs, early stopping, checkpoint selection, precision, seed và data order;
- image, GPU class, wall-time/cost budget, invocation/retry policy;
- evaluation, bootstrap, latency, memory và checkpoint-reload implementation.

Khác biệt dự kiến duy nhất là `gate_granularity`:

- QARF: masked query pooling rồi broadcast một weight vector cho mọi page;
- QPAF: một weight vector riêng cho từng query-page pair.

Learned QARF phải chạy và được independent review trước khi xin authorization cho
matched learned QPAF. Không được sửa QPAF config dựa trên confirmation outcome.

## 5. Success, partial và fail rules

Một positive core claim chỉ được phép khi:

1. đủ ba seed preregistered, không chọn best seed;
2. seed-averaged paired `QPAF - QARF` mean document nDCG@10 `>= 0.01`;
3. paired query-bootstrap CI95 có cận dưới `> 0`;
4. QPAF vượt mọi co-strongest deployable baseline đã chọn bằng development rule;
5. top-5% positive-gain share `< 0.90` cho stability claim;
6. median added fusion latency `<= 10.0 ms/query`;
7. peak learned-fusion CUDA allocation `< 1.50 GiB`;
8. không có NaN/Inf và fresh-process checkpoint reload sai khác `<= 1e-7`;
9. manifest, hashes, predictions, metrics, CI và telemetry qua independent review.

Nếu quality gate đạt nhưng operational gate không đạt, chỉ được báo **research quality
result**, không được báo operationally good enough. Nếu delta/CI/seed gate không đạt,
không được tuyên bố learned QPAF improvement; kết quả âm vẫn phải được lưu và báo cáo.

## 6. Claim boundary hiện tại

Evidence hiện tại chỉ hỗ trợ phát biểu:

> Trên một ViDoSeek exploratory subset 24 query đã freeze, relevance-informed QPAF
> oracle cho positive mean nDCG@10 headroom so với QARF dưới W7 và W66, với paired
> bootstrap lower bounds dương. Đây là bounded oracle upper bound, không phải learned,
> deployable hoặc generalizable improvement.

P1-02 và formal P1-03 vẫn `BLOCKED`. P2-01/P2-02 chỉ pass ở local method-core level.
Không có learned checkpoint hoặc learned QPAF metric được protocol freeze này tạo ra.

## 7. Evidence snapshot dùng cho freeze

Snapshot đọc lại ngày 25/09/2026 sau khi merge `origin/main`, branch hiện tại
`chore/repository-hygiene`, Git HEAD
`20cb3bf6d42c1d44d4516bfb5fdc9b82c8732455`. Worktree có tracked changes và nhiều
untracked files; HEAD không được xem là clean freeze commit.

| Evidence | SHA-256 tại lúc freeze |
|---|---|
| `TIMELINE_fixed.md` | `5b43226fd2ce96e12bb930b9be59d46eab0d25ee6345cefff17de248ce371be0` |
| `PROJECT_CONTEXT.md` | `ce384db620c6ed144dab1e0b8fe91541ac796bd2929459c3df32b7da377b1ffe` |
| `Tasks.md` | `c598aab4e2f1e4a5b0c25c3692873e163dc38dbe1106cd41952ca918215e0167` |
| `Context.md` | `696ec68e05deb727a32ec8e14e5c9dd82cef21052e5b42523a11b0de13e22b32` |
| `docs/PROJECT_ROADMAP.md` | `d44e976f4a35a6c984b4db67eecdda98eabdeed06a212c7e3076c8fddc9644d9` |
| `configs/datasets.yaml` | `72c220465803d26fbe6bfec19bafa8daa391685c4c6afe3d1751c3a65faf7e86` |
| `configs/vimdoc_m3_local_v1.json` | `0a68c19688519822e4ac58afa51e08ca43ad6350d849f642bac23115bc64be9d` |
| `configs/qarf_train.yaml` | `8e61c666f7a85381e52bd6f00b5eba971601869577603fb51a8a6c77c0c7f798` |
| `configs/qpaf_train.yaml` | `28a2fac6e34447ef9e9c3624126089e0f782fd852d0e37cb3bc8df3a8a28af99` |
| `artifacts/metric_reference.json` | `39e5f2fd7393be46db9b4c9a4b98998b9212350733dfdd81b9e9038b6c3bbb84` |
| `M1_FINAL/04_experiment_registry/experiment_registry.csv` | `6b779ae9836920ff38d9169d83ace7ed1df43db30009f292cb3438933c3ae7ef` |
| `M1_FINAL/04_experiment_registry/experiment_naming_rules.md` | `574d55cb62ecb283d748275545f38ea6ec42972cc818ae6891ba2ce561822d35` |
| `M1_FINAL/04_experiment_registry/test_classification.md` | `4eee1519854ab906abefe49a352845b8a8446ed12b76d2464c544c830d165074` |
| `M1_FINAL/04_experiment_registry/append_only_policy.md` | `3bc0b85c01c3d4e3cda24aabaa7f0d5068e9a00aa0b5258adbe51f0eecf7cf23` |

Các hash trên là provenance của M1.5 freeze, không thay thế M1.4 hash manifest. Exact
hash của từng protocol file và canonical package digest nằm trong
[protocol_freeze_manifest.json](protocol_freeze_manifest.json).

## 8. Evidence còn thiếu sau M1.5 freeze

| ID | Item | Evidence cần có | Gate effect | Owner |
|---|---|---|---|---|
| PF-D01 | Chưa có `M1_FINAL/01_repository_audit/` | Repo/data/config/run inventory, Git snapshot, hash manifest và gap log từ M1.4 | Blocker cho M1.4 completion, M1.6 và G1; không được suy ra từ scoped M1.5 cross-check | Khương |
| PF-D02 | Split 1.600/400/8.904 chưa có exact ID files/hashes | Three split manifests, canonical hashes, zero-overlap check và document-overlap report | Data-activation blocker trước candidate generation/training; algorithm và counts đã freeze | Khương + Phát |
| PF-D03 | ViMDoc live archive/OCR/score cache chưa verified | Collision PASS, OCR manifest, score/cache manifest, coverage `>=0.95`, zero uncovered query | Downstream Data Readiness; phải ghi rõ chưa hoàn tất | Khương |
| PF-D04 | Train-fitted static baseline chưa có exact runnable config/hash và chưa có selection result | Roster/rule được freeze ở M1.5; exact config trước run; selection artifact chỉ sau development results | Downstream execution/result blocker, không phải prerequisite của M1.5 | Phát + Thanh |
| PF-D05 | Runtime/image/batch/timeout/cost/commands cho result-bearing runs chưa bind | Reviewed execution packages trước từng run | Downstream authorization blocker | Phát + Khương |
| PF-R06 | M1.7 Draft đã merge và reconcile; M1.7 Final chưa freeze | M1.7 Final ghi exact M1.5 protocol path/hash sau M1.5 Freeze | **Post-freeze handoff**, không phải M1.5 blocker | Thanh |
| PF-D07 | Worktree chưa clean; protocol package chưa có commit | Allowlisted protocol diff hiện được content-address bằng manifest; commit riêng vẫn cần trước result-bearing run | Git publication/execution blocker; freeze không được mô tả là clean-commit freeze | Phát + Thanh |
| PF-R08 | Chưa có independent reviewer sign-off | Thanh review byte-identical package và ghi audit/sign-off | Blocker cho independent QA/G1, không phải tuyên bố do người tạo protocol tự cấp | Thanh |

## 9. Freeze decision và boundary

Protocol `QPAF-M1.5-v1` được freeze tại
`2026-09-25T20:43:27.4530745+07:00` trên source HEAD
`20cb3bf6d42c1d44d4516bfb5fdc9b82c8732455`, branch
`chore/repository-hygiene`, với dirty worktree được ghi nhận rõ. Căn cứ freeze:

1. dataset roles/split algorithm, metrics, seeds, baseline roster/selection rule,
   candidate semantics, statistical policy và change-control đã có exact decision;
2. protocol được cross-check trực tiếp với current repository/config/data identity
   evidence; việc này không được relabel thành M1.4 completion;
3. M1.7 Draft compatibility đã được kiểm tra; M1.7 Final là bước ngay sau M1.5,
   không phải prerequisite;
4. mọi unresolved M1.4/data-readiness/authorization/QA item được gắn downstream gate
   và không bị trình bày như đã hoàn tất;
5. freeze identity và per-file/package hashes được ghi trong
   [protocol_freeze_manifest.json](protocol_freeze_manifest.json);
6. yêu cầu finalization của task owner được ghi nhận trong working session; không có
   tuyên bố independent review;
7. mọi thay đổi sau timestamp này đi qua
   [protocol_amendments.md](protocol_amendments.md).

Kết luận: **M1.5 Final Freeze hoàn tất ở lớp protocol**. M1.4, M1.6, M1.7 Final,
Independent Evidence Audit, G1 và result-bearing execution vẫn là các trạng thái riêng,
chưa được suy ra là PASS/OPEN/AUTHORIZED từ freeze này.
