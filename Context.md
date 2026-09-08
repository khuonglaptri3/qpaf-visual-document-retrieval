# QPAF Implementation Context

This file is the standalone source of truth for implementing **Adaptive Retrieval Fusion for Visually Rich Document RAG**. It incorporates the feasibility analysis required before implementation. It does not claim that the learned method has been implemented, trained, or validated.

## Assumption Register

| ID | Underspecified in dossier | Assumption made | Rationale | Blast radius if wrong |
|---|---|---|---|---|
| A01 | The implementation repository is not named in the proposal | Use the existing `visual-rag-oracle-study` source layout (`src/oracle_study`, `tests`, `configs`) as the baseline code interface; provenance must be frozen in Phase 0 | The inspected prior checkout already implements score-cache validation, W7/W66 profiles, Global/QARF/QPAF oracle analysis, metrics, manifests, and a CLI | A different baseline repository invalidates every path and integration task in `Tasks.md` |
| A02 | Exact learned-fusion input features are not fixed | The minimum QPAF uses 13 label-free score/rank features defined below; query/page embeddings are an ablation, not part of the minimum method | This is the smallest dossier-consistent feature set that tests page-adaptive weighting without adding an encoder | If embeddings are essential, the minimum model may underestimate learnable QPAF performance |
| A03 | The gating architecture permits a linear layer or shallow MLP | Use a zero-initialized linear gate for the primary implementation; use a one-hidden-layer MLP only as a preregistered ablation | A linear gate is the cheapest faithful implementation and initializes exactly to equal fusion | If nonlinear interactions are required, the primary model may underfit |
| A04 | The training objective is not specified | Use masked listwise cross-entropy with soft targets proportional to graded relevance gain $2^r-1$ and temperature $\tau=1$ over the declared evaluation unit: pages for page-qrels datasets and HEAVEN documents after max-over-page aggregation for ViMDoc | It is differentiable almost everywhere, supports graded qrels, and aligns training with each frozen evaluation protocol | A different objective or aggregation can change rankings and all learned-model results |
| A05 | The proposal leaves the practical effect threshold $\delta$ open | Use $\delta=0.01$ mean per-query nDCG@10 for learned-model go/no-go decisions | It matches the existing oracle-study scale for beneficial gain and prevents treating negligible changes as success | A supervisor-approved threshold would replace all gates that cite $0.01$ |
| A06 | Team schedule and submission deadline are absent | Use 2026-09-05 as the Phase 1 decision checkpoint, not as a submission deadline | A concrete gate date is required by the execution prompt | Any real deadline changes task priority and feasible benchmark scope |
| A07 | Exact Modal resource settings are not declared | Use Modal as the only training and GPU score-extraction environment, with `gpu="L4"` as the human-approved default for environment probes and learned fusion; after the measured L4 calibration, the user approved L4 for frozen-protocol full ViDoSeek extraction on 2026-08-29, while the generic ViDoRe extractor remains on `A100-40GB`; on 2026-08-30 the user separately approved one human-run P1-02R all-corpus extraction on L4 with fixed query/page chunks 8/512 and visual batch 128; that invocation completed, passed local integrity verification on 2026-08-31, consumed the one approval, and is closed in the current checkout; local execution is limited to documentation, non-training unit tests, schema checks, and optional cached-score oracle analysis | The dataset-specific approvals reduce cost without changing models, batch sizes, or the 23.5 decimal-GB preflight guard; separating P1-02R prevents reusing approval across a materially larger candidate workload | A different Modal GPU/image/region, candidate workload, retry, or second invocation requires new approval and changes cost, memory limits, runtime estimates, and reproducibility manifests |
| A08 | Exact dense and visual checkpoints are not frozen in the proposal | Preserve the prior pipeline choices BGE-M3 for dense-text and ColQwen2.5 for visual scoring until Phase 0 records exact model revisions; BM25 indexes OCR Markdown | These are the concrete retrievers used by the inspected prior runbook and match the three-channel proposal | Changing a retriever invalidates cached scores and every comparison |
| A09 | Candidate depth for the three-channel learned study is not fixed | Start with top 200 from each channel, yielding at most $C=600$ unique candidates per query; expand only through a separately recorded protocol change | It bounds memory and matches the existing candidate-pool scale while adding the third channel explicitly | A lower union recall can falsely suppress fusion headroom |
| A10 | Number of seeds is not specified | Use seeds 20260820, 20260821, and 20260822 for learned fusion | Three seeds are the minimum planned estimate of run-to-run variability | Three seeds may still be insufficient if variance is large; Phase 3 must report this limitation |
| A11 | ViMDoc contains 362 unique raw `doc_ids` that do not resolve to exactly one extension-stripped page ID; the archive exposes 70,080 unique extension-stripped stems from 76,347 image assets, and the official HEAVEN transform yields 1,247 evaluation groups versus the card's 1,379 source documents | Following human approval on 2026-08-26, use the official HEAVEN document mapping (remove the final underscore segment from both page names and ground-truth IDs), score each document by its maximum page score, and apply loss/metrics at document level | This preserves QPAF page-specific weights while making the ViMDoc comparison match HEAVEN instead of fabricating page labels | ViMDoc confirmation claims are invalid if page-level labels are substituted, unmatched IDs are dropped, or a different aggregation is used |

## Original Feasibility Blocking Issues (2026-08-25 Snapshot)

| ID | Blocking issue | Location | Why it blocks | Required resolution |
|---|---|---|---|---|
| B01 | Current `tlcn` folder is not a Git repository | Workspace inspection on 2026-08-25 | Run manifests cannot name a commit or preserve a dirty diff | Initialize or select a Git repository, import the baseline snapshot, and record an immutable commit before any reportable run |
| B02 | Baseline source snapshot has no verified Git commit | Prior `visual-rag-oracle-study` checkout | File contents were inspected and tests pass, but source provenance is not immutable | Hash every imported source file and create the first baseline commit; record the source snapshot manifest |
| B03 | No dataset, qrels, raw-score table, or `_SUCCESS.json` is present in this workspace | Workspace and prior checkout inspection | Baseline metrics, candidate coverage, oracle headroom, memory on real batches, and learned performance cannot be measured | Complete score extraction and import the ten-artifact bundle with `_SUCCESS.json` and matching SHA-256 manifest |
| B04 | Modal app, pinned image, authentication, GPU class, persistent Volume, Secrets, and timeout are not yet configured | Environment inspection and user correction on 2026-08-25 | No training job can be submitted reproducibly until the remote contract exists | Create and verify `modal_app.py`, pin the image and Modal dependency, authenticate the workspace, and capture the remote environment probe before Phase 1 |
| B05 | Local PyTorch is CPU-only and the visible GPU is an NVIDIA GeForce MX130 with 2,048 MiB | Local environment inspection on 2026-08-25 | It is at least 22 GiB below the documented 24 GiB extraction minimum: $(24-2)/24=91.7\%$ shortfall (derived), and the user prohibits local training | Never train or extract retriever scores locally; submit those jobs to Modal and persist artifacts to the approved Modal Volume |
| B06 | ViDoSeek and ViMDoc revisions and licenses are not recorded | Proposal dataset sequence | Discovery/confirmation splits cannot be made reproducible | Record dataset identifiers, revisions, licenses, file counts, split hashes, and qrels checksums before Phase 1 |
| B07 | CARF clustering protocol is described conceptually but not present in the inspected code | Proposal versus baseline code | CARF results would otherwise require an invented clustering definition | Before CARF implementation, approve $K=3$, sensitivity $K\in\{2,4\}$, feature space, seed 20260820, and the rule that qrels never enter clustering |

There is no mathematical inconsistency in the QPAF scoring equations. At the 2026-08-25 snapshot, the feasibility verdict was **GO-WITH-CONDITIONS** and reportable implementation was blocked by B01–B07. This table is historical; use `Tasks.md` and the later dated evidence in this file for current gate status.

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
| $U$ | positive integer, $U\le C$ | Padded evaluation-unit count: pages normally, HEAVEN documents for ViMDoc |
| $E$ | $[B,U]$, bool | Valid evaluation-unit mask |
| $G$ | $[B,C]$, int64 | Page-to-evaluation-unit group index; identity for page evaluation |
| $R^E$ | $[B,U]$, float32 | Evaluation-unit relevance, used only in training/evaluation |
| $Z$ | $[B,C,M]$, float32 | Gate logits |
| $W$ | $[B,C,M]$, float32 | Non-negative channel weights summing to one |
| $S$ | $[B,C]$, float32 | Fused candidate scores |
| $T$ | $[B,U]$, float32 | Evaluation-unit scores; page scores normally, max-over-page document scores for ViMDoc |
| $Y$ | $[B,U]$, float32 | Normalized relevance-gain target distribution |
| $P$ | $[B,U]$, float32 | Predicted evaluation-unit distribution |
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

For page-level datasets, evaluation units are pages and $T_{bu}=S_{bu}$. For ViMDoc, apply the official HEAVEN mapping $d(p)$ that removes the final underscore-delimited segment, then aggregate pages to documents:

$$
G_{bi}=u\iff d(p_{bi})=d_u, \qquad
T_{bu}=\max_{i:A_{bi}=1,\,G_{bi}=u}S_{bi}. \tag{6a}
$$

The max uses ascending page ID to select the gradient recipient when scores tie. It is differentiable except at ties; the accepted deterministic subgradient is

$$
\frac{\partial T_{bu}}{\partial S_{bi}}=
\mathbf{1}\!\left[i=\operatorname*{argmax}^{\text{stable}}_{j:G_{bj}=u}S_{bj}\right]. \tag{6b}
$$

Padded positions are excluded by $A$ and $E$ from every reduction. Initialize $\Theta=0$ and $b=0$ so Eq. 5 gives exactly $(1/3,1/3,1/3)$ at step 0.

### 2.5 Training loss and backward derivation

For each query containing at least one positive candidate, define relevance-gain targets and the predicted listwise distribution:

$$
Y_{bu}=\frac{E_{bu}(2^{R^E_{bu}}-1)}{\sum_v E_{bv}(2^{R^E_{bv}}-1)}, \tag{7}
$$

$$
P_{bu}=\frac{E_{bu}\exp(T_{bu}/\tau)}{\sum_v E_{bv}\exp(T_{bv}/\tau)}, \tag{8}
$$

$$
\mathcal{L}=-\frac{1}{B}\sum_{b=1}^{B}\sum_{u=1}^{U}Y_{bu}\log P_{bu}. \tag{9}
$$

Implementation must use masked `log_softmax` in fp32 rather than exponentiating Eq. 8 directly. For valid page candidates,

$$
\frac{\partial\mathcal{L}}{\partial S_{bi}}=
\sum_{u=1}^{U}\frac{P_{bu}-Y_{bu}}{B\tau}
\frac{\partial T_{bu}}{\partial S_{bi}}
\equiv D_{bi}. \tag{10}
$$

Since $S_{bi}=W_{bi}^{\top}X_{bi}$ and $W_{bi}=\operatorname{softmax}(Z_{bi})$,

$$
\frac{\partial\mathcal{L}}{\partial Z_{bik}}=
D_{bi}W_{bik}\left(X_{bik}-S_{bi}\right). \tag{11}
$$

For the linear gate,

$$
\frac{\partial\mathcal{L}}{\partial\Theta}
=\sum_{b,i}\frac{\partial\mathcal{L}}{\partial Z_{bi}}H_{bi}^{\top},
\qquad
\frac{\partial\mathcal{L}}{\partial b}
=\sum_{b,i}\frac{\partial\mathcal{L}}{\partial Z_{bi}}. \tag{12}
$$

At zero initialization, $W_{bim}=1/3$ (derived). With uniform evaluation-unit predictions the initial per-query loss is $\log U_b$; the page-level upper bound $U_b=C_b=600$ gives $\log 600=6.397$ (derived), while ViMDoc uses its document count in the candidate union. The gate gradient is bounded by the normalized score range and is clipped to global norm $1.0$ as a guard. A constant score vector produces zero gate gradient via $X_{bik}-S_{bi}=0$; this is a detectable degenerate batch, not a numerical error.

### 2.6 QARF, CARF, and oracle roles

QARF uses query-pooled features $\bar H_b=\sum_iA_{bi}H_{bi}/\sum_iA_{bi}$ in Eq. 4 and broadcasts one $W_b$ to every candidate. CARF uses a fixed, label-free cluster assignment $K_{bi}\in\{0,\ldots,k-1\}$, pools features by cluster, and broadcasts one weight vector per cluster. Clustering is outside the gradient path. QPAF uses Eq. 4 independently at every valid page.

Oracle Global/QARF/CARF/QPAF searches only the preregistered $W_7$ and, after the gate, $W_{66}$. Oracle uses qrels to choose profiles and is never called a deployable model. Learned methods never receive oracle profiles or qrels as inference features.

### 2.7 Complexity

Feature construction is $O(BCM\log C)$ if ranks use sorting; gating and fusion are $O(BCFM)$; HEAVEN document grouping and max aggregation add $O(BC)$. The linear gate has $MF+M=3\cdot13+3=42$ parameters (derived). At $B=32,C=600,F=13,M=3$, the core forward tensors $H,Z,W,S$ contain

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
| `HEAVENDocumentAggregator` | Map ViMDoc pages by removing the final underscore segment and take deterministic max page score per document | $S[B,C]$, page IDs → $T[B,U],G[B,C],E[B,U]$ | None | N/A | 6a–6b |
| `ListwiseRankLoss` | Train on relevance at the declared evaluation unit | $T,R^E,E$ → scalar loss | None | N/A | 7–12 |
| `RankingEvaluator` | Deterministic ranking with evaluation-unit ID tie-break | $T,R^E,E$ → metrics | None | N/A | Metric protocol below |

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
                              |
         HEAVENDocumentAggregator Eq. 6a-6b for ViMDoc;
         identity mapping for page-level datasets
                              |
                              v
                    T [B,U] f32 device
                       /              \
                      / train          \ eval
                     v                  v
       ListwiseRankLoss Eq. 7-12    RankingEvaluator
       R^E [B,U] + E [B,U]         nDCG@10, R@1, R@3, MRR@10
```

## 5. Tensor Shape Contract

| Name | Shape | Dtype | Device | Constraint |
|---|---:|---|---|---|
| `raw_scores` | $[B,C,3]$ | float64 | CPU | finite on valid positions; channel order BM25, dense, visual |
| `scores` / $X$ | $[B,C,3]$ | float32 | CPU or CUDA | valid values in $[0,1]$ within $10^{-6}$ |
| `features` / $H$ | $[B,C,13]$ | float32 | same as $X$ | finite; label-free; padded rows zero |
| `valid_mask` / $A$ | $[B,C]$ | bool | same as $X$ | at least two valid candidates per query |
| `evaluation_group` / $G$ | $[B,C]$ | int64 | same as $X$ | page-to-document group for ViMDoc; identity for page evaluation; $-1$ on padding |
| `evaluation_mask` / $E$ | $[B,U]$ | bool | same as $X$ | at least two valid evaluation units per query |
| `evaluation_relevance` / $R^E$ | $[B,U]$ | float32 | same as $X$ | non-negative; at least one positive per training query |
| `logits` / $Z$ | $[B,C,3]$ | float32 | same as $X$ | finite on valid rows |
| `weights` / $W$ | $[B,C,3]$ | float32 | same as $X$ | each valid row in $[0,1]$; row sum $1\pm10^{-6}$ |
| `fused_scores` / $S$ | $[B,C]$ | float32 | same as $X$ | finite on valid positions; padded positions masked |
| `evaluation_scores` / $T$ | $[B,U]$ | float32 | same as $X$ | finite; ViMDoc value equals max score among pages in its document group |
| `target_distribution` / $Y$ | $[B,U]$ | float32 | same as $X$ | valid row sum $1\pm10^{-6}$ |
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
| ViMDoc document aggregation | Remove only the final underscore segment; stable max with ascending page-ID tie-break | Every qrels document maps to at least one page; repeated aggregation is byte-identical |

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

The approved default Modal Function uses a pinned `modal.Image`, `gpu="L4"`, an explicit timeout, one persistent Volume for score caches/checkpoints/run artifacts, and Secrets only for credentials. The full ViDoSeek Function uses L4 under its measured, user-approved dataset-specific contract and a ViDoSeek-only 86,400-second timeout; the generic ViDoRe full extractor remains on `A100-40GB` with its existing timeout. Modal source must be added from the versioned repository; a run manifest records the Modal package version, image definition hash, Function name, App/run identifier, requested and actual GPU, VRAM in decimal GB and binary GiB, driver, CUDA, PyTorch, Volume name, command, commit, config hash, and data hashes.

Hard learned-fusion cap: `torch.cuda.max_memory_allocated() < 1.50 GiB` on Modal. Exceeding it halts the run; batch size must not be silently changed. The 2026-08-25 Modal probe measured 22.034 GiB on the allocated L4. Against that capacity, the estimated $1.26$ GiB fusion footprint leaves $(22.034-1.26)/22.034=94.28\%$ headroom (derived from measured capacity and estimated footprint). This is not a measured training peak and must be replaced by telemetry after the first remote smoke job.

Offline BGE-M3/ColQwen2.5 score extraction has a frozen `23.5` decimal-GB preflight guard in the implementation (an operational threshold, not a model peak). The 2 GiB local GPU is not eligible. The 2026-08-25 Modal probe measured the L4 at 23.659 decimal GB (22.034 GiB), so it passes that guard by 0.159 decimal GB; comparing 22.034 GiB directly with the decimal-GB threshold was unit-inconsistent. The 2026-08-29 ViDoSeek calibration then measured a 7.720 GiB maximum allocation with unchanged models and batches. Based on that evidence, the user approved L4 for full ViDoSeek extraction on 2026-08-29; the generic ViDoRe full extractor remains on `A100-40GB`. Do not weaken the guard or change batch size silently. Exact allocated GPU/VRAM, PyTorch, CUDA, driver, model revisions, Modal image definition, and measured peak must be written to the run manifest before Phase 1.

The later post-hoc P1-02R all-corpus pool is a distinct 6,149,670-pair workload, so it did not inherit the 2026-08-29 full-extraction approval. Its bounded 8-query x 512-page calibration completed on an NVIDIA L4 in 588.160496293 seconds with 8,288,322,048 bytes (7.719 GiB) peak allocation. The componentwise projection is 7,860.383886004963 seconds (2.183439968334712 L4-hours), but excludes queueing, retries/OOM backoff, frozen-score-cache regeneration, output materialization, and price changes; it is review input, not a full result or monetary estimate. The P1-02R path caps query/page chunks at 8/512, atomically persists resumable embeddings and visual-score chunks, and streams final Parquet row groups. On 2026-08-30 the user approved exactly one human-run invocation of `extract-vidoseek-p1-02r-scores` on L4 at those limits. Function call `fc-01M19RE4SXMJ54M15049QSMXKA` completed under source commit `c7d84aaee0e9caab691a11bba377f4a87c6e059c`; the imported four-artifact bundle then passed local byte/content-hash, schema, row/key, normalization/rank, coverage, and provenance checks for all 6,149,670 rows per score table. The measured runtime was 7,818.803704091 seconds on NVIDIA L4, coverage was 1.0 with zero uncovered queries, and `full_score` was intentionally absent. This consumes the one approved invocation and closes the execution guard in the current checkout. The bundle is a verified post-hoc recovery score artifact, not an oracle, learned, HEAVEN, or deployable QPAF result; frozen P1-02 remains `BLOCKED`, and P1-03 remains blocked pending an explicit task-graph decision.

On 2026-09-01 the user approved creating and committing only a separately versioned P1-02R post-hoc W7 oracle/task-graph protocol and its tests. `configs/vidoseek_p1_02r_oracle_w7_v1.yaml` pins the verified retrieval-score and evidence hashes, current W7/source semantics, metrics, query-bootstrap settings, planned immutable outputs, and review gates. That preregistration recorded no oracle result and authorized no local oracle, output write, Modal/GPU work, P1-03, learned QPAF, or frozen P1-02 relabel. At that checkpoint, all-corpus oracle runtime was unmeasured and the protocol-bound preflight/immutable manifest support was not yet implemented.

The user then approved local preparation and commit of P1-02R-O1 pre-execution safeguards only. `src/oracle_study/vidoseek_p1_02r_oracle.py` now provides a hash/schema/evidence-bound read-only preflight, an atomic create-once engineering run-manifest writer that rejects oracle-result fields, and a separately guarded CPU timing entry point. The proposed non-result probe fixes three systematic queries, page ladders 128/256/512, one repetition, 100 bootstrap resamples, synthetic relevance only, one sequential worker with one CPU thread, a 120-second child-process limit per case, and a 300-second total ladder limit with no automatic retry. Preparation does not authorize that command: all probe/oracle/output-write/Modal/GPU/P1-03/learned-QPAF flags remain false, no probe or oracle result exists, full W7 remains unready, P1-02 stays `BLOCKED`, and a separate human approval/provenance patch is the next gate.

On 2026-09-02 the user approved preparing and committing the execution guard/provenance for exactly one human-run bounded CPU performance probe from safeguard commit `024f2f0a0998f0c781ac738d259603c6bbf29ba9`, while explicitly forbidding Codex execution, W7 oracle analysis, Modal/GPU, P1-03, and P1-02 relabeling. The runnable checkout must be one clean, non-merge direct-child approval commit with the exact seven-file changed-path allowlist. Only the probe-specific execution and engineering-output guards are open. The future human-run command atomically creates `_ATTEMPTED.json` before input preflight, consuming the one authorization even on failure; a retry requires a new approval. No attempt marker, timing manifest, probe, or oracle result has yet been produced, and full W7 remains unready.

The human invoked that approved command on 2026-09-02, but CPython stopped during preinitialization before the project module loaded because the unquoted CMD form `set PYTHONUTF8=1 &&` stored `PYTHONUTF8` as `1 ` with a trailing space. The original authorization is consumed under its no-retry rule even though no `_ATTEMPTED.json`, input preflight, performance probe, manifest, or oracle result was produced. The user then separately approved one corrective replacement human invocation. Its operational command uses `set "NAME=value"` for every CMD assignment, keeps the same CPU/query/page/bootstrap/timeout limits, and is not a retry under the prior authorization. The replacement checkout must be one clean, non-merge direct child of failed approval commit `fd2f411214b4b47750ffe6488bb0b5b654b55f66` with the same exact seven-file allowlist. Codex still may not run the probe, W7 oracle, Modal/GPU, P1-03, learned QPAF, or relabel P1-02.

The human ran that corrective replacement from commit `aebeef11d5964b9c45ea56242f41ad4202aec95c`, and the bounded CPU performance probe passed. The immutable attempt marker is 908 bytes with SHA-256 `f394faa42c3ac324e4378bde332a01794848780248b86cda12ccf8bc7fc61ace`; the immutable engineering manifest is 2,894 bytes with SHA-256 `2b030610ad7f8fb261799aa1d972ae47ee86724ea536eb4f317e6c2d71704549`. Its three-query synthetic-relevance cases at 128, 256, and 512 pages completed in 0.6704216001089662, 3.7113504000008106, and 13.628036600071937 seconds. This consumes and closes the replacement authorization; no retry or probe output write remains authorized. Extrapolation to 1,142 queries by 5,385 pages gives a review-only single-worker range of 4.97–20.02 days, with a 10.68-day three-point power fit and a 9.15-day quadratic-log estimate, before full-bootstrap, I/O/materialization, checkpoint/process, contention, and thermal overheads. The current monolithic full W7 is therefore a resource `NO-GO`. The recommended next step is only a separately approved query-sharded/resumable CPU-wrapper preparation with exact-semantic equivalence tests; neither that preparation, a full-page calibration, W7 execution, Modal/GPU, P1-03/P1-03R, learned QPAF, nor frozen P1-02 relabeling is authorized by this recording.

On 2026-09-02 the user separately approved local preparation and commit of that query-sharded/resumable CPU wrapper, while continuing to forbid the full-page calibration, live W7/checkpoint/result writes, Modal/GPU, P1-03/P1-03R, learned QPAF, and frozen P1-02 relabeling. The prepared implementation keeps the frozen monolithic `src/oracle_study/qpaf.py` bytes unchanged. Its first pass streams the existing Parquet row groups in candidate-audit order and atomically stores hash-sealed metrics for all seven W7 profiles per query; only after all 1,142 query checkpoints validate does it freeze the single shared Global profile. Its second pass runs the unchanged query-local QARF/QPAF primitives and atomically stores one result checkpoint per query. Resume requires the exact run-plan identity, protocol/source/input/query hashes, canonical query order, and exact checkpoint inventories. An absent expected checkpoint is computed once in its canonical pass; invalid existing or unexpected state and any incomplete post-pass inventory fail closed without overwrite. Deterministic fixture tests require exact equality with monolithic W7 rows, summary/bootstrap, and subgroups, then verify byte-preserving complete resume, one-file partial resume in either phase, and fail-closed tamper handling. The next proposed step is still review-only: a separately approved single synthetic query at candidate-audit index 570 over all 5,385 pages, with one worker/thread, 100 resamples, a 2,700-second hard stop, and no retry. Its quoted CMD command is recorded but closed; no calibration attempt marker, calibration manifest, live checkpoint directory, or oracle result was created.

On 2026-09-04 the user approved a local-only P1-02R-O1 review-hardening patch. The recorded-state CLI preflight now accepts the existing performance-probe evidence only after validating its exact recorded hashes and boundaries. The future full-page calibration and full-W7 guards now require the live checkout to be a clean tracked, non-merge direct child of an explicitly approved parent commit with an exact changed-path allowlist; a 40-character claim alone is insufficient. Synthetic seven-page fixture tests exercise the calibration path through success, create-before-preflight consumption, failed preflight, timeout cleanup, immutable manifest output, and retry refusal. These are temporary test artifacts only: the protocol status and all execution/readiness flags remain unchanged, no live calibration/W7/Modal/GPU/P1-03/P1-03R/learned-QPAF work was run, and P1-02 remains `BLOCKED`.

On 2026-09-05 the user approved local preparation and commit of the guard/provenance amendment for exactly one human-run P1-02R-O1 full-page synthetic calibration from parent `9821d100a4d64d73e8772f48f68f30388f851c06`. The fixed contract is candidate-audit query index 570, all 5,385 pages, synthetic first-and-middle-page binary relevance, 100 resamples, one CPU worker/thread, a 2,700-second hard stop, and no retry. The approval commit must be the clean non-merge direct child of that parent and contain exactly the seven recorded paths. Only the calibration, its engineering-manifest write, and temporary checkpoint permissions are open; performance-probe, full-W7, general oracle/output, Modal/GPU, P1-03/P1-03R, and learned-QPAF permissions remain closed. This amendment did not run the calibration or create its attempt marker/manifest. The create-once marker will consume the sole human authorization before preflight; success or failure cannot automatically authorize a retry or full W7, and P1-02 remains `BLOCKED`.

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

At the original feasibility snapshot, no Git commit existed for the inspected baseline. Current repository and run provenance are recorded in `Tasks.md`, `experiments/CHANGELOG.md`, and the dated artifact manifests. The historical baseline code check was:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

The original baseline acceptance was exactly 29 passed, 0 failed, 0 errors before new tests were added. It reproduced software behavior only, not a published or completed experimental number.

### 8.2 Raw-score contract

One row per `(dataset, query_id, page_id)` must include finite `bm25_score`, `dense_score`, and `visual_score`, plus `source`, split, retriever revisions, and candidate provenance. Page-qrels datasets also carry non-negative page relevance. ViMDoc instead carries a deterministic `document_id` derived by removing the final underscore segment and joins relevance only after page scores are aggregated to documents; repeating document relevance onto pages is forbidden. HEAVEN-format imports used by the baseline cache builder also carry `stage1_score`, genuine `full_score`, `stage2_ms`, and `stage2_flops`; these HEAVEN fields are not QPAF input features. The P1-02R recovery bundle is a separate QPAF score contract and intentionally omits `full_score` and stage-2 cost fields, so it does not satisfy HEAVEN preflight. Duplicate keys are forbidden. The score file and evaluation-unit qrels receive SHA-256 hashes. Minimum relevant evaluation-unit coverage is $0.95$ before oracle or training.

### 8.3 Metrics

Primary metric is mean per-query nDCG@10 using gain $2^r-1$ and discount $1/\log_2(i+2)$. Secondary metrics are Recall@1, Recall@3, and MRR@10. Ranking sorts by descending score with ascending evaluation-unit ID as deterministic tie-break: page ID for page-qrels datasets and HEAVEN document ID for ViMDoc after max-over-page aggregation. Use `src/oracle_study/metrics.py`; do not substitute a library implementation without an equivalence test on hand-computed fixtures.

### 8.4 Dataset sequence

The active scope contains exactly three datasets: Discovery uses ViDoSeek, Confirmation uses a frozen 2,000-query ViMDoc development sample followed by full ViMDoc for the final HEAVEN-aligned comparison, and External validation uses sealed ViDoRe V3. The ViMDoc development sample is selected without labels: compute SHA-256 over the UTF-8 string `20260820:<query_id>`, sort by digest and then query ID, and take the first 2,000 unique query IDs. Sampling must not read `doc_ids`, qrels, relevance counts, document length, or retrieval scores. Modal materialization on 2026-08-25 found 362 unique raw ViMDoc `doc_ids` that do not resolve to exactly one extension-stripped page ID in revision `25657f1fe0358f49147148ca89e231291ba42788`; later scans measured 70,080 unique extension-stripped page stems from the card's 76,347 image assets and 1,247 HEAVEN evaluation groups versus the card's 1,379 source documents. Following human approval on 2026-08-26, ViMDoc confirmation is HEAVEN-aligned document-level retrieval: remove the final underscore segment from both archive page stems and raw ground-truth IDs, take the maximum fused page score per document with ascending page-ID tie handling, and apply loss and metrics to binary document qrels. The discrepancies remain recorded audit evidence; no ID is dropped and no page label is fabricated. Their identifiers, revisions, licenses, and split hashes are Phase 0 deliverables. MMDocIR and Vietnamese VQA datasets are future work, not executable study dependencies.

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

Latest execution evidence (2026-09-06): the one human P1-02R-O1 full-page synthetic CPU calibration completed and its imported evidence passed review in `artifacts/vidoseek_p1_02r_full_page_calibration_review.json`. Query index 570 over 5,385 pages took 752.7996488000001 seconds in the worker; all source/protocol/hash, resource-limit, and non-result checks passed. The attempt is consumed, with zero remaining; the executed YAML remains a historical approval snapshot and the immutable attempt marker in both checkouts enforces no retry. This is engineering evidence only. Full W7 remains unauthorized; `docs/QPAF_CALIBRATION_REVIEW_AND_NEXT_STEP.md` records the resource review and an unapproved 12-query exploratory proposal. P1-02/P1-03 and learned-method gates remain unchanged.

Exploratory-12 follow-up (2026-09-07): the separately approved one-time CPU pilot stopped with 12/12 Global checkpoints and 4/12 query results. The process is gone and no complete manifest exists. Read-only source/input/checkpoint and saved-ranking metric checks passed in `artifacts/vidoseek_exploratory12_interruption_review_20260907/checkpoint_integrity_review.json`; eight query searches and final comparison remain unfinished. The prior session hit its usage limit, but the experiment continued afterward and its later termination cause is unknown. No aggregate result or phase decision is available. The original run is preserved, zero invocations remain, and no recovery was launched. See `docs/QPAF_EXPLORATORY12_INTERRUPTION_HANDOFF.md`.

Recovery preparation (2026-09-07): a separate launcher/config and synthetic recovery tests are complete. Focused checks passed 24 tests; the full suite passed 182 tests. Read-only recovery preflight passed without relevance loading or oracle search. The original 43 run files, original oracle source, and original approval/config pins remain unchanged. The new recovery directory does not exist and its approval flags remain false. See `docs/QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md` for the one-invocation, one-worker/thread, additional six-hour recovery proposal. No manual file edits or commands are needed from the user; separate execution approval remains necessary.

Recovery closeout (2026-09-07): the separately approved recovery launched at 10:02 UTC and completed at 11:42:29 UTC, reusing four saved results and computing eight missing queries with one CPU worker/thread, within the additional six-hour cap and with no automatic retry. All twelve results passed independent review; the chart passed visual inspection. Mean nDCG@10 is Global 0.952556, QARF 0.958333, QPAF 1.000000 on this single-seed exploratory subset (seed 20260820). All gain is from query 797; the other eleven queries are at the Global ceiling. `docs/QPAF_QUERY797_CASE_STUDY.md` explains the saved two-page weight changes and independently reconstructs 144 metrics. `docs/QPAF_NEXT_EVALUATION_PROPOSAL.md` is review-only; full W7/W66, P1-03 and learned work remain closed. See `docs/QPAF_EXPLORATORY12_RESULTS.md` and the current recovery status. Earlier interruption and closed-preparation statements above are historical; both attempts remain consumed.

Fixed-profile discovery audit preparation (2026-09-07): a separate runner, closed config and synthetic tests are prepared following the exploratory-12 case review. Read-only preflight passed on the frozen score bundle; no full-discovery relevance values were loaded and no new retrieval metric or attempt was produced. `docs/QPAF_FIXED_PROFILE_AUDIT_EXECUTION_REVIEW.md` records the seven-profile Global/QARF audit, theoretical gain-bound interpretation and proposed 30-minute, one-worker/thread, one-invocation, no-retry contract. Execution remains closed; the existing frozen P1-02/P1-03 and learned-method gates remain unchanged.

Fixed-profile discovery audit closeout (2026-09-08): the separately approved one-time local CPU invocation completed in 561.485 seconds with all 1,142 queries and 6,149,670 query-page pairs. Independent raw-score reconstruction verified 1,171 artifact hashes, 1,142 checkpoint envelopes and 32,012 metric values. Global selected visual-only and reached mean nDCG@10 0.875138; QARF reached 0.908268. The mean theoretical `1 - QARF nDCG@10` bound is 0.091732, with 216 queries retaining positive headroom, so the audit advice is `HEADROOM_POSSIBLE_REVIEW_COMPUTE`. This bound is not measured QPAF gain and does not change the formal task graph. See `docs/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md`; further page-level search still requires a separate reviewed protocol and explicit execution approval.

Exploratory-24 preparation (2026-09-08): the bounded representative page-level feasibility protocol is frozen after the fixed-profile audit. It deterministically selects 24 additional queries from the 1,130-query remainder without using relevance, retrieval scores or fixed-audit per-query metrics; query-list SHA-256 is `95715b6a8c0c2d684b3a34e9130eca25ea641aafb62678f7daa764f0ab585f5b`. The separate runner reuses unchanged W7/Global/QARF/QPAF primitives over all 5,385 pages/query and preserves 10,000-resample bootstrap semantics. Nineteen focused tests and 232 full tests pass; read-only preflight passes and the closed CLI refuses before writes. The proposed 12-hour cap is a budget for one CPU worker/thread and zero retries, not an estimate or authorization. See `docs/QPAF_EXPLORATORY24_EXECUTION_REVIEW.md`; full W7/W66, formal gates, training, Modal/GPU and P1-02/P1-03 remain closed.

Exploratory-24 closeout (2026-09-08): the user approved the reviewed one-invocation contract, and the local CPU run completed all 24 frozen additional queries and 129,240 query-page pairs in 8,700.394 seconds with one worker/thread and no retry. Independent review verified 82 manifest artifacts, 50 checkpoint envelopes, 25 source snapshots, 960 raw ranking metrics and 415 aggregate comparisons. Mean nDCG@10 is Global 0.817634, QARF 0.853845 and QPAF 0.903856. QPAF-minus-QARF is 0.050011 with bootstrap CI95 [0.008344, 0.101921], win/tie/loss 5/19/0 and top-5% gain share 0.666315; six page assignments changed across five queries. This clears the exploratory W7 continuation signals but remains a subset oracle upper bound, not a formal Phase 1 or learned-model result. See `docs/QPAF_EXPLORATORY24_RESULTS.md`; W66, full W7, training, Modal/GPU, P1-03 and frozen P1-02 remain closed.

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
- Adding MMDocIR or Vietnamese VQA datasets to the active three-dataset study without a new approved scope change.
