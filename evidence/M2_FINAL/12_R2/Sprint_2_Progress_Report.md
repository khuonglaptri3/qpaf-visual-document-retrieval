# Sprint 2 Progress Report

> **Report status:** `ISSUED_D1_BLOCKED_M2_CLOSURE_NOT_REACHED`
>
> **Planned period:** 28/09/2026 – 09/10/2026 (workbook rows M2.1–M2.12)
>
> **Evidence period:** 29/09/2026 (G1) – 21/10/2026 (D1)
>
> **Report date:** 21/10/2026
>
> **Prepared by:** Tấn Phát — Research Lead / Protocol & Gate Owner
>
> **Source snapshot:** `origin/develop` `7d4f9282ecc4593cc050a748e0055bf06f5fa255`
>
> **D1 (M2.11):** `BLOCKED` — owner Thanh, 21/10/2026
>
> **Independent review of this report:** `PENDING`
>
> **M2 closure:** `NOT_REACHED`
>
> **Learned training / evaluation:** `NOT_RUN`

This report closes the M2.12 reporting task for Sprint 2. It summarizes what
the repository evidence shows on the source snapshot above, the D1 blockers and
the plan for Sprint 3. It is not a D1 decision, an M2 closure record or an
authorization to run the learned pilot. Every status below comes from a
committed evidence record. Planned dates do not count as acceptance evidence.

## 1. Sprint objective

Sprint 2 prepares one valid, matched package for the learned QARF/QPAF pilot:

1. freeze the data-split roles and ID manifests;
2. calibrate the three retrievers and the pinned OCR on bounded samples;
3. build and test the minimal learned training/evaluation pipeline;
4. freeze the baseline roster, statistics and leakage checks;
5. run full-corpus OCR with page-level hashes;
6. freeze QARF/QPAF configs that differ only in gate granularity;
7. build the verified three-retriever score cache and candidate pool;
8. close the CARF diagnostic or record why it was not run;
9. audit readiness independently and record D1;
10. report status, blockers and the next sprint plan (this file).

Success in this sprint is a valid D1, not a retrieval number. G1 authorized
data preparation, OCR calibration, full OCR and score-cache construction. It
kept learned training restricted
([G1 final decision](../../M1_FINAL/06_G1/G1_final_decision.md), §2.3).

## 2. Timeline position

The workbook planned M2 for 28/09–09/10 and the first M3 tasks from 12/10.
The result-bearing M2 runs were executed between 17/10 and 20/10, and D1 was
recorded on 21/10. Sprint 2 therefore finished about 12 days after its planned
end. M3.1–M3.8 (planned 12/10–23/10) have not started, because each depends on
D1.

## 3. Task status

| Task | Owner | Evidence state | Selected evidence | Remaining limitation |
| --- | --- | --- | --- | --- |
| M2.1 Data-split roles | Thanh | `VERIFIED_ACTIVE_PRIMARY_SPLITS` | [`m2.1-002`](../../revisions/m2.1-002/README.md) | Confirmation and external roles are not activated |
| M2.2 Retriever calibration | Khương | `PASS` (bounded smoke) | [`m2.2-001`](../../revisions/m2.2-001/README.md) | 4 queries × 16 pages; not full-corpus quality |
| M2.3 OCR calibration | Khương | `COMPLETE_BOUNDED_CALIBRATION / FROZEN_OPERATING_CONFIGURATION` | [`m2.3-002`](../../revisions/m2.3-002/README.md) | Decisions were recorded by Codex AI at the user's request; no team acceptance signature; no corpus accuracy claim |
| M2.4 Learned pipeline | Tấn Phát | `synthetic_software_verification` | [method](../../../docs/03_method/m2.4-learned-pipeline.md), [runs](../../../results/m2.4/README.md) | Real-data run waits for an accepted cache; independent review `PENDING` |
| M2.5 Baselines, statistics, leakage | Thanh | `FROZEN_METHOD_AND_SOFTWARE_FIXTURE_ONLY` | [`m2.5-001`](../../revisions/m2.5-001/README.md) | `learned_qarf` and all real results `NOT_RUN`; independent review `PENDING` |
| M2.6 Full OCR + page hashes | Khương | `COMPLETE / VERIFIED_FULL_OCR_BUNDLE` | [`m2.6-001`](../../revisions/m2.6-001/README.md) | No OCR-accuracy certification |
| M2.7 Matched QARF/QPAF configs | Tấn Phát | `FROZEN_CONFIG_PENDING_M2.8_INPUTS` | [`m2.7-002`](../../revisions/m2.7-002/README.md) (supersedes `m2.7-001`) | Real cache, qrels and candidate bindings remain `PENDING_M2.8` |
| M2.8 Score cache + candidate pool | Khương | `GPU COMPLETE / CACHE VERIFIED / BLOCKED_COVERAGE` | [`m2.8-001`](../../revisions/m2.8-001/README.md) | One train query is uncovered; the zero-uncovered gate fails |
| M2.9 CARF diagnostic | Thanh | `NOT_RUN_JUSTIFIED` | [`m2.9-001`](../../revisions/m2.9-001/README.md) | Deferred to M6/P3-02; a permitted disposition, not readiness evidence |
| M2.10 Readiness audit | Thanh | `AUDIT_COMPLETED_READINESS_BLOCKED` | [`m2.10-001`](../../revisions/m2.10-001/README.md) | Technical audit only; named human review `PENDING` |
| M2.11 D1 Data Readiness | Thanh | `BLOCKED` | [`m2.11-001`](../../revisions/m2.11-001/README.md) | See §5 |
| M2.12 R2 report | Tấn Phát | `ISSUED` | This file | Independent report review `PENDING` |

Ten of the eleven technical tasks reached the end state their milestone row
allows. Those states are verified software, calibration or data records. Even
so, D1 is `BLOCKED`, so M2 cannot close.

## 4. Measured Sprint 2 evidence

All figures below are engineering or data-readiness measurements. None of them
is a learned retrieval result.

| Area | Measured value | Source |
| --- | --- | --- |
| Active primary corpus | ViDoSeek: 292 PDFs, 5,385 pages, 1,142 queries | [`m2.1-002`](../../M2_FINAL/01_data_splits/README.md), [`m2.6-001`](../../revisions/m2.6-001/README.md) |
| Split roles | Train/validation/test = 799/171/172; pairwise overlap 0 | [`m2.1-002`](../../M2_FINAL/01_data_splits/README.md) |
| Retriever calibration | BM25, BGE-M3, ColQwen2.5 PASS on 4 queries × 16 pages; ColQwen2.5 runs float32 with a 256-visual-token cap, and the earlier bfloat16 parity FAIL stays recorded | [M2.2 summary](../../M2_FINAL/02_retriever_calibration/README.md) |
| OCR operating config | Tesseract 5.3.0, eng, 300 DPI, OEM 3/PSM 3; 121 sample pages, 242 OCR attempts, 0 technical errors | [`m2.3-002`](../../revisions/m2.3-002/README.md) |
| Full OCR | 5,385 retained page records; 1 technical failure (0.0186%), within the frozen 1% cap; 37,695 artifacts verified | [`m2.6-001` summary](../../revisions/m2.6-001/summary.json) |
| Learned pipeline | QARF/QPAF train, select, checkpoint and reload on a synthetic fixture; reload Δ = 0 | [M2.4 results](../../../results/m2.4/README.md) |
| Baseline and statistics freeze | Primary metric nDCG@10 (page unit); roster BM25, BGE-M3, ColQwen2.5, uniform CombSUM, RRF k=60, train-fitted static, learned QARF; seeds 20260820/21/22; paired 10,000-bootstrap CI with W/T/L | [`configs/m2.5/freeze.json`](../../../configs/m2.5/freeze.json) |
| Matched configs | For all three seeds, QARF/QPAF differ only in `gate_granularity` (`query` vs `page`); 42 initial parameters are bit-identical; 4 training batches over 2 epochs have identical query-ID order | [`m2.7-002`](../../revisions/m2.7-002/README.md) |
| Score cache | Real Modal A10 run; 18,449,010 scalar scores; 549,689 frozen candidates; ≤600 pages per query | [`m2.8-001`](../../revisions/m2.8-001/README.md) |
| Candidate coverage | Macro recall 0.999124343257443; train 798/799, validation 171/171, test 172/172 | [M2.10 audit](../../revisions/m2.10-001/audit.json) |
| Readiness audit replay | 17 M2.6 and 30 M2.8 revision files rehashed; split hashes, matched parity and coverage replayed; M2.4/M2.5/M2.7/M2.8/M2.10 tests ran 20/6/19/34/3, all OK | [M2.10 audit](../../revisions/m2.10-001/audit.json) |

### The uncovered train query

Query `04450a0f59f81025574451222aa26322ae7ede42_2` asks when an EU pilot project
started. The source label is page 7 (a timeline showing May 2019). All three
retrievers ranked pages of the correct PDF first. Page 7 ranked 271 (BM25),
273 (dense) and 769 (visual), which puts it outside the frozen top-200
per-channel union of 448 pages. No missing page, OCR, namespace or shard-merge
error was found
([follow-up note](../../../docs/superpowers/reports/2026-10-21-m28-uncovered-query-followup.md),
[diagnosis](../../revisions/m2.8-001/uncovered_diagnosis.json)). The freeze was
kept intact: the query was not dropped, no positive was injected and depth was
not changed.

## 5. D1 decision and open blockers

D1 asks whether the matched learned-pilot package is valid to execute. The
recorded answer is `BLOCKED`
([decision](../../revisions/m2.11-001/decision.json),
[method note](../../../docs/03_method/m2.11-d1-data-readiness.md)).

| D1 check | Result |
| --- | --- |
| Split hashes and counts | `PASS` |
| M2.6 / M2.8 revision hashes | `PASS_LOCAL_METADATA` |
| Matched config and synthetic parity | `PASS` |
| Candidate macro recall ≥ 0.95 | `PASS` |
| Zero uncovered queries | `BLOCKED` |
| Real cache / qrels / candidate binding | `PENDING` |
| Synthetic checkpoint reload | `PASS_IN_PROCESS` |
| Real learned checkpoint reload | `NOT_APPLICABLE_BEFORE_PILOT` |
| Named independent human review | `PENDING` |

| ID | Blocker (from `blocking_reasons`) | Owner | Closure evidence |
| --- | --- | --- | --- |
| R2-B01 | `M2.8_ZERO_UNCOVERED_GATE_FAILED` | Tấn Phát (amendment) + Khương (cache) | Approved candidate-policy amendment, or a documented review that keeps the policy; then a new create-once cache revision with recall ≥ 0.95, zero uncovered, ≤600 pages per query and passing integrity checks |
| R2-B02 | `M2.7_REAL_INPUT_BINDING_NOT_FROZEN` | Tấn Phát | New M2.7 revision or M3 run manifests that bind the accepted cache, candidate-set and qrels SHA-256; parity replay repeated on the real rows |
| R2-B03 | `NAMED_HUMAN_REVIEW_PENDING` | Thanh + named reviewer | Repeated M2.10 audit on the new revision and a named independent D1 review |

The M2.8 follow-up note proposes a label-free expansion: fill the spare
candidate capacity with pages from the single highest max-RRF PDF, keeping the
original union. It has **not** been implemented or approved. The proposal was
written after a train failure had been observed, so the amendment must say
that it is post hoc. It must also be checked on train/validation only, as one
fixed policy, with no test labels used to choose a variant. Rescoring is not
needed for this: the cache already holds all 6,149,670 query-page scores for
each channel.

## 6. Scientific claim boundary

- No learned QARF or QPAF checkpoint has been trained on real data.
- No test ranking metric has been computed (`test_ranking_metrics_computed: false`
  in M2.10 and D1).
- M2.4 and M2.7 numbers come from synthetic fixtures and verify software only.
- Coverage of 99.91% is a candidate-pool property, not evidence that nDCG@10
  or learned QPAF will improve.
- The earlier ViDoSeek oracle studies remain bounded `oracle_upper_bound`
  evidence and are not repeated or extended here.
- The CARF not-run record makes no readiness or performance claim.

A valid negative or blocked result is acceptable. The gate is not weakened to
reach a PASS.

## 7. Risks

| Risk | Impact | Control | Owner |
| --- | --- | --- | --- |
| The candidate-policy fix is tuned on the observed failure | Post-hoc bias; unfair comparison | One fixed label-free rule, recorded as post hoc in the amendment, evaluated on train/validation only, same pool for QARF, QPAF and all baselines | Tấn Phát + Thanh |
| A larger union adds distractors or cost | Lower ranking quality or higher latency | Report candidate min/mean/max and added pages; measure the latency/memory gate at M3.6 | Khương |
| Schedule slip (~12 days) compresses M3 | Pressure to skip review or reload checks | Keep D1 → M3 order; re-baseline M3 dates instead of overlapping gated tasks | Tấn Phát |
| Local checkouts lack the Parquet payload | Audits rely on archived receipts | Re-verify payload hashes from the Modal Volume when the new revision is built | Khương + Thanh |
| AI-recorded decisions are read as team sign-off (M2.3) | Overstated acceptance | Keep the "no team signature" limitation visible until a named reviewer confirms | Whole team |
| Independent reviews stay pending (M2.4, M2.5, M2.7, D1) | Gate cannot pass | Schedule named reviews as explicit tasks before the new D1 | Thanh |

## 8. Next sprint plan (Sprint 3 / M3)

Sprint 3 begins with an M2 carry-over. M3 tasks begin only after a new D1
decision records `PASS` (or a `PARTIAL` that explicitly permits the pilot).

**Step 0 — D1 recovery (carry-over, before M3.1):**

1. Tấn Phát drafts the candidate-policy amendment (old/new definition,
   post-hoc status, leakage, fairness, cost, runs to repeat), or a documented
   decision to keep the policy.
2. Khương implements a separate builder/verifier with its own policy ID,
   evaluates the fixed rule on train/validation, freezes candidates for all
   queries, then audits coverage in a new create-once revision.
3. Tấn Phát binds the accepted cache, candidate and qrels hashes for the
   matched pilot.
4. Thanh reruns `scripts/audit_m210_readiness.py` into a new revision. A named
   independent reviewer then records a new D1.

**M3 sequence after D1 PASS** (durations from the workbook, in working days
after D1):

| Order | Task | Owner | Workbook duration | Relative slot |
| --- | --- | --- | --- | --- |
| 1 | M3.1 Seal pilot inputs, verify row parity | Khương | 2 days | D1 + 1–2 |
| 2 | M3.2 Matched learned QARF pilot | Tấn Phát | 3 days | D1 + 3–5 |
| 3 | M3.3 Independent QARF validation (reload ≤ 1e-7) | Thanh | 2 days | D1 + 6–7 |
| 4 | M3.4 Matched learned QPAF pilot | Tấn Phát | 2 days | D1 + 8–9 |
| 5 | M3.5 Per-query QPAF − QARF deltas, 95% CI, W/T/L | Thanh | 2 days | D1 + 9–10 |
| 5 | M3.6 Output integrity and resource gates | Khương | 2 days | D1 + 9–10 |
| 6 | M3.7 G2 decision | Tấn Phát | 1 day | D1 + 10 |
| 6 | M3.8 R3 report | Tấn Phát | 2 days | D1 + 9–10 |

Each pilot run needs its own authorization record under the
[run policy](../../M1_FINAL/02_protocol/run_policy.md) §3 (exact commit,
data/cache/qrels hashes, command, resource and cost caps, retry count,
create-once namespace). Neither D1 nor this plan is that authorization.

## 9. Execution and compute ledger

| Activity | Platform | Measured | Status |
| --- | --- | --- | --- |
| M2.2 retriever smoke | Modal GPU (`A10G` in resolved config) | 4 × 16 bounded sample | `PASS` |
| M2.3 OCR calibration | Modal CPU, no GPU | Worker wall 285.9 s; peak RSS 1,281 MiB | `COMPLETE_BOUNDED` |
| M2.6 full OCR | Modal CPU (4 cores, 2 workers), no GPU | Wall 4,846 s (80.8 min); peak RSS 1,432 MiB; 17.5 GB artifacts | `COMPLETE` |
| M2.8 score cache | Modal NVIDIA A10, CUDA 12.6, PyTorch 2.7.1 | Wall 5,490 s (91.5 min) | `COMPLETE / BLOCKED_COVERAGE` |
| Learned QARF/QPAF training on real data | — | — | `NOT_RUN` |
| Test ranking evaluation | — | — | `NOT_RUN` |
| R2 preparation | Local | Documentation, SHA-256 hashing, unit tests | This report |

## 10. Regression receipt for this report

Command: `python -X utf8 -m unittest discover -s tests -q`, run on the source
snapshot on 21/10/2026. Environment: local Windows, Python 3.13.7, a fresh
virtual environment built from
[`requirements/dev-local.txt`](../../../requirements/dev-local.txt) (PyTorch
2.7.1, pypdfium2 4.30.0, Pillow 11.3.0, pytesseract 0.3.13).

| Result | Count |
| --- | ---: |
| Tests run | 333 |
| Passed | 331 |
| Skipped | 2 |
| Errors | 0 |
| Failures | 0 |

`pip check` reported no broken requirements. Separate runs of the M2.4, M2.5,
M2.7, M2.8 and M2.10 test groups gave 20/6/19/34/3 tests, all OK, the same
counts the M2.10 audit recorded. The pinned-environment receipts of the
original tasks remain the acceptance evidence. This local run does not replace
them.

An earlier run in an unprepared global Python (333 tests, 7 errors) failed only
because `pytesseract` was not installed. It was an environment gap, not a code
regression, and is not the reported result.

## 11. Evidence index

SHA-256 values were computed on the source snapshot above.

| File | SHA-256 |
| --- | --- |
| `evidence/M1_FINAL/06_G1/G1_final_decision.md` | `8a65555f0a7f38cada9fabb385e048afee01014395782fe842f38814c24ff66a` |
| `evidence/revisions/m2.1-002/data_split_manifest.json` | `ea5a19f93dce07cce375d6fb6afed630606e00916c5daa10938562aee9cddfad` |
| `evidence/revisions/m2.2-001/summary.json` | `9bfba2c320013efa67fd416f2fc68f75e906fe2641d8bb94c63c8f34539a46fd` |
| `evidence/revisions/m2.3-002/decision.json` | `dbc5896fae70c72ee5775bf70095355867a2a1b39e2ca6ebdf4ef94f833c2f99` |
| `evidence/revisions/m2.5-001/verification.json` | `777b0042fb9781cd73c761cad74956c00fd2bb04f784e441e61c132ce82e87d3` |
| `configs/m2.5/freeze.json` | `317b4333968ae4250e0e9bc71846d37f47e5f958872c8cf27949a0c0d8c3579c` |
| `evidence/revisions/m2.6-001/handover.json` | `64cb69c0256e77b9fc00b9ca5810bee07ac3205b9388b050e598d66c53822649` |
| `evidence/revisions/m2.7-002/verification.json` | `bf60c08804248b88990622121fb17687fd186fbc209213f0a0f1e857a4171463` |
| `configs/m2.7/matched.json` | `705dd5705a3849239568eebee2542a9f39ccc2f123e334e7e933fde74f55fa6d` |
| `evidence/revisions/m2.8-001/handover.json` | `8664d01b48720826bf5ceda4dc4f07f9ba0aea29d414ffbd39f8d35ef3ae5b37` |
| `evidence/revisions/m2.8-001/coverage_report.json` | `598a68b513112abb4eb98d5b798b4ce60f17476eb8f07390a002434a100b4d62` |
| `evidence/revisions/m2.9-001/decision.json` | `e9c74fb0338d96e22e61baa74e1999a7db06f7a57064e3f1f64ea420c529d2fe` |
| `evidence/revisions/m2.10-001/audit.json` | `aeaba024909ba5be6d63d28a45f41518ed752ca4dc1e9fd2f0508e9ef02b36aa` |
| `evidence/revisions/m2.11-001/decision.json` | `7c9583ad3dbb5a38e4566fe985d22695a73bcc6820db869d9f0a0175aa7f5104` |

The M2.9, M2.10, M2.8 handover and M2.7 manifest hashes match the bindings
inside the D1 decision.

## 12. Pending fields and sign-off state

| Field | Value |
| --- | --- |
| D1 decision | `BLOCKED` (M2.11-001) |
| New D1 after recovery | `NOT_REACHED` |
| Candidate-policy amendment | `PROPOSED_NOT_APPROVED` |
| Named independent D1 review | `PENDING` |
| Independent review of this report | `PENDING` |
| M2 closure record | `NOT_CREATED` — requires a non-blocked D1 |
| G2 (M3.7) | `NOT_REACHED` |

| Role | State |
| --- | --- |
| Report owner — Tấn Phát | `ISSUED` |
| D1 owner — Thanh | `BLOCKED` decision recorded |
| Technical owner — Khương | Cache verified; coverage blocker open |
| Named independent reviewer | `PENDING` |

M2 stays open. When a new D1 is recorded, add an append-only addendum to this
file or create a successor report. Do not edit the statuses above in place.
