# QPAF Implementation Context

This file is the standalone source of truth for implementing **Adaptive Retrieval Fusion for Visually Rich Document RAG**. It incorporates the feasibility analysis required before implementation. It does not claim that the learned method has been implemented, trained, or validated.

## Assumption Register

| ID | Underspecified in dossier | Assumption made | Rationale | Blast radius if wrong |
|---|---|---|---|---|
| A01 | The implementation repository is not named in the proposal | Use the existing `visual-rag-oracle-study` source layout (`src/oracle_study`, `tests`, `configs`) as the baseline code interface; provenance must be frozen in Phase 0 | The inspected prior checkout already implements score-cache validation, W7/W66 profiles, Global/QARF/QPAF oracle analysis, metrics, manifests, and a CLI | A different baseline repository invalidates every path and integration task in `Tasks.md` |
| A02 | Exact learned-fusion input features are not fixed | The minimum QPAF uses 13 label-free score/rank features defined below; query/page embeddings are an ablation, not part of the minimum method | This is the smallest dossier-consistent feature set that tests page-adaptive weighting without adding an encoder | If embeddings are essential, the minimum model may underestimate learnable QPAF performance |
| A03 | The gating architecture permits a linear layer or shallow MLP | Use a zero-initialized linear gate for the primary implementation; use a one-hidden-layer MLP only as a preregistered ablation | A linear gate is the cheapest faithful implementation and initializes exactly to equal fusion | If nonlinear interactions are required, the primary model may underfit |
| A04 | The training objective is not specified | Use masked listwise cross-entropy with soft targets proportional to graded relevance gain $2^r-1$ and temperature $\tau=1$ | It is differentiable, supports graded qrels, and directly trains a ranking distribution over the fixed candidate pool | A different objective can change rankings and all learned-model results |
| A05 | The proposal leaves the practical effect threshold $\delta$ open | Use $\delta=0.01$ mean per-query nDCG@10 for learned-model go/no-go decisions | It matches the existing oracle-study scale for beneficial gain and prevents treating negligible changes as success | A supervisor-approved threshold would replace all gates that cite $0.01$ |
| A06 | Team schedule and submission deadline are absent | Use 2026-09-05 as the Phase 1 decision checkpoint, not as a submission deadline | A concrete gate date is required by the execution prompt | Any real deadline changes task priority and feasible benchmark scope |
| A07 | Exact Modal resource settings are not declared | Use Modal as the only training and GPU score-extraction environment, with `gpu="L4"` as the human-approved default for environment probes and learned fusion; use `A100-40GB` only for full score extraction because the measured L4 capacity is below the frozen 23.5 GiB extractor guard; local execution is limited to documentation, non-training unit tests, schema checks, and optional cached-score oracle analysis | The user explicitly approved L4 on 2026-08-25 to reduce cost; learned fusion is lightweight, while full retriever extraction must preserve its frozen memory contract | A different Modal GPU/image/region changes cost, memory limits, runtime estimates, and reproducibility manifests |
| A08 | Exact dense and visual checkpoints are not frozen in the proposal | Preserve the prior pipeline choices BGE-M3 for dense-text and ColQwen2.5 for visual scoring until Phase 0 records exact model revisions; BM25 indexes OCR Markdown | These are the concrete retrievers used by the inspected prior runbook and match the three-channel proposal | Changing a retriever invalidates cached scores and every comparison |
| A09 | Candidate depth for the three-channel learned study is not fixed | Start with top 200 from each channel, yielding at most $C=600$ unique candidates per query; expand only through a separately recorded protocol change | It bounds memory and matches the existing candidate-pool scale while adding the third channel explicitly | A lower union recall can falsely suppress fusion headroom |
| A10 | Number of seeds is not specified | Use seeds 20260820, 20260821, and 20260822 for learned fusion | Three seeds are the minimum planned estimate of run-to-run variability | Three seeds may still be insufficient if variance is large; Phase 3 must report this limitation |

## Blocking Issues

| ID | Blocking issue | Location | Why it blocks | Required resolution |
|---|---|---|---|---|
| B01 | Current `tlcn` folder is not a Git repository | Workspace inspection on 2026-08-25 | Run manifests cannot name a commit or preserve a dirty diff | Initialize or select a Git repository, import the baseline snapshot, and record an immutable commit before any reportable run |
| B02 | Baseline source snapshot has no verified Git commit | Prior `visual-rag-oracle-study` checkout | File contents were inspected and tests pass, but source provenance is not immutable | Hash every imported source file and create the first baseline commit; record the source snapshot manifest |
| B03 | No dataset, qrels, raw-score table, or `_SUCCESS.json` is present in this workspace | Workspace and prior checkout inspection | Baseline metrics, candidate coverage, oracle headroom, memory on real batches, and learned performance cannot be measured | Complete score extraction and import the ten-artifact bundle with `_SUCCESS.json` and matching SHA-256 manifest |
| B04 | Modal app, pinned image, authentication, GPU class, persistent Volume, Secrets, and timeout are not yet configured | Environment inspection and user correction on 2026-08-25 | No training job can be submitted reproducibly until the remote contract exists | Create and verify `modal_app.py`, pin the image and Modal dependency, authenticate the workspace, and capture the remote environment probe before Phase 1 |
| B05 | Local PyTorch is CPU-only and the visible GPU is an NVIDIA GeForce MX130 with 2,048 MiB | Local environment inspection on 2026-08-25 | It is at least 22 GiB below the documented 24 GiB extraction minimum: $(24-2)/24=91.7\%$ shortfall (derived), and the user prohibits local training | Never train or extract retriever scores locally; submit those jobs to Modal and persist artifacts to the approved Modal Volume |
| B06 | ViDoSeek and ViMDoc revisions and licenses are not recorded | Proposal dataset sequence | Discovery/confirmation splits cannot be made reproducible | Record dataset identifiers, revisions, licenses, file counts, split hashes, and qrels checksums before Phase 1 |
| B07 | CARF clustering protocol is described conceptually but not present in the inspected code | Proposal versus baseline code | CARF results would otherwise require an invented clustering definition | Before CARF implementation, approve $K=3$, sensitivity $K\in\{2,4\}$, feature space, seed 20260820, and the rule that qrels never enter clustering |

There is no mathematical inconsistency in the QPAF scoring equations. The feasibility verdict is **GO-WITH-CONDITIONS**: cached-score oracle and learned fusion are technically small, but reportable implementation is blocked by B01–B07. No task after Phase 0 may run until its corresponding blocker is resolved.

## 1. Objective

**Falsifiable hypothesis:** after controlling the candidate pool, score normalization, retrievers, split, and training budget, label-free query–page features allow a learned QPAF gate to improve mean per-query nDCG@10 by at least $0.01$ over the strongest deployable fixed or query-adaptive fusion baseline on confirmation data.

**Observable confirmation:** across seeds 20260820–20260822 trained on Modal, learned QPAF has mean $\Delta\mathrm{nDCG@10}\ge0.01$ versus the strongest deployable baseline, its query-bootstrap 95% confidence interval has lower bound $>0$, and its added median fusion latency is $\le10$ ms/query on the declared Modal evaluation hardware. Oracle results do not satisfy this objective.

**Falsification:** QPAF oracle adds less than $0.01$ mean nDCG@10 over QARF on confirmation data, or learned QPAF fails the observable confirmation above. In that case, select QARF or fixed fusion rather than increasing model complexity.

## 2. Mathematical and Algorithmic Foundation

### 2.1 Symbols

| Symbol | Domain and shape | Meaning |
|---|---|---|
| $B$ | positive integer | Query batch size; primary bound $B\le32$ |
| $C$ | positive integer | Padded candidate count; primary bound $C\le600$ |
| $M$ | $3$ | Retrieval channels in fixed order BM25, dense-text, visual |
| $F$ | $13$ | Minimum label-free feature count |
| $q_b$ | identifier/string | Query for batch item $b$ |
| $p_{bi}$ | identifier/string | Candidate page at padded index $i$ |
| $X$ | $[B,C,M]$, float32 | Finite min–max-normalized retrieval scores |
| $H$ | $[B,C,F]$, float32 | QPAF feature tensor |
| $A$ | $[B,C]$, bool | Valid-candidate mask |
| $R$ | $[B,C]$, float32 | Graded relevance, used only in training/evaluation |
| $Z$ | $[B,C,M]$, float32 | Gate logits |
| $W$ | $[B,C,M]$, float32 | Non-negative channel weights summing to one |
| $S$ | $[B,C]$, float32 | Fused candidate scores |
| $Y$ | $[B,C]$, float32 | Normalized relevance-gain target distribution |
| $P$ | $[B,C]$, float32 | Predicted candidate distribution |
| $\Theta,b$ | $[M,F]$, $[M]$, float32 | Linear-gate weight and bias |
| $\tau$ | positive scalar | Listwise temperature; fixed to $1.0$ in the primary experiment |

### 2.2 Candidate pool and normalization

The label-free candidate union is

$$
\mathcal{C}_q=
\operatorname{Top}_{200}^{B}(q)\cup
\operatorname{Top}_{200}^{D}(q)\cup
\operatorname{Top}_{200}^{V}(q),
\qquad |\mathcal{C}_q|\le600. \tag{1}
$$

For channel $m$, min–max normalization is computed over the fixed union:

$$
X_{bim}=
\begin{cases}
\dfrac{s_{bim}-\min_{j:A_{bj}=1}s_{bjm}}
{\max_{j:A_{bj}=1}s_{bjm}-\min_{j:A_{bj}=1}s_{bjm}},
& \text{if range}>10^{-15},\\[6pt]
0, & \text{otherwise.}
\end{cases} \tag{2}
$$

The hard branch in Eq. 2 is offline preprocessing with accepted gradient blocking. Raw retriever scores and candidate construction are frozen; no gradient is required through retrieval, top-$K$, set union, ranking, or normalization.

### 2.3 Feature construction

For each valid candidate, concatenate:

$$
H_{bi}=\left[
X_{bi,:},
\rho_{bi,:},
X_{bi,:}-\operatorname{median}_{j:A_{bj}=1}X_{bj,:},
g_{b,:},
d_{bi}
\right]\in\mathbb{R}^{13}, \tag{3}
$$

where $\rho_{bim}\in[0,1]$ is deterministic normalized rank with page ID as the tie-break, $g_{bm}=X_{b(1)m}-X_{b(2)m}$ is the top-1/top-2 gap broadcast to every candidate, and $d_{bi}=\operatorname{std}_m(\rho_{bim})\in[0,0.5]$ is rank disagreement. Sorting, ranks, and median are label-free non-differentiable feature preprocessing; gradients stop at $H$.

### 2.4 QPAF forward pass

The primary linear gate is

$$
Z_{bi}=\Theta H_{bi}+b, \qquad \Theta\in\mathbb{R}^{3\times13},\quad b\in\mathbb{R}^{3}. \tag{4}
$$

Channel weights and fused scores are

$$
W_{bim}=\frac{\exp Z_{bim}}{\sum_{k=1}^{3}\exp Z_{bik}}, \tag{5}
$$

$$
S_{bi}=\sum_{m=1}^{3}W_{bim}X_{bim}. \tag{6}
$$

Padded positions are excluded by $A$ from every reduction. Initialize $\Theta=0$ and $b=0$ so Eq. 5 gives exactly $(1/3,1/3,1/3)$ at step 0.

### 2.5 Training loss and backward derivation

For each query containing at least one positive candidate, define relevance-gain targets and the predicted listwise distribution:

$$
Y_{bi}=\frac{A_{bi}(2^{R_{bi}}-1)}{\sum_j A_{bj}(2^{R_{bj}}-1)}, \tag{7}
$$

$$
P_{bi}=\frac{A_{bi}\exp(S_{bi}/\tau)}{\sum_j A_{bj}\exp(S_{bj}/\tau)}, \tag{8}
$$

$$
\mathcal{L}=-\frac{1}{B}\sum_{b=1}^{B}\sum_{i=1}^{C}Y_{bi}\log P_{bi}. \tag{9}
$$

Implementation must use masked `log_softmax` in fp32 rather than exponentiating Eq. 8 directly. For valid positions,

$$
\frac{\partial\mathcal{L}}{\partial S_{bi}}=
\frac{P_{bi}-Y_{bi}}{B\tau}. \tag{10}
$$

Since $S_{bi}=W_{bi}^{\top}X_{bi}$ and $W_{bi}=\operatorname{softmax}(Z_{bi})$,

$$
\frac{\partial\mathcal{L}}{\partial Z_{bik}}=
\frac{P_{bi}-Y_{bi}}{B\tau}
W_{bik}\left(X_{bik}-S_{bi}\right). \tag{11}
$$

For the linear gate,

$$
\frac{\partial\mathcal{L}}{\partial\Theta}
=\sum_{b,i}\frac{\partial\mathcal{L}}{\partial Z_{bi}}H_{bi}^{\top},
\qquad
\frac{\partial\mathcal{L}}{\partial b}
=\sum_{b,i}\frac{\partial\mathcal{L}}{\partial Z_{bi}}. \tag{12}
$$

At zero initialization, $W_{bim}=1/3$ (derived). With uniform candidate predictions the initial per-query loss is $\log C_b$; for $C_b=600$, $\log 600=6.397$ (derived). The gate gradient is bounded by the normalized score range and is clipped to global norm $1.0$ as a guard. A constant score vector produces zero gate gradient via $X_{bik}-S_{bi}=0$; this is a detectable degenerate batch, not a numerical error.

### 2.6 QARF, CARF, and oracle roles

QARF uses query-pooled features $\bar H_b=\sum_iA_{bi}H_{bi}/\sum_iA_{bi}$ in Eq. 4 and broadcasts one $W_b$ to every candidate. CARF uses a fixed, label-free cluster assignment $K_{bi}\in\{0,\ldots,k-1\}$, pools features by cluster, and broadcasts one weight vector per cluster. Clustering is outside the gradient path. QPAF uses Eq. 4 independently at every valid page.

Oracle Global/QARF/CARF/QPAF searches only the preregistered $W_7$ and, after the gate, $W_{66}$. Oracle uses qrels to choose profiles and is never called a deployable model. Learned methods never receive oracle profiles or qrels as inference features.

### 2.7 Complexity

Feature construction is $O(BCM\log C)$ if ranks use sorting; gating and fusion are $O(BCFM)$. The linear gate has $MF+M=3\cdot13+3=42$ parameters (derived). At $B=32,C=600,F=13,M=3$, the core forward tensors $H,Z,W,S$ contain

$$
32\cdot600\cdot(13+3+3+1)=384{,}000
$$

float32 values, or $384{,}000\cdot4/2^{20}=1.465$ MiB (derived). Allowing three copies for backward yields approximately $4.40$ MiB (estimated). Candidate score extraction, not fusion, is expected to dominate compute and VRAM.

## 3. Architecture Specification

| Module | Responsibility | Input → output | Learnable parameters | Initialization | Equations |
|---|---|---|---|---|---|
| `ScoreCacheValidator` | Validate schema, finiteness, uniqueness, qrels provenance, and candidate coverage | Parquet rows → validated table | None | N/A | 1–2 |
| `CandidateUnionBuilder` | Stable top-200 union without qrels | Three ranked lists → $\mathcal C_q$ | None | N/A | 1 |
| `MinMaxNormalizer` | Per-query/per-channel normalization | raw scores $[C,3]$ → $X[C,3]$ | None | N/A | 2 |
| `FusionFeatureBuilder` | Build 13 label-free features | $X[C,3]$, page IDs → $H[C,13]$ | None | N/A | 3 |
| `LinearQPAFGate` | Produce page-specific channel weights | $H[B,C,13]$ → $W[B,C,3]$ | $\Theta[3,13],b[3]$ | All zeros | 4–5 |
| `LinearQARFGate` | Produce one query-level channel weight vector | pooled $H[B,13]$ → $W[B,1,3]$ | $\Theta[3,13],b[3]$ | All zeros | 4–5 |
| `LinearCARFGate` | Produce one weight vector per fixed candidate cluster | cluster-pooled $H[B,k,13]$ → $W[B,k,3]$ | $\Theta[3,13],b[3]$ | All zeros | 4–5 |
| `FusionScorer` | Apply convex fusion | $X,W,A$ → $S[B,C]$ | None | N/A | 6 |
| `ListwiseRankLoss` | Train on graded relevance | $S,R,A$ → scalar loss | None | N/A | 7–12 |
| `RankingEvaluator` | Deterministic ranking with page-ID tie-break | $S,R,A$ → metrics | None | N/A | Metric protocol below |

No custom CUDA kernel is required or permitted for the primary implementation.

## 4. ASCII Tensor Flow

```text
 three ranked score tables per query
 BM25 [C_B] f64   Dense [C_D] f64   Visual [C_V] f64
          \              |              /
           \             |             /
            +---- CandidateUnionBuilder ----+  Eq. 1; stop-gradient
                              |
                              v
                 raw_scores [B,C,3] f64 CPU
                              |
                    MinMaxNormalizer  Eq. 2
                              |
                              v
                    X [B,C,3] f32 device
                              |
                  FusionFeatureBuilder Eq. 3
                              |
                              v
                    H [B,C,13] f32 device
                              |
                    LinearQPAFGate Eq. 4
                              |
                              v
                    Z [B,C,3] f32 device
                              |
                       softmax Eq. 5
                              |
                              v
                    W [B,C,3] f32 device
                              |
                    FusionScorer Eq. 6
                              |
                              v
                    S [B,C] f32 device
                       /              \
                      / train          \ eval
                     v                  v
       ListwiseRankLoss Eq. 7-12    RankingEvaluator
       R [B,C] + A [B,C]           nDCG@10, R@1, R@3, MRR@10
```

## 5. Tensor Shape Contract

| Name | Shape | Dtype | Device | Constraint |
|---|---:|---|---|---|
| `raw_scores` | $[B,C,3]$ | float64 | CPU | finite on valid positions; channel order BM25, dense, visual |
| `scores` / $X$ | $[B,C,3]$ | float32 | CPU or CUDA | valid values in $[0,1]$ within $10^{-6}$ |
| `features` / $H$ | $[B,C,13]$ | float32 | same as $X$ | finite; label-free; padded rows zero |
| `valid_mask` / $A$ | $[B,C]$ | bool | same as $X$ | at least two valid candidates per query |
| `relevance` / $R$ | $[B,C]$ | float32 | same as $X$ | non-negative; at least one positive per training query |
| `logits` / $Z$ | $[B,C,3]$ | float32 | same as $X$ | finite on valid rows |
| `weights` / $W$ | $[B,C,3]$ | float32 | same as $X$ | each valid row in $[0,1]$; row sum $1\pm10^{-6}$ |
| `fused_scores` / $S$ | $[B,C]$ | float32 | same as $X$ | finite on valid positions; padded positions masked |
| `target_distribution` / $Y$ | $[B,C]$ | float32 | same as $X$ | valid row sum $1\pm10^{-6}$ |
| `loss` | scalar | float32 | same as $X$ | finite and non-negative |
| `cluster_ids` / $K$ | $[B,C]$ | int64 | same as $X$ | $-1$ for padding; otherwise $0\le K<k$ |

## 6. Numerical Stability Requirements

| Operation | Guard | Required assertion |
|---|---|---|
| Offline min–max | If range $\le10^{-15}$, emit zeros | All normalized values finite and in $[0,1]\pm10^{-12}$ in float64 |
| Model input cast | Cast validated values once to float32 | `torch.isfinite(scores).all()` on valid positions |
| Masked listwise loss | Reject queries with no valid or no positive candidate; use `log_softmax` | Per-query target mass equals one within $10^{-6}$ |
| Softmax weights | Use PyTorch stable softmax in fp32 | Weight sums equal one within $10^{-6}$ |
| AMP | Keep normalization, logits, softmax, `log_softmax`, loss, and metrics in fp32 | Loss and every parameter gradient finite after backward |
| Gradient update | Global gradient norm clip at $1.0$ | Post-clip norm $\le1.0001$ |
| Ranking ties | Stable descending score, ascending page ID | Repeated evaluation produces identical order |
| Padded rows | Zero feature rows; mask before loss/metric | Changing padded values does not change loss within $10^{-7}$ |

Enable `torch.autograd.set_detect_anomaly(True)` only for the first 100 debug steps because it adds synchronization and memory overhead; disable it for measured runs. Fail immediately on NaN/Inf rather than replacing model outputs.

## 7. Pipeline, Memory, and Environment Constraints

**Execution boundary:** no QARF, CARF, QPAF, retriever, ablation, or benchmark training may run on the local machine. Local commands may render/read documentation, validate manifests and schemas, run non-training unit tests on tiny deterministic fixtures, and analyze already-cached scores. Any command that creates optimizer steps or trained checkpoints must execute inside a Modal Function.

### 7.1 Observed environment

| Item | Observed value on 2026-08-25 |
|---|---|
| Local OS | Windows / PowerShell |
| Python | 3.13.7 |
| PyTorch | 2.11.0+cpu |
| Visible GPU | NVIDIA GeForce MX130, 2,048 MiB |
| Driver | 581.83 |
| CUDA toolkit | Not installed |
| Current workspace Git state | Not a Git repository |
| Datasets in workspace | None |
| Existing oracle test command | `$env:PYTHONPATH='src'; python -m pytest -q` (non-training code tests only) |
| Existing oracle test result | 29 passed in 5.13 s (measured locally); this is code validation, not experimental validation |

### 7.2 Modal execution and VRAM budget

For $B=32,C=600,F=13$, the 42-parameter linear gate uses $42\cdot4=168$ bytes for parameters and three additional fp32 copies for gradients plus Adam moments, totaling $42\cdot4\cdot4=672$ bytes (derived). Core retained activations are approximately 4.40 MiB (estimated from the three-copy bound above). Budgeting 1.00 GiB for CUDA context, 0.25 GiB for allocator/framework fragmentation, and 0.01 GiB for model, activations, dataloader staging, and safety rounding gives $1.00+0.25+0.01=1.26$ GiB (estimated). Against 2.00 GiB, headroom is $0.74/2.00=37\%$ (derived), but this has not been measured because local PyTorch is CPU-only.

The approved default Modal Function uses a pinned `modal.Image`, `gpu="L4"`, an explicit timeout, one persistent Volume for score caches/checkpoints/run artifacts, and Secrets only for credentials. `A100-40GB` is reserved for full score extraction under the frozen guard. Modal source must be added from the versioned repository; a run manifest records the Modal package version, image definition hash, Function name, App/run identifier, requested and actual GPU, VRAM in decimal GB and binary GiB, driver, CUDA, PyTorch, Volume name, command, commit, config hash, and data hashes.

Hard learned-fusion cap: `torch.cuda.max_memory_allocated() < 1.50 GiB` on Modal. Exceeding it halts the run; batch size must not be silently changed. The 2026-08-25 Modal probe measured 22.034 GiB on the allocated L4. Against that capacity, the estimated $1.26$ GiB fusion footprint leaves $(22.034-1.26)/22.034=94.28\%$ headroom (derived from measured capacity and estimated footprint). This is not a measured training peak and must be replaced by telemetry after the first remote smoke job.

Offline BGE-M3/ColQwen2.5 score extraction has a frozen `23.5` GiB preflight guard in the inspected runbook (an operational threshold, not a measured peak in this session). The 2 GiB local GPU is not eligible. The 2026-08-25 Modal probe measured the L4 at 23.659 decimal GB but 22.034 GiB, which is $23.5-22.034=1.466$ GiB, or $1.466/23.5=6.24\%$, below the frozen guard (derived). Therefore full extraction uses `A100-40GB`; do not weaken the guard or change batch size silently. Exact allocated GPU/VRAM, PyTorch, CUDA, driver, model revisions, Modal image definition, and measured peak must be written to the run manifest before Phase 1.

### 7.3 Scaling and runtime

Fusion activation memory scales linearly in $BC(F+2M+1)$. Candidate count $C$ is the first controllable variable; it may only change through the candidate-pool sensitivity experiment because changing it changes retrieval coverage. No responsible Modal GPU-hour or cost estimate is possible before B03/B04 are resolved. The cheapest disproof after a valid cache exists is CPU-capable W7 oracle analysis: existing code has 29 non-training tests completing in 5.13 seconds locally (measured), but real oracle runtime remains unmeasured.

Optimization levers ranked by benefit/cost for learned fusion are: (1) stream query batches from Parquet instead of materializing all features; (2) mixed precision for cached features only while retaining softmax/loss in fp32; (3) reduce dataloader prefetch if host RAM grows; (4) gradient checkpointing is not justified for a single linear layer; (5) custom CUDA kernels are out of scope.

## 8. Baseline and Evaluation Protocol

### 8.1 Code baseline

The inspected baseline package is `visual-rag-oracle-study` version 0.1.0 with modules:

- `src/oracle_study/cache.py`: score-cache construction and coverage checks;
- `src/oracle_study/metrics.py`: stable ranking, nDCG@10, Recall@1, Recall@3, MRR@10, min–max;
- `src/oracle_study/profiles.py`: exact W7 and W66 simplex profiles;
- `src/oracle_study/qpaf.py`: Global, QARF, and candidate-level QPAF oracle;
- `src/oracle_study/bootstrap.py`: query bootstrap confidence intervals;
- `src/oracle_study/decision.py`: preregistered decision gates;
- `src/oracle_study/manifest.py`: run provenance;
- `configs/preregistered.yaml`: seed 20260820 and oracle thresholds.

No Git commit exists for the inspected snapshot. Phase 0 must freeze it before edits. The exact baseline code check is:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

Acceptance is exactly 29 passed, 0 failed, 0 errors before new tests are added. This reproduces software behavior only; there is no published or completed experimental number available to reproduce.

### 8.2 Raw-score contract

One row per `(dataset, query_id, page_id)` must include finite `bm25_score`, `dense_score`, and `visual_score`, plus non-negative `relevance`, `source`, split, retriever revisions, and candidate provenance. For compatibility with the inspected baseline cache builder, the imported raw table also carries `stage1_score`, `full_score`, `stage2_ms`, and `stage2_flops`; these HEAVEN fields are not QPAF input features. Duplicate keys are forbidden. The file and qrels receive SHA-256 hashes. Minimum relevant-page coverage is $0.95$ before oracle or training.

### 8.3 Metrics

Primary metric is mean per-query nDCG@10 using gain $2^r-1$ and discount $1/\log_2(i+2)$. Secondary metrics are Recall@1, Recall@3, and MRR@10. Ranking sorts by descending score with ascending `page_id` as deterministic tie-break. Use `src/oracle_study/metrics.py`; do not substitute a library implementation without an equivalence test on hand-computed fixtures.

### 8.4 Dataset sequence

Discovery: ViDoSeek. Confirmation: a frozen 2,000-query ViMDoc sample. External validation: sealed ViDoRe V3. Long-document validation: MMDocIR. Vietnamese evaluation is separate and may use ViOCRVQA/ReceiptVQA only after page-level retrieval qrels are validated. Dataset IDs, revisions, licenses, and split hashes are Phase 0 deliverables.

## 9. Risk and Failure Modes

| ID | Risk | Category | Likelihood | Impact | Observable signal | Detection method | Mitigation | Fallback | Decision point |
|---|---|---|---|---|---|---|---|---|---|
| R01 | Qrels leak into candidates/features/clusters | Scientific | Medium | Fatal | Feature or cache provenance references relevance/test labels | Provenance audit and forbidden-column test | Separate score and label joins; whitelist feature columns | Kill affected runs and rebuild cache | Before Phase 1 |
| R02 | Candidate pool misses relevant pages | Scientific | Medium | High | Relevant-page coverage below 0.95 | `preflight` coverage report | Expand top-$K$ under recorded protocol | Stop adaptive study if coverage remains low | P0 gate |
| R03 | Oracle gain is construction-driven and concentrated | Scientific | High | High | Top 5% queries contribute at least 90% of positive gain | Query-bootstrap and concentration report | Require gain, CI, and coverage together | Prefer QARF/fixed fusion | P1 gate |
| R04 | Learned gate collapses to one channel | Optimization | Medium | High | Mean weight entropy below 0.05 and one channel receives over 0.98 mean weight without metric gain | Log weight entropy and channel mass | Zero initialization, weight decay, early stopping | Revert to QARF/fixed fusion | First 100 steps and validation |
| R05 | Gate receives zero gradient | Optimization | Medium | High | Every parameter gradient norm below $10^{-10}$ for 10 consecutive non-degenerate batches | Gradient hook/test | Verify feature variance and Eq. 11 | Halt; do not tune LR | Phase 2 bring-up |
| R06 | NaN/Inf in normalization or loss | Numerical | Low | High | Non-finite score, loss, or gradient | Boundary tests plus finite assertions | Eq. 2 constant-range branch; masked `log_softmax` | Kill run and repair data/math | Any occurrence |
| R07 | Empty-positive query enters training | Data | Medium | High | Target gain denominator equals zero | Schema validation | Exclude only by preregistered rule and report count | Halt if any test query lacks defined evaluation handling | P0/P2 |
| R08 | GPU OOM during retriever extraction | Memory | High locally | High | Peak allocation exceeds declared VRAM or OOM | Remote manifest and peak-memory log | Use approved 24+ GiB GPU and cache outputs | Do not reduce experimental settings silently | Extraction preflight |
| R09 | Host RAM growth across epochs | Memory | Medium | Medium | Resident memory rises over 5% across three identical epochs | Process-memory logging | Stream Parquet, detach logging tensors | Reduce prefetch only through config | Phase 2 smoke run |
| R10 | Nondeterministic tie ranking | Reproducibility | Medium | Medium | Same scores yield different page order | Repeat-ranking unit test | Ascending page-ID tie-break | Kill affected results | Phase 0 |
| R11 | Existing baseline cannot be reproduced | Baseline | Medium | Fatal | Not exactly 29 passing tests or manifest hash mismatch | Baseline test and snapshot verification | Restore frozen snapshot/environment | Halt project | P0 gate |
| R12 | Learned gain lies inside seed variance | Scientific | High | High | $\Delta<0.01$ or bootstrap lower bound $\le0$ | Three seeds plus query bootstrap | Report inconclusive; do not claim improvement | Select simpler fusion | P3 gate |
| R13 | Test set influences model selection | Scientific | Medium | Fatal | Test metric timestamp precedes frozen config/model hash | Manifest chronology audit | Seal test command until final run | Kill contaminated study | Before external evaluation |
| R14 | CARF clusters use qrels | Scientific | Low | Fatal | Cluster artifact depends on relevance column/hash | Input-column whitelist | Cluster score/rank features only | Omit CARF | Before CARF run |
| R15 | Local/remote dependency drift | Reproducibility | High | High | Environment lock or model revision differs | Manifest comparison | Pin dependencies and model revisions | Re-run all affected results | Every run |

**Feasibility verdict:** GO-WITH-CONDITIONS. The three most likely project killers are: (1) insufficient candidate complementarity, detected by union coverage and oracle gain in Phase 1 by 2026-09-05; (2) page-level oracle gain below $0.01$ over QARF, detected in the same Phase 1 report; and (3) learned QPAF failing to generalize beyond seed variance, detected in Phase 3 before external claims.

**Cheapest disproof:** validate a real three-channel score cache, then run exhaustive W7 Global/QARF/QPAF oracle analysis on ViDoSeek. It requires no learned model and no retriever GPU after caching. Estimated engineering effort is 0.5 day once the cache exists; GPU cost for fusion is 0 GPU-hours (estimated), while score-extraction cost is unknown until the remote environment is declared. This is Phase 1 in `Tasks.md`.

## 10. Results Table Shell

All cells marked `—` are unmeasured. Oracle rows must remain visually separated from deployable rows.

| Class | Method | ViDoSeek nDCG@10 | ViMDoc nDCG@10 | Recall@1 | Recall@3 | MRR@10 | Seeds | Added latency ms/query | Status / success target |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Retriever | BM25 | — | — | — | — | — | 0 | — | Baseline |
| Retriever | BGE-M3 dense | — | — | — | — | — | 0 | — | Baseline |
| Retriever | ColQwen2.5 visual | — | — | — | — | — | 0 | — | Baseline |
| Deployable | RRF | — | — | — | — | — | 0 | — | Baseline |
| Deployable | Fixed weighted fusion | — | — | — | — | — | 0 | — | Strongest static baseline |
| Deployable | Learned QARF | — | — | — | — | — | 3 | — | Query-adaptive baseline |
| Deployable | Learned CARF | — | — | — | — | — | 3 | — | Run only if CARF gate passes |
| Deployable | Learned QPAF | — | — | — | — | — | 3 | — | $\Delta\ge0.01$, CI low $>0$, latency $\le10$ ms/query |
| Oracle upper bound | Global W7/W66 | — | — | — | — | — | N/A | N/A | Not deployable |
| Oracle upper bound | QARF W7/W66 | — | — | — | — | — | N/A | N/A | Not deployable |
| Oracle upper bound | CARF W7/W66 | — | — | — | — | — | N/A | N/A | Not deployable |
| Oracle upper bound | QPAF W7/W66 | — | — | — | — | — | N/A | N/A | Headroom only |

## 11. Out of Scope

- Fine-tuning BM25, BGE-M3, ColQwen2.5, OCR, or any document encoder.
- Replacing the three retrievers or adding a fourth channel without a new approved proposal.
- End-to-end answer generation or evaluating answer quality as if it were retrieval quality.
- Using qrels in candidate generation, normalization, feature construction, clustering, or inference.
- Claiming oracle gain as learned or deployable performance.
- Local training or local retriever score extraction; all optimizer-bearing jobs and GPU extraction run on Modal.
- Custom CUDA kernels, distributed training, model serving, UI work, or production deployment.
- Silent changes to datasets, splits, candidate depth, W7/W66, normalization, metrics, seeds, or thresholds.
- Treating VQA accuracy as page-retrieval evidence without a validated retrieval corpus and qrels.
