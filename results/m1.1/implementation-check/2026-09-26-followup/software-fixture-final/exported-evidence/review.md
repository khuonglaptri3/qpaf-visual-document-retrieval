# New M1.1 Oracle run

This is a new study with recorded inputs, not a reproduction of the historical Exploratory-24.
Queries: 2. Corpus pages: 3. Metric: nDCG@10.

| Weight set | Global | QARF | QPAF | Delta | CI95 | W/T/L |
| --- | --- | --- | --- | --- | --- | --- |
| W7 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | [0.0, 0.0] | 0/2/0 |
| W66 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | [0.0, 0.0] | 0/2/0 |

Binary per-page Oracle maximizes relevant scores and minimizes nonrelevant scores.
Weight sets containing all three simplex vertices have the same QPAF optimum.
The historical report has different W7/W66 QPAF values; its exact solver and inputs
were not supplied. That difference remains unresolved and is not a reproduction target.
Global selects weights using all study labels and is also an Oracle, not a deployable baseline.
No learned QPAF performance is measured. Historical study scopes are not pooled here.
Independent review by another team member: PENDING.
