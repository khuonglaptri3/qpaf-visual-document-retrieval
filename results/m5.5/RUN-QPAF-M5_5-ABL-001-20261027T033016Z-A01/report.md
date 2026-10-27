# M5.5 CPU diagnostics

Validation only; no refit or primary-method change.

| Method | nDCG@10 | R@1 | R@3 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| bm25 | 0.725095482 | 0.549707602 | 0.736842105 | 0.665313747 |
| bge_m3 | 0.763862176 | 0.584795322 | 0.795321637 | 0.705518426 |
| colqwen25 | 0.869295567 | 0.736842105 | 0.912280702 | 0.830472013 |
| uniform_combsum | 0.841254122 | 0.695906433 | 0.894736842 | 0.797034252 |
| without_bm25 | 0.861483172 | 0.725146199 | 0.894736842 | 0.820214889 |
| without_bge_m3 | 0.821954896 | 0.666666667 | 0.865497076 | 0.773503202 |
| without_colqwen25 | 0.789199445 | 0.619883041 | 0.830409357 | 0.732827439 |
| uniform_zscore | 0.845281771 | 0.695906433 | 0.888888889 | 0.800663696 |

R5-01/02/03: technical PASS; independent human review pending.
R5-04: NOT_RUN_DEFERRED_MODAL_NETWORK_BLOCKED. Full M5.5 remains partial.
Historical M3.6 measurements are context, not a new M5.5 result.
