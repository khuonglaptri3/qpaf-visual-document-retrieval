# Comprehensive Review and Technical Summary: Query-Page-Adaptive Fusion (QPAF)

This document provides a comprehensive review and architectural synthesis of the research project **Adaptive Retrieval Fusion for Visually Rich Document RAG** ([`DE_XUAT_NGHIEN_CUU_QPAF.md`](../../DE_XUAT_NGHIEN_CUU_QPAF.md), [`PROJECT_OVERVIEW.md`](../../PROJECT_OVERVIEW.md), [`Context.md`](../../Context.md)). It details the exact problem statement, the mathematical framework, the experimental lifecycle, current state and blockers, and the complete spectrum of knowledge required to solve it thoroughly.

---

## 1. Executive Summary & Project Orientation

### 1.1 Project Identity & Core Thesis
* **Title:** Adaptive Retrieval Fusion for Visually Rich Document RAG (Vietnamese: *Dung hợp truy xuất thích ứng cho hệ thống RAG trên tài liệu giàu thông tin trực quan*).
* **Core Proposal:** When retrieving evidence pages from visually complex documents (e.g., financial statements, technical reports, presentation decks, infographics) for Visual Retrieval-Augmented Generation (Visual RAG), relevant evidence can manifest through exact keywords, semantic paraphrases, or visual elements (tables, charts, layout). 
* **Primary Innovation:** **Query-Page-Adaptive Fusion (QPAF)** introduces a lightweight reranking layer that dynamically predicts convex combination weights over three frozen retrieval channels for every candidate page conditioned on query-page interactions:
  1. Lexical matching: **BM25** on extracted text/OCR.
  2. Dense-text semantic matching: **BGE-M3**.
  3. Vision-language page retrieval: **ColQwen2.5** (late-interaction visual retriever).

### 1.2 The Methodological Hierarchy
The project establishes a hierarchy of fusion granularities to test the limits of adaptation:
$$\text{Single Channel} \longrightarrow \text{Global Fixed Fusion } (w_m) \longrightarrow \text{QARF } (w_m(q)) \longrightarrow \text{CARF } (w_m(q, c)) \longrightarrow \text{QPAF } (w_m(q, p))$$

```
   +-----------------------------------------------------------------------------------+
   |                             FUSION GRANULARITIES                                  |
   +-----------------------------------------------------------------------------------+
   |  Level       | Weight Notation  | Description                                     |
   |--------------|------------------|-------------------------------------------------|
   |  Global      | w_m              | 1 static weight vector across the entire corpus |
   |  QARF        | w_m(q)           | 1 weight vector per query                       |
   |  CARF        | w_m(q, c)        | 1 weight vector per candidate cluster c         |
   |  QPAF        | w_m(q, p)        | 1 weight vector per (query, page) pair          |
   +-----------------------------------------------------------------------------------+
```

### 1.3 Strict Scientific Discipline & Pre-registration
Unlike typical empirical deep learning projects that jump directly to training neural networks, this project enforces **falsifiability and pre-registration**:
* **Diagnostic Oracle First:** Before training any model, an exhaustive oracle search over a simplex grid of weights ($W_7$ and $W_{66}$) is run using relevance judgments (qrels) to measure the **theoretical maximum headroom**.
* **Hard Phase Gates:** If QPAF oracle fails to beat QARF oracle by at least $\mathbf{0.03\ \text{nDCG@10}}$ with a $95\%$ bootstrap confidence interval strictly above $0$ on discovery data, or if gains are concentrated in $<5\%$ of queries, **the project halts or reverts to simpler fusion (QARF/Global)**.
* **Separation of Concerns:** 
  * *Oracle $\ne$ Deployable Model:* Oracle uses qrels to measure diagnostic upper bounds.
  * *Learned Model:* Must predict weights using only **13 label-free features** at inference time without accessing ground truth.

---

## 2. The Exact Problem Statement

### 2.1 The Retrieval Challenge in Visual RAG
Downstream Large Multimodal Models (LMMs) require accurate context pages to answer queries about complex documents. In visually rich PDF collections:
1. **Heterogeneous Evidence Signals:** A financial query regarding net revenue may require exact keyword matching on numbers (**BM25**), while a thematic query requires semantic abstraction (**BGE-M3**), and a query about trends in an infographic requires structural and visual reasoning (**ColQwen2.5**).
2. **Channel Failure Modes:** Single retrievers exhibit orthogonal failure modes. A visual retriever may miss dense textual footnotes; dense text embeddings often suffer from numerical hallucination or loss of exact alphanumeric identifiers; BM25 fails completely on scanned diagrams or semantic paraphrasing.
3. **Intra-Query Candidate Divergence:** For a single query, candidate page $p_1$ might be a dense text page where lexical or semantic retrieval is reliable, while candidate page $p_2$ might be an infographic or balance sheet table where visual late-interaction is critical. Query-level adaptive fusion (QARF) enforces the same channel weights across all candidate pages for that query, potentially degrading performance on heterogeneous candidate sets.

### 2.2 Mathematical Formulation

Let $q \in \mathcal{Q}$ be a query, $\mathcal{P}$ be the document page corpus, and $\mathcal{M} = \{B, D, V\}$ represent the three frozen retriever channels:
* $s_B(q, p)$: BM25 lexical score
* $s_D(q, p)$: BGE-M3 dense-text score
* $s_V(q, p)$: ColQwen2.5 visual retrieval score

#### Candidate Set Construction (Label-Free)
To avoid scoring entire corpora with expensive late-interaction models, candidate pools are constructed via union of top-$K$ retrievers:
$$\mathcal{C}_q = \operatorname{Top}_{K}^{B}(q) \cup \operatorname{Top}_{K}^{D}(q) \cup \operatorname{Top}_{K}^{V}(q), \quad |\mathcal{C}_q| \le 3K$$

#### Score Normalization
Because score ranges and distributions vary dramatically across channels, per-query min-max normalization is applied over $\mathcal{C}_q$:
$$\hat{s}_m(q, p) = \begin{cases} 
\dfrac{s_m(q, p) - \min_{p' \in \mathcal{C}_q} s_m(q, p')}{\max_{p' \in \mathcal{C}_q} s_m(q, p') - \min_{p' \in \mathcal{C}_q} s_m(q, p')}, & \text{if } \text{range} > 10^{-15} \\
0, & \text{otherwise}
\end{cases}$$

#### Fusion Scoring Function
The final composite score $S(q, p)$ is a candidate-dependent convex combination:
$$S(q, p) = \sum_{m \in \{B, D, V\}} w_m(q, p) \cdot \hat{s}_m(q, p), \quad \text{subject to } w_m(q, p) \ge 0, \ \sum_{m} w_m(q, p) = 1$$

#### Deterministic Ranking & Primary Evaluation Metric
Candidates in $\mathcal{C}_q$ are ranked in descending order of $S(q, p)$, breaking ties deterministically by ascending alphanumeric `page_id`.
The primary optimization and evaluation metric is mean per-query Normalized Discounted Cumulative Gain at rank 10 (**nDCG@10**):
$$\text{DCG@10}(q) = \sum_{i=1}^{10} \frac{2^{r(q, p_{(i)})} - 1}{\log_2(i + 1)}, \quad \text{nDCG@10}(q) = \frac{\text{DCG@10}(q)}{\text{IDCG@10}(q)}$$
Secondary metrics: **Recall@1**, **Recall@3**, **MRR@10**.

### 2.3 The Core Research Questions (RQs)
1. **RQ1 (Complementarity):** Do the three retrieval channels exhibit sufficient orthogonality such that their candidate union $\mathcal{C}_q$ achieves significantly higher recall than any individual retriever?
2. **RQ2 (Query-Adaptive Headroom):** Does query-level weight adaptation ($w_m(q)$, QARF) yield substantial, statistically verified gains over global fixed weighting ($w_m$)?
3. **RQ3 (Page-Adaptive Headroom):** Does candidate-level adaptation ($w_m(q, p)$, QPAF) provide meaningful additional headroom over QARF across a broad distribution of queries rather than outlier artifacts?
4. **RQ4 (Learnability & Generalization):** Can a parameterized gating network learn to predict these adaptive weights using only label-free features, maintaining a positive validation gain ($\Delta \ge 0.01\ \text{nDCG@10}$) over the best deployable baseline without violating operational latency ($\le 10\text{ ms/query}$) and memory ($\le 1.50\text{ GiB}$) constraints?

---

## 3. System Architecture & Engineering Contracts

The project is architected with strict decoupling between offline heavy computation, caching, diagnostic analysis, and model training.

```mermaid
flowchart TD
    subgraph Data Layer
        D1["ViDoSeek (Discovery)<br/>1,142 queries, 5,385 pages"]
        D2["ViMDoc (Confirmation)<br/>10,904 queries, 70,080 pages"]
        D3["ViDoRe V3 Finance EN (External)<br/>309 queries, 2,942 pages"]
    end

    subgraph Tier 1: Heavy Extraction (Modal GPU)
        M1["BM25 (CPU Text / OCR)"]
        M2["BGE-M3 (Dense Embeddings)"]
        M3["ColQwen2.5 (Late-Interaction Visual)"]
        M4["DSE (Candidate Stage 1 Provenance)"]
        SC["Parquet Score Cache<br/>raw_scores.parquet"]
    end

    subgraph Tier 2: Integrity & Diagnostic Gates (Local / CPU)
        V1["ScoreCacheValidator<br/>Schema, Hash, Key, Nan/Inf"]
        V2["Coverage Gate<br/>Coverage >= 0.95 & Zero-Uncovered == 0"]
        V3["Oracle Simplex Search<br/>W7 (7 profiles) & W66 (66 profiles)"]
        V4["Bootstrap Analysis<br/>10,000 resamples, 95% CI"]
    end

    subgraph Tier 3: Learned Fusion Pipeline (Modal L4 / GPU)
        F1["13 Label-Free Features (H)"]
        G1["Linear Softmax Gate (42 params)<br/>Z = Theta * H + b"]
        L1["Masked Listwise Loss<br/>Targets: Y ~ 2^r - 1"]
        E1["Ranking Evaluator<br/>nDCG@10, R@1, R@3, MRR@10"]
    end

    D1 & D2 & D3 --> M1 & M2 & M3 & M4
    M1 & M2 & M3 & M4 --> SC
    SC --> V1 --> V2
    V2 -->|Pass Gate| V3 --> V4
    V4 -->|Delta >= 0.03 & CI > 0| F1
    F1 --> G1 --> L1 --> E1
```

### 3.1 Datasets and Evaluation Units
* **ViDoSeek ([Discovery]):** 1,142 queries, 292 PDFs, 5,385 prepared pages. Page-level binary qrels.
* **ViMDoc ([Confirmation]):** 10,904 queries, 76,347 page images (70,080 unique stems), 1,247 HEAVEN evaluation document groups. Evaluated on a deterministic 2,000-query dev sample using **max-over-page document aggregation**:
  $$T(q, d) = \max_{p \in d} S(q, p)$$
  Loss and metrics are computed on document-level relevance judgments.
* **ViDoRe V3 Finance EN ([External Sealed Validation]):** 309 queries, 2,942 pages. Graded relevance judgments. Used strictly as a sealed test bed.

### 3.2 The 13 Label-Free Features ($H \in \mathbb{R}^{13}$)
The learned gate consumes no query text or raw page embeddings (avoiding expensive encoders during fusion). It operates solely on 13 score/rank distribution metrics:
1. **Normalized scores ($3$):** $[\hat{s}_B, \hat{s}_D, \hat{s}_V]$
2. **Normalized candidate ranks ($3$):** $[\rho_B, \rho_D, \rho_V] \in [0, 1]$
3. **Median-relative score margins ($3$):** $\hat{s}_m(q, p) - \operatorname{median}_{p' \in \mathcal{C}_q} \hat{s}_m(q, p')$
4. **Top-1 / Top-2 score gaps ($3$):** $g_m(q) = \hat{s}_m(q, p_{(1)}) - \hat{s}_m(q, p_{(2)})$ broadcast to all candidates
5. **Rank disagreement ($1$):** $d(q, p) = \operatorname{std}_m(\rho_m(q, p))$

### 3.3 The Gating Model & Listwise Objective
* **Architecture:** Zero-initialized linear gate:
  $$Z_{bi} = \Theta H_{bi} + b, \quad \Theta \in \mathbb{R}^{3 \times 13}, \ b \in \mathbb{R}^3 \quad (42\text{ learnable parameters})$$
  Because $\Theta = 0$ and $b = 0$ at step 0, initial weights are identically equal: $W = [1/3, 1/3, 1/3]$.
* **Training Objective:** Masked Listwise Softmax Cross-Entropy:
  $$Y_{bu} = \frac{E_{bu}(2^{R_{bu}} - 1)}{\sum_v E_{bv}(2^{R_{bv}} - 1)}, \quad P_{bu} = \frac{E_{bu} \exp(T_{bu}/\tau)}{\sum_v E_{bv} \exp(T_{bv}/\tau)}$$
  $$\mathcal{L} = - \frac{1}{B} \sum_{b=1}^B \sum_{u=1}^U Y_{bu} \log P_{bu}$$

---

## 4. Current Project State & Diagnostic Blockers

The execution state is formally tracked in [`PROJECT_TRACKING.md`](../../PROJECT_TRACKING.md) and [`Tasks.md`](../../Tasks.md):

```
PHASE 0: Environment, Contracts, Baseline Bundle ----------> [PASS]
  * P0-01: Freeze baseline snapshot (29/29 tests pass)      [PASS]
  * P0-02: Modal environment probe & dataset manifests      [PASS]
  * P0-03: ViDoRe 3-channel score bundle validation         [PASS]

PHASE 1: Cheapest Disproof (Oracle Analysis) -------------> [BLOCKED / P1-02R PASS]
  * P1-01: Harden normalization & metric contracts          [PASS]
  * P1-02: ViDoSeek Top-K W7 Pilot                           [BLOCKED]
    -> Reason: Top-K union missed relevant page for 1 query (coverage 0.999124, but 1 uncovered)
  * P1-02R: Post-hoc All-Corpus Recovery Bundle              [PASS]
    -> 1,142 queries x 5,385 pages = 6,149,670 rows verified; coverage = 1.0; 0 uncovered
  * P1-02R-O1: Bounded CPU Probe & Sharded Wrapper           [IN PROGRESS / GUARDED]
    -> 3-case synthetic probe verified
    -> Single-threaded monolithic W7 estimated at ~5-20 days CPU (NO-GO for monolith)
    -> Two-pass query-sharded resumable wrapper implemented & verified against monolith
    -> Exactly ONE human-run full-page calibration authorized; full W7 execution blocked
  * P1-03: W66 Sensitivity & Granularity Decision           [BLOCKED on P1-02/P1-02R]

PHASE 2: Learned Gating Implementation -------------------> [BLOCKED]
PHASE 3: Multi-seed Benchmarking & Validation ------------> [BLOCKED]
```

### The P1-02 Blockage vs. P1-02R Recovery
1. **The P1-02 Block:** The frozen top-$K$ protocol specified candidate pool $\operatorname{Top}_{200}^D \cup \operatorname{Top}_{100}^B \cup \operatorname{Top}_{100}^V$, expanding once to $(300, 200, 200)$ if coverage $< 0.95$. Overall coverage reached $99.91\%$, but query `027dee01b7aced677eb5093c754ebad82a89015d_1` had $0$ relevant candidates in the pool. By pre-registered rule ("zero uncovered queries allowed"), P1-02 was declared **BLOCKED**. No results were faked or massaged.
2. **The P1-02R Recovery:** A post-hoc recovery protocol was approved that scores the **entire 5,385-page corpus for all 1,142 queries** ($6,149,670$ query-page pairs). Modal extraction completed on an NVIDIA L4 GPU in $7,818.8$ seconds. Local verification confirmed coverage $1.0$ and $0$ uncovered queries.
3. **The Current Computational Hurdle:** Running exhaustive W7 coordinate-ascent oracle across $6.15$ million pairs on a single CPU thread scales quadratically/logarithmically with candidates, taking an estimated **$5$ to $20$ days**. A two-pass query-sharded resumable wrapper ([`src/oracle_study/vidoseek_p1_02r_sharded.py`](../../src/oracle_study/vidoseek_p1_02r_sharded.py)) was developed to enable atomic per-query checkpointing. Currently, a single-query full-page synthetic calibration is authorized for human execution to measure real single-query latency before deciding on full W7 execution.

---

## 5. Comprehensive Knowledge Required to Solve the Problem Thoroughly

To drive this project from its current state through Phase 1 oracle decisions, Phase 2 learned gating, Phase 3 multi-seed benchmarking, and final research publication, deep interdisciplinary mastery across seven core domains is required.

```
+---------------------------------------------------------------------------------------------------+
|                        COMPREHENSIVE KNOWLEDGE MATRIX FOR QPAF                                     |
+---------------------------------------------------------------------------------------------------+
| 1. Multimodal Information Retrieval (IR) & Late-Interaction Vision-Language Models                |
| 2. Learning-to-Rank (LTR) & Differentiable Ranking Surrogates                                     |
| 3. Visual Document Understanding (VDU) & Layout-Aware Parsing                                     |
| 4. Experimental Metrology, Statistical Significance & Pre-Registration Science                    |
| 5. High-Performance Distributed Systems & Memory-Bounded Cloud Computing (Modal / PyTorch / CUDA) |
| 6. Algorithmic Optimization & Scalable Computational Complexity                                   |
| 7. Software Architecture, Cryptographic Provenance & Rigorous Testing Discipline                 |
+---------------------------------------------------------------------------------------------------+
```

---

### Domain 1: Multimodal Information Retrieval (IR) & Late-Interaction Vision Models
Solving this project requires foundational and cutting-edge understanding of information retrieval architectures:
* **Lexical vs. Dense vs. Multi-Vector Representations:**
  * *Lexical (BM25):* Exact term matching, inverted index mechanics, term frequency/inverse document frequency saturation ($k_1, b$ parameters). Crucial for tabular numbers, model codes, and named entities.
  * *Dense Semantic Embedding (BGE-M3):* Single-vector dot-product representations; capturing paraphrasing and high-level semantic intent while losing fine-grained spatial and lexical granularity.
  * *Late-Interaction Vision Retrievers (ColPali / ColQwen2.5):* Multi-vector patch-level embeddings matched against query tokens via the **MaxSim** operator:
    $$S_{\text{visual}}(q, p) = \sum_{i=1}^{|q|} \max_{j=1}^{|p|} \left( \mathbf{E}_{q, i} \cdot \mathbf{E}_{p, j}^\top \right)$$
    Understanding token pruning, patch resolution scaling, and why MaxSim requires substantial GPU memory ($O(|q| \times |p|)$ similarity tensors).
* **Fusion Theory & Reranking:**
  * Convex linear combination vs. Reciprocal Rank Fusion (RRF: $RRF(d) = \sum \frac{1}{60 + r_m(d)}$).
  * Why rank-based fusion (RRF) discards confidence margins and why score-based convex combinations retain margin information but require strict score normalization.
  * Multi-page aggregation semantics: understanding how page-level scores propagate to document-level rankings (e.g., in the HEAVEN benchmark on ViMDoc) via max-pooling vs. average pooling.

---

### Domain 2: Learning-to-Rank (LTR) & Optimization Theory
Building the deployable learned gate in Phase 2 requires deep familiarity with ranking loss functions and gradient dynamics:
* **Taxonomy of LTR Losses:**
  * *Pointwise:* Regressing relevance scores directly (ignores candidate competition).
  * *Pairwise (RankNet, LambdaMART):* Optimizing pairwise orderings (computationally expensive over large candidate pools $O(C^2)$).
  * *Listwise (ListNet, ListMLE, Softmax Cross-Entropy):* Treating the candidate ranking as a probability distribution over permutations or top-1 choices.
* **Listwise Cross-Entropy with DCG-Aligned Soft Targets:**
  * Derivation of the gradient through softmax gating (Eq. 10–12 in [`Context.md`](../../Context.md)):
    $$\frac{\partial \mathcal{L}}{\partial Z_{bik}} = D_{bi} W_{bik} (X_{bik} - S_{bi}), \quad \text{where } D_{bi} = \frac{P_{bu} - Y_{bu}}{B\tau} \cdot \frac{\partial T_{bu}}{\partial S_{bi}}$$
  * Understanding how soft targets $Y_{bu} \propto 2^{R_{bu}} - 1$ bias gradients toward highly relevant documents ($R=2, 3$) compared to binary relevance.
  * Temperature scaling ($\tau$): How lowering temperature sharpens probability distributions and increases sensitivity to top ranks, while higher temperature diffuses gradient signals.
* **Non-Differentiable Boundaries & Subgradients:**
  * Dealing with max-over-page document aggregation ($T_{bu} = \max_{p \in d} S_{bi}$): handling non-differentiable ties via stable subgradient assignment to the lowest lexicographical page ID.
  * Stop-gradient boundaries: Ensuring no gradients propagate into offline candidate selection, sorting, or min-max normalization.

---

### Domain 3: Visual Document Understanding (VDU) & Parsing
The underlying data consists of raw visual documents that introduce domain-specific artifacts:
* **PDF Materialization Pipelines:**
  * Poppler rendering utilities (`pdftoppm`) at standard resolutions (200 DPI) and font-aware text extractors (`pdftotext -layout`).
  * Recognizing the trade-offs between native PDF text extraction and Optical Character Recognition (OCR): OCR handles scanned imagery but introduces typographical errors, whereas native extraction preserves true strings but fails on rasterized text or complex table grids.
* **Document Layout & Spatial Modalities:**
  * How tables, charts, headers, and reading order affect retriever scores.
  * Why a page containing only a chart with no OCR text causes BM25 to yield a zero score, triggering edge cases in min-max normalization.

---

### Domain 4: Experimental Metrology & Statistical Significance
A major reason previous research produces irreproducible claims is methodological leakage and statistical malpractice. Solving QPAF requires:
* **Pre-Registration Principles:**
  * Pre-defining hypotheses, alpha thresholds ($\delta = 0.01$), candidate depths, and evaluation metrics before running experiments.
  * Strict adherence to **falsification**: Willingness to accept a `NO-GO` or `STOP` verdict when evidence shows page-level adaptation is unnecessary.
* **Non-Parametric Bootstrap Testing:**
  * Paired query-level bootstrapping (10,000 resamples): Calculating empirical confidence intervals for $\Delta \text{nDCG@10} = \text{nDCG}_{\text{QPAF}} - \text{nDCG}_{\text{baseline}}$.
  * Verifying that the lower bound of the $95\%$ CI is strictly positive ($CI_{\text{low}} > 0$).
* **Gain Concentration & Gini Metrics:**
  * Measuring whether overall mean gains are driven broadly across the corpus or heavily concentrated in a small fraction of queries (e.g., verifying that the top $5\%$ of queries do not account for $>90\%$ of total positive gain).
* **Information Leakage Prevention:**
  * Ensuring zero label contamination: Relevance judgments (qrels) must never be accessed by candidate union builders, normalization routines, feature extractors, clustering algorithms (CARF), or inference-time models.

---

### Domain 5: High-Performance Distributed Systems & Cloud Orchestration
The project operates under hard hardware and infrastructure boundaries:
* **Serverless GPU Orchestration via Modal:**
  * Structuring serverless workflows using pinned container images, explicit function timeouts, persistent networked volumes, and cryptographic environment probing.
  * Knowing when to deploy NVIDIA L4 (24GB VRAM) vs. NVIDIA A100 (40GB/80GB) based on memory profiling.
* **VRAM Allocation & GPU Memory Management:**
  * Managing PyTorch CUDA memory contexts, allocator fragmentation, and memory caching.
  * Enforcing hard memory ceilings: The project enforces a strict cap of **$\le 1.50\text{ GiB}$ peak CUDA memory** for learned fusion inference.
  * Handling large late-interaction tensor operations in batches to avoid OOM crashes during ColQwen2.5 scoring.
* **Streaming I/O & Host RAM Control:**
  * Preventing host RAM leaks across training epochs.
  * Utilizing Apache Parquet row-group streaming to iterate through millions of candidate rows without loading full multi-gigabyte matrices into system memory.

---

### Domain 6: Algorithmic Complexity & Optimization
Scaling candidate pools from top-$K$ unions ($C \approx 600$) to all-corpus pools ($C = 5,385$) fundamentally changes the computational complexity:
* **Coordinate Ascent & Simplex Search Complexity:**
  * Monolithic QPAF oracle performs coordinate ascent over candidate pages. For $Q$ queries, $C$ candidates, and $S$ coordinate sweeps, sorting and metric recalculation scale as $O(Q \cdot C \cdot S \cdot C \log C) = O(Q \cdot S \cdot C^2 \log C)$.
  * When $C$ increases from $600$ to $5,385$, computation scales by $(5385 / 600)^2 \approx 80.5\times$, turning a 30-minute run into a multi-week run.
* **Parallelization & Checkpoint State Machines:**
  * Designing multi-pass query-sharded architectures:
    * *Pass 1:* Map-reduce across queries to compute profile-level metric matrices and freeze the global optimal profile.
    * *Pass 2:* Independent query-local optimization for QARF and QPAF.
  * Designing fail-closed resumable state machines that validate run-plan IDs, self-hashes, and input hashes before reusing checkpoint files.

---

### Domain 7: Software Engineering, Cryptographic Provenance & MLOps
The project maintains software engineering standards:
* **Immutable Provenance:**
  * Tracking dataset files, code snapshots, configuration YAMLs, model weights, and outputs via **SHA-256 digests**.
  * Creating `_SUCCESS.json`, `_ATTEMPTED.json`, and run manifests to ensure every reported number can be traced back to an exact Git commit and hardware environment.
* **Defensive Numerical Programming:**
  * Numerical stability in PyTorch: Using `torch.log_softmax` over raw exponents to prevent numerical underflow/overflow.
  * Zero-range normalization handling ($10^{-15}$ tolerances).
  * Stable tie-breaking: Always coupling primary metric sorting with a secondary deterministic key (e.g., ascending string ID) to guarantee exact reproducibility across OS and hardware platforms.
* **Unit, Property, and Regression Testing:**
  * Hand-calculated metric reference fixtures tested to $10^{-12}$ tolerances.
  * Analytical gradient checks (`torch.autograd.gradcheck`) in float64 to verify exact match with analytical subgradients.

---

## 6. Strategic Roadmap to Project Completion

To take this project from its current blocked state to successful defense or publication, the following sequence of technical steps must be executed:

```mermaid
timeline
    title Execution Roadmap to Completion
    section Step 1 : Resolve Oracle Headroom
        Execute 1-query human calibration : Index 570, 5385 pages
        Decide on W7 execution strategy : Parallelized CPU vs. Modal worker pool
        Execute full W7 oracle & evaluate gate : Gain >= 0.03, CI > 0
    section Step 2 : Sensitivity & Granularity
        Execute W66 simplex sensitivity : 66 profiles
        Issue Phase 1 Granularity Decision : Proceed QPAF vs. Revise vs. Stop
    section Step 3 : Learned Fusion (Phase 2)
        Implement 13-feature extractor : features.py
        Implement Linear Gates & Loss : models.py, losses.py
        Train QARF & QPAF on Modal L4 : 3 seeds, gradcheck, memory profiling
    section Step 4 : Robustness & Packaging (Phase 3)
        Run confirmation benchmark : ViMDoc document aggregation
        Sealed external validation : ViDoRe V3 Finance EN
        Package reproducibility bundle : QPAF_REPRODUCIBILITY.zip
```

1. **Step 1: Execute Synthetic Calibration & Solve All-Corpus W7 Runtime**
   * Execute the authorized one-query synthetic calibration for candidate index 570 over all 5,385 pages.
   * Based on measured single-query latency, decide whether to run the sharded CPU wrapper locally across multiple cores or distribute the 143 row groups across a pool of parallel Modal CPU workers.
   * Complete the full P1-02R W7 oracle analysis and evaluate the Phase 1 gate ($\Delta \ge 0.03$).

2. **Step 2: W66 Simplex Sensitivity & Granularity Decision (P1-03)**
   * Run the 66-profile simplex search to determine if finer weight intervals alter the conclusions.
   * Evaluate gain concentration (verifying that the top 5% of queries do not dominate the gains).
   * Emit the machine-readable decision: `proceed_qpaf`, `revise`, or `stop`.

3. **Step 3: Implement & Train Learned Fusion Models (Phase 2)**
   * Implement [`features.py`](../../src/oracle_study/features.py) to build the 13 label-free features without accessing labels.
   * Implement [`models.py`](../../src/oracle_study/models.py) (Linear QARF and QPAF gates initialized to zero) and [`losses.py`](../../src/oracle_study/losses.py) (Masked Listwise Loss).
   * Verify gradients with `torch.autograd.gradcheck`.
   * Train learned QARF (baseline) and learned QPAF on Modal L4 using seeds `20260820`, `20260821`, and `20260822`.
   * Verify that learned QPAF achieves $\Delta \ge 0.01\ \text{nDCG@10}$ over QARF, latency $\le 10\text{ ms/query}$, and peak VRAM $< 1.50\text{ GiB}$.

4. **Step 4: Confirmation, Sealed Validation & Publication Packaging (Phase 3)**
   * Evaluate on the 2,000-query dev split of ViMDoc using max-over-page document aggregation.
   * Run ablations on individual channels (BM25 vs. Dense vs. Visual), feature subsets, and gate architectures (Linear vs. shallow MLP).
   * Execute sealed external validation on ViDoRe V3 Finance EN without modifying hyper-parameters.
   * Assemble the complete cryptographic reproducibility package (`QPAF_REPRODUCIBILITY.zip`) containing code, manifests, logs, and benchmark tables.

---

## 7. Conclusion

The **Query-Page-Adaptive Fusion (QPAF)** project is an exemplar of rigorous, falsifiable AI research. Rather than hastily training complex architectures, it systematically decomposes the problem into:
1. **Verifiable score contracts** across three complementary modalities (BM25, BGE-M3, ColQwen2.5).
2. **Oracle upper-bound diagnostics** that establish whether candidate-level adaptation is mathematically justified before writing a single line of model code.
3. **Strict operational guards** enforcing data isolation, deterministic tie-breaking, append-only provenance, and hard latency/memory budgets.

Thoroughly solving this project requires mastering multimodal information retrieval, learning-to-rank optimization, layout-aware PDF engineering, statistical hypothesis testing, and high-performance cloud systems engineering. The project's infrastructure, contracts, and safety rails are fully established; resolving the all-corpus oracle computational throughput is the immediate key to unlocking the learned fusion phase.
