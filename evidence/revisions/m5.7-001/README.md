# M5.7 / R8 — Three-seed paired TEST-172 analysis

Owner: Thanh. Inputs are the independently reviewed, sealed R7 run and the
M5.1 preregistration. `summary.json` and `per_query_deltas.csv` are generated
by `scripts/analyze_m57_r8.py`; `owner_confirmation.json` records Thanh's
acceptance with the negative baseline result.

| Comparison, nDCG@10 | Seed-mean paired delta | 95% query-bootstrap CI | W/T/L |
| --- | ---: | --- | --- |
| QPAF − matched QARF | +0.076175 | [+0.042928, +0.109909] | 49/107/16 |
| QPAF − train-fitted static | −0.006748 | [−0.019028, +0.005269] | 7/152/13 |

The three QPAF test means are 0.817284, 0.820049 and 0.819034; the QARF
means are 0.742817, 0.742206 and 0.742817. The frozen, validation-selected
strongest deployable baseline is `train_fitted_static`, with test nDCG@10
0.825537. The overall quality gate is **not met** because QPAF does not
exceed that baseline. No seed, checkpoint, method or baseline was selected
after viewing TEST-172.

For each of 172 queries, R8 averages the three matched seed deltas first,
then draws 10,000 paired query bootstrap samples with
`numpy.default_rng(20260820)`. The CI uses linear 2.5/97.5 percentiles and
W/T/L tolerance `1e-12`. The report includes seed stability, gain
concentration, the ten largest losses and descriptive candidate-count and
query-length subgroups. Every query has exactly one relevant page, so a
relevance-count split is uninformative. Subgroups are descriptive, not extra
primary tests.

Operational latency/memory acceptance remains separate. R8 alone does not
establish external generalization or a G3 pass.
