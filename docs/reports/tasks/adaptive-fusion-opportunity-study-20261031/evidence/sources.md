# Primary-source evidence ledger

Checked 31/10/2026. Two focused research agents inspected literature and dataset documentation; the executor opened and cross-checked the key sources. No secondary summaries are used as evidence.

**V3 — [ViDoRe V3](https://arxiv.org/html/2601.08620v1)** (2026-01-13; §§3–4, App.B/E)

Ten corpora, eight public; query taxonomy, page qrels and six language versions. Visual models lead aggregate results. Hybrid generation context is not learned-fusion evidence.

Limit: Group translations; public releases are evaluation data. Multi-modality alone is not complementarity.

**V3I — [ViDoRe V3 Industrial author card](https://huggingface.co/datasets/vidore/vidore_v3_industrial)** (Dataset Statistics / Structure)

27 documents, 5,244 pages, 283 base queries; mean 1.8 relevant pages/query. Images, Markdown, document IDs, graded page qrels.

Limit: Test release; no native gate-training split. Corpus structure suggests a hypothesis, not measured QPAF gains.

**V3F — [ViDoRe V3 Finance EN author card](https://huggingface.co/datasets/vidore/vidore_v3_finance_en)** (Dataset Statistics / Structure)

Six bank reports, 2,942 pages, 309 base queries; mean 4.7 relevant pages/query.

Limit: Publisher document licenses differ from annotation license; local exposure must be audited.

**V3C — [ViDoRe V3 Computer Science author card](https://huggingface.co/datasets/vidore/vidore_v3_computer_science)** (Dataset Statistics / Structure)

Two textbooks, 1,360 pages, 215 base queries; mean 4.6 relevant pages/query.

Limit: Only two source books: weak standalone document-generalization split.

**MM — [MMDocIR paper](https://arxiv.org/html/2501.08828v3)** (2025-11-07 v3; §§2–5, App.G)

Body/release reports 1,658 evaluation questions and 73,843 training questions/6,878 documents. Known-document page retrieval uses Recall@k; visual baselines remain strong.

Limit: Abstract/conclusion retain inconsistent older counts; new annotations have research/noncommercial conditions.

**MMC — [MMDocIR evaluation author release](https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset)** (Evaluation Set Overview / Pages)

313 documents, 20,395 page screenshots, 1,658 questions; OCR/VLM text and page/layout evidence annotations.

Limit: Hub loader named train is not a valid research training split; metadata license conflicts with more restrictive paper/repo statements.

**MMCODE — [MMDocIR official code](https://github.com/MMDocRAG/MMDocIR)** (README; encode.py; metric_eval.py)

Encoding/evaluation restricts candidate ranges by known source document; domain macro and question-average recall are distinct.

Limit: Global pooled search or layout-to-page conversion is a protocol extension.

**UNI — [UniDoc-Bench paper](https://arxiv.org/html/2510.03663v2)** (2025-10-09 v2; §4/App.E Table7)

Recall@10 reverses by evidence type: text-required text .821 vs image .774; image-required text .751 vs image .922.

Limit: OpenAI text embedding versus ColQwen, not this project's retrievers. Evidence-chunk/page-overlap metric differs from page nDCG.

**UNIREPO — [UniDoc-Bench official repository](https://github.com/SalesforceAIResearch/UniDoc-Bench)** (Data Preparation / License / Usage Notice)

70k pages, eight domains, 1,600 synthetic QA pairs; source paper reports 20% human validation.

Limit: CC-BY-NC and an explicit model-use notice; inspect actual intended use and artifact availability before adoption.

**REAL — [REAL-MM-RAG paper](https://arxiv.org/html/2502.12342v1)** (2025-02-17; §§3–5)

Finance/technical report and slide corpora; controlled rephrasings vary lexical match while retaining semantics. Baselines include BM25/BGE-M3 OCR.

Limit: Mostly single verified relevant page and visual dominance: more direct QARF diagnostic than QPAF proof. Group paraphrases.

**MFAR — [Multi-Field Adaptive Retrieval](https://arxiv.org/html/2410.20056)** (ICLR2025; §2.2, §5.1 Table2)

Query-conditioned field/scorer weights; query conditioning ablation improves mean MRR .456 to .545.

Limit: Encoder fine-tuning and structured fields differ from frozen score fusion; no candidate-conditioned claim.

**DAT — [Dynamic Alpha Tuning](https://arxiv.org/html/2503.23013v1)** (2025-03-29; §§4–5)

An LLM judges two top-ranked results to compute one alpha per query.

Limit: Small paragraph-retrieval setting and online LLM cost; does not show page-level weighting is needed.

**BRUCH — [An Analysis of Fusion Functions for Hybrid Retrieval](https://arxiv.org/html/2210.11934)** (TOIS42(1); §5 Table2, §6)

Tuned global convex fusion is a strong, sample-efficient baseline and can beat default RRF across the evaluated datasets.

Limit: Not a universal dominance theorem; normalization and static tuning budget must be controlled.

**GQR — [Guided Query Refinement](https://arxiv.org/html/2510.05038v3)** (ICLR2026; 2026-04-06 v3; Table3)

ViDoRe2: tuned min-max fusion +3.4% relative mean nDCG@5 over primary versus untuned RRF -2.8%.

Limit: GQR modifies query embeddings; its gains are not QPAF convex-score-fusion results. Percentages are relative, not absolute points.

**MIDR — [MIDR: Enrichment-Augmented Indexing](https://arxiv.org/html/2609.01316v1)** (2026-09-01; App.L/M Tables24–25)

On 1,489 English queries, enriched-text MIDR and reproduced ColQwen2.5 win decisively on 351 and 362 queries. Per-query selector reaches .7042 versus visual .6300.

Limit: Label-using selector; MIDR changes text representation with offline MLLM enrichment. Not evidence for the current OCR channel or learned page routing.

**DRAG — [DRAG / LckBorda](https://www.mdpi.com/2079-9292/15/4/843)** (2026-02-16; §3.3)

Uses page chart/image area for visual/text weights; overlap-first and weighted Borda on remaining pages.

Limit: Closest checked heuristic page-aware precedent. Publisher indexed text verified mechanism; direct fetch returned429, so no numerical fusion-ablation claim is used.

**MULTI — [DocRetriever / MultiDocR](https://arxiv.org/html/2605.30027v1)** (KDD2026; §§3.4,5)

Extends MMDocIR's 313 documents to 2,581 questions with graded relevance and cross-page/cross-modal annotations; a fixed .8 dense weight is a strong control.

Limit: Reused source documents/derived queries mean MMDocIR and MultiDocR are not independent confirmations.

**VIDORAG — [ViDoRAG](https://arxiv.org/html/2502.18017)** (2025-06-03 v2; §5.1)

GMM chooses retrieval depth separately per modality, followed by union and original page order.

Limit: Adaptive retrieval depth is not a query/page relevance-score weighting mechanism.

**UNVEIL — [Unveil](https://aclanthology.org/2025.acl-long.1166.pdf)** (ACL2025; §2.2 Eqs8–9)

Adaptive reweighting applies to distillation training samples.

Limit: Do not describe its training-loss ablation as inference-time page-fusion evidence.

**INTERVAL — [Optimal Fusion Weights Form Intervals, Not Points](https://arxiv.org/html/2610.24341)** (2026-10-17 preprint; §§3–5)

Optimal query-level WRRF weights can occupy intervals; ranking utility need not identify one unique target weight.

Limit: Recent preprint; its mean-optimal-weight comparator is not equivalent to optimizing aggregate static utility, and it does not establish QPAF.

**LIMITS — [Evidence-Unit Fairness and Limits of Query-Adaptive Fusion](https://arxiv.org/html/2608.00183)** (2026-09-11 v2; §§IV–V)

Financial retrieval has oracle headroom but tested lightweight routers do not establish a reliable gain under grouped evaluation.

Limit: Recent study with a compact encoder and evidence mapping limits; fixed blend comparator does not settle every strong-static case.
