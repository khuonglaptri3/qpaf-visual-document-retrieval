| Block | Method | Rank | nDCG@10 | R@1 | R@3 | MRR@10 | Co-strongest |
|---|---|---:|---:|---:|---:|---:|---|
| deployable | bm25 | 7 | 0.725095 | 0.549708 | 0.736842 | 0.665314 |  |
| deployable | bge_m3 | 5 | 0.763862 | 0.584795 | 0.795322 | 0.705518 |  |
| deployable | colqwen25 | 2 | 0.869296 | 0.736842 | 0.912281 | 0.830472 |  |
| deployable | uniform_combsum | 3 | 0.841254 | 0.695906 | 0.894737 | 0.797034 |  |
| deployable | rrf_k60 | 4 | 0.829366 | 0.678363 | 0.877193 | 0.781651 |  |
| deployable | train_fitted_static | 1 | 0.871414 | 0.736842 | 0.918129 | 0.833062 | yes |
| deployable | learned_qarf | 6 | 0.752147 | 0.584795 | 0.783626 | 0.696888 |  |
| proposed | qpaf (frozen) | | 0.866280 | 0.736842 | 0.906433 | 0.828279 | not eligible |

- Learned QARF and QPAF checkpoints were selected on this validation split; their numbers are optimistic.
- Single seed 20260820; not the three-seed confirmatory result.
- Oracle rows are reported separately (QPAF-M4_4-ORC-001) and never enter selection.
