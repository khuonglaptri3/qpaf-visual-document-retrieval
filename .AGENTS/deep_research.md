# DEEP RESEARCH TASK: NOVEL RESEARCH DIRECTION DISCOVERY

## 0. CONFIGURATION — fill in before running

RESEARCH_DOMAIN: <e.g. Adaptive Retrieval Fusion for Visually Rich Document RAG>
TARGET_VENUES: ICCV, CVPR, ECCV, NeurIPS, ICML, ICLR, AAAI, IJCAI, TPAMI, IJCV
RECENCY_WINDOW: 36 months (HOT ZONE = last 12 months)
SUBMISSION_DEADLINE: <date or "none">
COMPUTE_BUDGET: <e.g. 4x A100, ~3 GPU-months>
TIME_HORIZON: <e.g. 3 months>
TEAM: <size + skills, e.g. 1 PhD student, strong CUDA, weak theory>
EXISTING_ASSETS: <codebases, datasets, hardware, prior papers>
RISK_APPETITE: balanced
EXCLUSION_LIST: <directions already taken by me / my lab>
N_FINAL: 3

## 1. MISSION

Discover research directions in RESEARCH_DOMAIN that are genuinely open, falsifiable,
measurable, feasible under my stated budget, and publishable at TARGET_VENUES.

Execute Stages 1-6 in order. Each stage has a gate. Items that fail a gate are killed and
logged, never carried forward. Do not skip stages. Do not reorder them. Do not produce the
final answer before Stage 6.

## 2. OPERATING RULES (binding on every stage)

R1 EVIDENCE. Every claim about the literature carries a ledger key [E##]. A ledger entry is
valid only with title, first author, venue+year, and a stable ID (arXiv ID / DOI /
OpenReview ID). Claims about a paper's content must name the locus: [E12, Sec.4.2],
[E12, Tab.3], [E12, Fig.6]. "Paper X shows Y" without a locus is invalid.

R2 NO UNRETRIEVED CITATIONS. Never cite a work you did not retrieve in this run. If you
recall a paper but cannot retrieve it, tag it [MEM]; it is speculative and cannot satisfy a
gate. Fabricated evidence invalidates the entire run.

R3 EVIDENCE STRENGTH. Tag each claim (D) direct — stated/measured at a named locus;
(I) inferred — combines >=2 direct sources via reasoning you state; (S) speculative — your
judgment. Gates accept only (D) and (I).

R4 CALIBRATION. Attach confidence 0.00-1.00 to every gap, novelty verdict, and feasibility
estimate. 0.90 means you would accept 9:1 odds. Never exceed 0.85 for any claim resting on
absence of evidence.

R5 ABSENCE RULE. "I searched and found nothing" is weak evidence. Every novelty or openness
claim must report the queries run, sources searched, date range, and the closest works
found. An empty closest-work table means the search failed — expand vocabulary and search
again.

R6 PERMISSION TO RETURN LESS. One strong direction is success. Zero directions plus a
saturation report is success. Never pad to fill a template. Never invent a gap, citation, or
candidate to satisfy a required field.

R7 ANTI-SYCOPHANCY. When evaluating your own earlier output, adopt the adversarial role
fully and resolve uncertainty toward rejection.

R8 VERDICTS. Every evaluated item ends in exactly one of PROMOTE / REVISE / KILL. Killed
items go to the Kill Log with a one-line reason. Never silently drop anything.

## 3. RETRIEVAL PROTOCOL (used in Stages 1, 3, 5)

RP1 ANCHOR: 2-4 recent surveys or position papers. Anchors orient; they are never evidence.
RP2 SEED: from anchors, extract most-cited and most-recent method papers.
RP3 BACKWARD: references of each seed — recovers inherited assumptions.
RP4 FORWARD: works citing each seed, newest first. This is where "already solved" lives.
RP5 VENUE SWEEP: accepted-paper lists of TARGET_VENUES, last N cycles, keyword filtered.
RP6 FRONTIER: arXiv HOT ZONE + OpenReview, INCLUDING rejected and withdrawn submissions —
these record what was tried, why it failed, and which gaps are already considered closed.
RP7 VOCABULARY: before declaring anything absent, generate >=5 phrasings: the sub-field's
jargon, an adjacent field's term, the pre-deep-learning term, the application
community's term, and a jargon-free description.

READING TIERS
T1 deep (8-15 papers): method, math, protocol, ablations, failure cases, appendix.
T2 method-level (30-60): setting, mechanism, benchmarks, headline numbers, limitations.
T3 metadata (unbounded): title/abstract/venue/year, for trend statistics only. A T3 paper
may never be cited as evidence about method internals.

Log every query, source, and date filter. The Search Log is a required output.

## 4. STAGES

### STAGE 1 — LANDSCAPE AND PARADIGM MAP

Propose nothing. No ideas, no gaps, no "this suggests". Any proposal here is an error.

Execute RP1-RP6 and build the Evidence Ledger. Cluster the corpus by underlying commitment
(representation, supervision signal, or problem formulation) — NOT by application or
backbone. If two clusters differ only in backbone, they are one cluster.

For each paradigm state: core commitment; >=3 representative works (>=1 read at T1); the
mechanism in 3-5 technical sentences; datasets and benchmarks; evaluation protocol;
demonstrated strengths (D); demonstrated weaknesses (D, from reported failures and ablations,
not your priors); STATED assumptions; UNSTATED assumptions inferable from the method's
construction; and how the paradigm changed across RECENCY_WINDOW.

Also produce: an ancestry graph (which paradigm descends from which, and which assumptions
were inherited without re-examination), and an OPEN DISAGREEMENTS table recording verbatim
pairs of incompatible claims across papers. Do not resolve the disagreements.

STOP only when: (S1) the last 15 T3 papers introduced no new cluster; (S2) every cluster has

> =3 works and >=1 T1 read; (S3) the forward-citation frontier of every seed in the HOT ZONE
> is enumerated; (S4) for every cluster you can state its primary benchmark and best reported
> number. If you stop short, name the under-covered clusters. Never claim completeness you did
> not reach.

OUTPUT: Evidence Ledger table | Paradigm blocks | Ancestry graph | Open Disagreements table |
Trajectory summary | Coverage report | Search log.

### STAGE 2 — EVALUATION REGIME AND MEASURABILITY AUDIT

Determine what this field can and cannot measure, and therefore what contribution is even
demonstrable.

Per benchmark: (a) provenance and how usage drifted from original purpose; (b) HEADROOM —
best number vs ceiling vs inter-run noise; compute the spread across the top 5 reported
results, and if improvements sit inside noise, declare it SATURATED; (c) protocol integrity —
do papers actually use the same splits, resolutions, preprocessing, metrics? log every
inconsistency (D); (d) contamination/leakage risk, especially against pretraining corpora;
(e) metric validity — what it rewards that nobody wants, what it cannot see; (f) population
coverage gaps.

Then: BLIND SPOT LIST — capabilities the field cannot currently detect; for each, would a
real improvement register on any existing benchmark? If no, name the instrument required.

Then partition the space: MEASURABLE (existing benchmarks can demonstrate it) /
INSTRUMENTABLE (needs a new benchmark or protocol buildable within COMPUTE_BUDGET and
TIME_HORIZON — here the instrument may itself be the contribution) / UNMEASURABLE (no
feasible instrument; must be killed now, not in month five).

If RESEARCH_DOMAIN has no leaderboard culture, replace (b)-(f) with that field's validity
regime (proof strength and assumption weakening; statistical power and construct validity;
clinical endpoint validity and data access). The blind-spot list and partition remain
mandatory in every field.

OUTPUT: benchmark audit table | protocol inconsistency log | LIVE/NEAR-SATURATED/SATURATED
verdict per benchmark WITH NUMBERS | blind spot list | measurability partition | 3-6
contribution shapes this field can currently reward.

### STAGE 3 — GAP EXCAVATION

Propose no solutions. Do NOT source gaps from "Limitations" or "Future Work" sections — those
are the field's advertised, already-crowded gaps. You may cite them as corroboration of a gap
you found independently, never as its origin.

Apply all six lenses:
L1 ASSUMPTION EXCAVATION — per paradigm, enumerate what must be true (data, sensor, geometry,
distribution, supervision, scale, compute); mark stated vs unstated; for each unstated
assumption name a realistic violating condition and check whether any work examined it (D).
L2 ANCESTRY DRIFT — assumptions inherited from a founding work and never re-examined, where
conditions have since changed (data scale, model class, sensors, deployment).
L3 CONTRADICTION MINING — for each Open Disagreement, decide whether it is confound-explained
(different splits/scale/protocol) or genuinely unexplained. Unexplained contradictions
between competent works localize phenomena the field does not understand.
L4 FAILURE FORENSICS — aggregate every reported failure case, negative ablation, and failure
figure across T1+T2; cluster by symptom. A symptom recurring across mechanistically
different paradigms is a structural gap, not an engineering defect.
L5 NEGATIVE SPACE — cross-tabulate {problem settings} x {method families} and {desired
capabilities} x {benchmarks that can detect them}. For every empty cell, classify why:
HARD / UNMEASURABLE / UNINTERESTING / UNNOTICED, with a stated reason. Only UNNOTICED and
UNMEASURABLE-BUT-IMPORTANT count as gaps.
L6 MEASUREMENT BLINDNESS — from the Stage 2 blind spots: what does the field not pursue
because nothing rewards it? These are systematically under-crowded.

Per gap emit: GAP-ID | lens | one-sentence statement phrased as an unsolved problem (not a
wish) | why it is open (the mechanism, not a restatement) | evidence: >=2 independent (D)/(I)
entries with loci | prior attempts and specifically why they fell short [E##, locus] |
SOLVED-BY TEST: the observable result that would constitute solving it | measurability class
from Stage 2 | crowding in the HOT ZONE (none/light/heavy, D) | confidence | KILL CONDITION:
the single finding that would prove this gap is not real.

GATE 1 — EVIDENCE GATE. PASS = >=2 independent (D)/(I) citations with loci plus a stated
mechanism of openness. WATCHLIST = real but thin (reported separately, not carried forward).
KILL = supported only by (S), by a single source, or originating from Future Work.

OUTPUT: Gap Matrix | Watchlist | Kill Log | lens yield summary (report lenses that came up
empty rather than forcing output).

### STAGE 4 — FALSIFICATION OF GAPS

Your objective is to CLOSE these gaps. You succeed by finding the paper that already solved
one, not by confirming openness.

Per gap: assume a competent group already solved it and you simply have not found their
paper. Apply RP7 (>=5 phrasings, logged, including adjacent-field terminology — cross-
community duplication is the dominant cause of false openness). Execute RP4 and RP6, reading
rejected OpenReview submissions deliberately.

Build a CLOSEST-WORK TABLE of >=5 works ranked by proximity even when none is close. Per
work: what it does | what it measures | the precise residual the gap still contains. Then
check the SOLVED-BY TEST against each.

VERDICT: OPEN | PARTIALLY-OPEN (name the remaining conditions) | CLOSED (cite the closing
work) | UNMEASURABLE | UNCERTAIN (state what evidence would resolve it). Attach confidence
and CONCURRENT WORK RISK (none/moderate/high) evaluated against SUBMISSION_DEADLINE.

GATE 2 — PROMOTE only OPEN / PARTIALLY-OPEN with a non-empty closest-work table and >=5
logged phrasings. Kill the rest with the closing citation.

OUTPUT: per-gap falsification report | surviving gaps ranked by openness confidence x
measurability x inverse crowding | Kill Log | search log.

### STAGE 5 — HYPOTHESES, IDEAS, AND SOLUTION-LEVEL PRIOR-ART AUDIT

5A. GENERATE. Per surviving gap, 1-3 candidates. Each declares exactly one PRIMARY NOVELTY
AXIS: A1 reformulation | A2 representation | A3 objective/supervision | A4 inference or
optimization procedure | A5 theory explaining an unexplained phenomenon | A6 measurement
instrument | A7 removal of an assumption every current method depends on.

AUTO-KILL: if the one-sentence description reduces to "apply X to Y", "add X to Y", or
"combine X and Y", kill it — unless it states, with evidence, either the specific reason the
combination was impossible until a recent development, or how it changes the problem
formulation rather than the solution stack.

DIVERSITY: at most one candidate per primary axis; include a pairwise distinctness statement.
If two candidates would be refuted by the same experiment, they are one candidate.
RISK: unless RISK_APPETITE is conservative, at least one candidate must be marked
HIGH-VARIANCE (low probability, high consequence). Generate it before filtering — a filter
cannot recover an idea that was never generated.

IDEA CARD (one page each): IDEA-ID | title stated as a claim | GAP-ID and the residual
attacked | CORE HYPOTHESIS H, one falsifiable sentence "If <intervention>, then <observable>,
because <mechanism>" | why existing methods cannot do this, at mechanism level, citing
paradigm assumptions [E##] | key insight (the non-obvious thing that must be true) | primary
axis | MINIMAL VIABLE EXPERIMENT with dataset, baseline, metric, and the numeric threshold
that counts as support | DISCONFIRMING EXPERIMENT that would refute H — if you cannot name
one, kill the card | what the field learns IF H IS FALSE | measurability class | feasibility
GREEN/AMBER/RED against COMPUTE_BUDGET, TIME_HORIZON, TEAM, EXISTING_ASSETS with a rough
GPU-hour and person-month basis | EXCLUSION_LIST check.

5B. AUDIT. This is the highest-leverage step: an open gap attacked with a published method is
how research plans die. Decompose each card into primitives (problem setting, representation,
supervision signal, inference procedure, claimed effect). Search each primitive separately,
then combined, with >=5 phrasings each, including adjacent-field and pre-deep-learning terms.
Execute RP4 and RP6.

Build a CLOSEST-WORK TABLE of >=5 entries per card: work [E##] | what it does | shared
primitives | DELTA (what your card does that it does not) | is the delta a difference IN KIND
or IN DEGREE? Then write a DELTA STATEMENT a hostile reviewer would have to accept. If the
honest delta is degree-only, say so — that is a duplicate in new vocabulary.

VERDICT: NOVEL | NARROWLY-NOVEL (state the exact conditions) | DUPLICATE (cite it) |
CONCURRENT-RISK (novel today, likely scooped before SUBMISSION_DEADLINE).

GATE 3 — PROMOTE NOVEL, or NARROWLY-NOVEL whose delta survives paraphrase by a hostile
reader. REVISE returns to 5A with the colliding work named. KILL duplicates and degree-only
deltas. If fewer than 5 closest works surface for any card, the search failed — search again
before returning.

OUTPUT: Idea Cards | pairwise distinctness statement | closest-work tables | delta statements
| verdicts with confidence and concurrent-work risk | auto-kill log | search log.

### STAGE 6 — ADVERSARIAL REVIEW, THEN PLAN THE SURVIVORS

6A. PANEL. Write four independent reviews per card in full before starting the next. Do not
harmonize them; disagreement must survive into the output.
R1 NOVELTY SKEPTIC — "this is <prior work> renamed." Attack the delta statement specifically:
difference in kind, or a difference narrated as one?
R2 METHODOLOGIST — "the experiment cannot support the claim." Attack the chain from MVE
result to H: confounds, missing ablations, unfair or differently-protocoled baselines
(use the Stage 2 inconsistency log), metric-claim mismatch, threshold inside benchmark noise.
R3 DOMAIN INSIDER — "the premise is wrong." Attack assumptions treated as settled,
known-but-unpublished negative results, practical obstacles invisible from the literature,
and whether the gap is an artifact of reading papers rather than running code.
R4 RESOURCES — "this cannot be done as described." GPU-hours vs COMPUTE_BUDGET; calendar vs
TIME_HORIZON and SUBMISSION_DEADLINE; skills vs TEAM; dataset access and licensing;
whether baseline code exists and reproduces published numbers; whether fair comparison is
achievable.

Each reviewer scores 1-5 with a one-line justification on: Novelty/delta durability, Gap
evidence, Soundness of plan-to-claim inference, Measurability, Feasibility, Reviewer risk.
Anchors: 1 fatal, 2 serious unaddressed weakness, 3 defensible, 4 strong, 5 exceptional.

AREA CHAIR: write a meta-review per card naming which objections are fatal and which are
addressable; resolve reviewer disagreement explicitly rather than averaging it. When >=3
cards are under review, reject at least two thirds; ties break toward rejection; every
rejected card enters the Kill Log with its meta-review so I can overrule it. Rank survivors
on TWO axes — expected scientific value if H holds, and probability of acceptance — and
report the frontier. Do not collapse it into one score.

REBUTTAL: one round. A valid rebuttal supplies new evidence, a design change, or a scoped-down
claim; rhetorical reframing is not a rebuttal. If a rebuttal changes the core hypothesis or
any novelty primitive, the card returns to Stage 5B for re-audit and does not proceed.

GATE 4 — PASS requires no dimension scored <=2 by any reviewer, mean >=3.5, no unaddressed
fatal objection. Promote at most N_FINAL cards.

6B. DOSSIER — for survivors only:

1. Problem statement, formal setting, notation, explicit assumptions, H restated precisely.
2. Positioning paragraph + comparison table against the 5 nearest works.
3. TABLE 1 WRITTEN FIRST: the main results table of the unwritten paper — exact rows
   (methods), exact columns (datasets, metrics), and the numbers required for the claim to
   hold. Then the ablation table, each row isolating one component and answering one reviewer
   question.
4. Method development plan, staged from the simplest version that could support H.
5. Resources: datasets with access route and license; baselines with public code links and
   whether they reproduce; GPU-hour estimate per experiment, summed against COMPUTE_BUDGET
   with headroom stated; skill gaps vs TEAM.
6. Timeline against TIME_HORIZON with milestones, and per milestone a DECISION DATE and a
   KILL CRITERION — the observable result that means stop.
7. Risk register: technical, research, publication. Each with probability, impact, early
   warning signal, mitigation, resolution date. Include what to do if scooped at month three.
8. INSURANCE CONTRIBUTION: what remains publishable if H is false. If there is none, say so
   plainly rather than inventing one.
9. The three most likely reviewer objections, each with the pre-empting experiment, scheduled.
10. Re-validation schedule: novelty decays — dates to re-run the Stage 5B audit and re-sweep
    the HOT ZONE.

## 5. FINAL OUTPUT

Return, in this order:
A. Executive summary: the surviving directions (<=N_FINAL), one paragraph each.
B. Full dossiers.
C. Evidence Ledger.
D. Kill Log (everything killed at every gate, with reasons) — this is a required deliverable,
not an appendix.
E. RUN AUDIT: ledger size by tier; paradigms covered and knowingly under-covered; saturation
conditions met vs unmet; total queries and sources; share of claims at (D)/(I)/(S) with
every [MEM] listed; THE WEAKEST LINK — the single artifact most likely to be wrong and
what I should verify first; what this run could not determine; artifact dates and novelty
expiry.

Before returning, verify: no citation lacks a stable ID and locus; no closest-work table has
fewer than 5 entries; no surviving hypothesis lacks a disconfirming experiment; no surviving
card exceeds COMPUTE_BUDGET; no Stage 1 output contains a proposal; every killed item appears
in the Kill Log. Fix any violation before answering.
