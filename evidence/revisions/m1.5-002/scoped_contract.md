# Scoped implementation reconciliation — proposed successor

State: `DRAFT_RECONCILIATION_NOT_ADOPTED`; review and effective-version assignment pending. Paths below are relative to the repository root; exact inspected bytes appear in `source_hashes.csv`.

## Scope and dataset roles

| Scope | Contract / evidence classification | Evaluation and claim limit |
|---|---|---|
| Historical Oracle report | Original Word and source manifest in `results/m1.1/reference/`; historically accepted feasibility | Reproduction unverified; old W7/W66 results are not outputs of this implementation |
| Current M1.1 Oracle preset | `configs/m1.1/vidoseek.toml`; distinct ViDoSeek Oracle study | Binary **page** nDCG@10 and label-aware upper bounds; no deployable learned claim |
| Current M1.2 core preset | `configs/m1.2/core.toml`; `qpaf13_v1` | Synthetic software verification; local optimizer steps are not research training |
| Proposed learned primary | ViDoSeek primary dataset (A002 recorded approved); page-level evaluation proposed | Matched learned QARF/QPAF research contract requires owner adoption, independent review and run authorization |
| Future confirmation | ViMDoc confirmation/document-level scope proposed | Exact dataset version, split, model, candidate, metric and seed policy must be separately adopted before execution |

A001 records pairwise logistic loss approval; A002 records active ViDoSeek primary adoption and deterministic 70/15/15 query splitting. They do not automatically approve every feature, rank, model, candidate or metric change below. Legacy ViMDoc 1,600/400/8,904 and document nDCG policies remain historical scope references; this draft does not silently replace their bytes.

ViDoSeek source: `Qiuchen-Wang/ViDoSeek@e91a92ba5f38690696c7e66be5c5474b54c6e791`, annotation `vidoseek.json`, key `examples`, corpus `vidoseek_pdf_document.zip`. The reported 1,142 query count must be confirmed by an actual corpus audit. The split proposal retains seed `2026`, namespace `vidoseek_v1`, hash-order partition 70/15/15; counts for 1,142 inputs are 799/171/172 under Python `round` used by the implementation, **not** the 800/171/171 claimed in the old narrative. Exact persisted IDs and hashes are authoritative after validation. A count-allocation change requires an explicit decision and new split identity.

## Observed M1.1 preset

| Field | Exact current preset / implementation |
|---|---|
| Query selection | `count=0`: all queries; full corpus retained; selection seed `2026` |
| Execution seed | `2026` |
| BM25 | Lowercase Unicode `\w+` tokens; positive Robertson IDF; `k1=1.5`, `b=0.75` |
| Dense | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`; normalized embeddings, dot product; max sequence length 8192; empty query/page prefix; batch 4 |
| Visual adapter / processor | `vidore/colqwen2-v1.0@2b6ac8fb37f46a49e4841e599583d00ae8a20117` |
| Visual base | `vidore/colqwen2-base@9fe8a713422a7cb4ef79ca77a09b381ee2243101`; frozen; bfloat16, SDPA, max pixels 602112; query prefix `Query: ` |
| Candidates | Rank each channel descending raw score, ties ascending page ID; top **100** each; sorted union at most 300; qrels do not construct the union |
| Scores | Three finite scores for every full-corpus page; missing IDs/shape/hash/nonfinite cache rejected; no imputation |
| Arithmetic | Oracle converts raw scores to NumPy float64; per-query/per-channel min-max over union; **exact zero range** maps to zeros; any nonzero range is divided |
| Ranking | Descending score, ascending page ID for equal scores; profile ties select first configured profile |
| Metric | Binary page nDCG@10; IDCG counts all relevant corpus pages, including relevant pages outside candidates |
| Statistics | 10,000 paired query-bootstrap resamples, seed `2026`; CI95 percentile with linear interpolation; W/T/L tolerance `1e-12` |

The W7 set is the three simplex vertices, equal thirds, and the three equal half/half edges. W66 is the simplex grid with divisions 10. Global chooses one profile by mean nDCG across evaluated queries; QARF chooses the best profile per query; QPAF chooses per-page profile maxima for positives and minima for negatives. This is an exact binary independent-page upper bound. Because both sets contain all three vertices, current QPAF optima match for the same inputs. The historical report has different QPAF values across W7/W66; solver/config equivalence is unverified. Label-aware profile selection cannot be described as a deployable retrieval model or held-out learned evaluation.

## Exact M1.2 feature and loss contract

Source: `src/qpaf/m12/features.py`, `model.py`, `losses.py`, `config.py`; preset `configs/m1.2/core.toml`.

Input: float32 or float64 `[batch, candidates, 3]` raw scores in channel order BM25/dense/visual, query text, page IDs, and boolean active-candidate mask. Every query needs an active candidate; active scores must be finite and active page IDs unique/nonempty. Frozen raw inputs are detached. Inactive feature values are zeros; labels are not feature-builder inputs.

| Index | Feature | Exact value |
|---|---|---|
| 1–3 | `score_bm25`, `score_dense`, `score_visual` | Per-query/per-channel min-max over active candidates; denominator replaced with 1 **only if span == 0** |
| 4–6 | `rr_bm25`, `rr_dense`, `rr_visual` | Reciprocal one-based rank **1/rank**; raw score descending, ascending page ID ties |
| 7–9 | `gap_bm25`, `gap_dense`, `gap_visual` | Top normalized score minus second normalized score, repeated on every active page; singleton gap 0 |
| 10–12 | `disagreement_bm25_dense`, `disagreement_bm25_visual`, `disagreement_dense_visual` | Absolute pairwise differences of that page's normalized channel scores |
| 13 | `query_length` | `min(len(re.findall(r'\w+', text)), 64) / 64`, repeated on each active page |

This is a distinct `qpaf13_v1` feature definition, not a claim that the Word report's different 13-feature grouping was reproduced. Reciprocal rank has worst value `1/N`, not 0. Tiny positive ranges remain nonzero, unlike the historical `<=1e-15` zero-range policy.

The default gate is `Linear(13,3)`, temperature 1.0; optional MLP is `13 → 16 → Tanh → 3`. QARF averages active candidate feature rows then broadcasts one gate output per query. QPAF applies the same architecture separately per page. Softmax gives three simplex weights; fused score is the weighted sum of detached normalized channel scores. Both granularities use the same initialization seed `2026`; the core preset runs **40 SGD verification steps at learning rate 0.2**. These settings describe software verification only.

Loss: for each query with at least one positive and one negative, average `softplus(s_negative - s_positive)` over all positive-negative pairs; average those query losses with equal query weight. Labels must be binary. Skip queries lacking either class and report the skipped count; raise an error if no valid query remains. This is `pairwise_logistic` / `query_mean`, consistent with the narrow A001 loss decision. It is not masked listwise loss.

## Differences requiring explicit reconciliation

| Dimension | Historical frozen description | Current code / proposed handling |
|---|---|---|
| Dataset role | ViMDoc primary; ViDoSeek discovery | A002 records ViDoSeek primary; page-level learned primary and future document-level confirmation scope proposed |
| Visual model | ColQwen2.5 | M1.1 uses pinned ColQwen2-v1.0 adapter and ColQwen2 base; no interchangeability claimed |
| Candidate depth | 200/channel, max 600 | M1.1 uses 100/channel, max 300; learned depth pending adoption |
| Features/ranks | Historical 13-feature grouping; normalized rank best=1/worst=0 | `qpaf13_v1` above; reciprocal rank; review all changes beyond A001 |
| Zero-range rule | Range `<=1e-15` → 0 | M1.1/M1.2 exact zero only; tiny-range choice needs approval for research |
| Precision | Historical cache float64, explicit float32 cast/parity | M1.1 evaluates float64; M1.2 accepts float32/float64. No cross-preset parity measurement claimed |
| Loss | Masked listwise | A001 records pairwise approval; exact query-balanced/skipped-query behavior inventoried above |
| Seeds | Learned 20260820/21/22; bootstrap 20260820 | Oracle/software seed 2026; research multiseed policy not replaced by a software seed |
| Metric | Document nDCG@10 with page-to-document max | Current Oracle page nDCG@10; learned primary page unit proposed, confirmation document unit separate |
| Parity thresholds | Metric absolute `1e-12`, checkpoint reload `1e-7` | Historical acceptance targets only; `1e-12` Oracle W/T/L is a tie threshold, not evidence of cross-implementation parity |

Existing historical coverage thresholds, operational budgets and learned success criteria must be explicitly adopted or amended for each learned scope. This inventory does not claim they were run or passed. Real candidate recall, learned results, reload parity and latency/memory measurements remain separately required evidence when that scope is executed.

## OCR and identity interfaces

The inspected M1.1 text preset is `native_or_ocr`, PDFium rendering 150 DPI, minimum native characters 40, language `eng`, timeout 120 seconds. Its remediation config records parser `pypdfium2` version `4.30.0`, OCR engine `tesseract` version `5.3.0`, `quality_status=PROVISIONAL`, minimum OCR characters 50, minimum printable ratio 0.85, minimum OCR confidence 60.0, and maximum failure fraction 0.01. These are configured values, not measured calibration or proof that the executing machine's binaries match. The execution namespace config records `experiment_id=QPAF-M1_1-ORACLE-001` and empty `retry_of` for the initial attempt.

M1.8-001 describes PyMuPDF/pdfplumber, 300 DPI, minimum 50, `vie+eng`, 15 seconds and provisional printable/confidence/error-rate thresholds. These are distinct scopes and must not be reported as already identical. Runtime remediation and measured calibration need their own source/config/evidence identity; this package alone does not certify either.

Proposed M1.3/M1.6 interchange uses canonical `{doc}_page_{page:04d}`, with explicit legacy-ID aliases when needed. All positive qrels must resolve against actual document/page counts. Query IDs and document IDs must not be used interchangeably in split lookups. Preserve exact split bytes and measure query, document and content overlap separately. The draft does not rewrite historical M1.1 page IDs or historical evidence.

Proposed schedule: provisional OCR policy reviewed at M1, calibration at M2.3, full OCR at M2.6. The G1 team must record whether this schedule is accepted; this draft does not resolve the older G1 checklist's different calibration requirement by decree.

## Adoption and review checklist

- [ ] Phát confirms dataset/evaluation roles and every effective preset difference, including split rounding/count allocation.
- [ ] Thanh independently reviews the exact implementation/config hashes and impact beyond A001/A002.
- [ ] Select final source snapshot, new effective protocol/version and any further amendment IDs without rewriting A001/A002.
- [ ] Record approved learned candidate/feature/rank/precision/loss/seed/metric/statistical contract and required parity measurements.
- [ ] Record real corpus/qrels/split/overlap acceptance and OCR/G1 schedule decision.
- [ ] Bind adopted identity to an append-only registry event and final evidence package; obtain actual sign-offs through the existing governance process.

Until those decisions exist, this package is an auditable proposal and implementation inventory, with no new approval, freeze or G1 outcome.
