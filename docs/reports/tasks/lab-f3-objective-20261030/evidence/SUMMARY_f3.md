| Dataset | Variant | Queries | static | QARF | QPAF | QPAF − QARF |
|---|---|---:|---:|---:|---:|---|
| vidoseek | baseline | 970 | 0.8655 | 0.8657 | 0.8609 | -0.0049 [-0.0096, -0.0002] 30/887/53 |
| vidoseek | f3_approxndcg | 970 | 0.8655 | 0.8665 | 0.8631 | -0.0034 [-0.0061, -0.0007] 19/921/30 |
| vidoseek | f3_topk_hard | 970 | 0.8655 | 0.8643 | 0.8616 | -0.0028 [-0.0079, +0.0023] 44/869/57 |

Delta so với `baseline` cùng method: mean [CI95] W/T/L, rồi verdict.

| Dataset | Variant | Method | Delta vs reference | Verdict |
|---|---|---|---|---|
| vidoseek | f3_approxndcg | QARF | +0.0007 [-0.0013, +0.0028] 12/946/12 | n/a |
| vidoseek | f3_approxndcg | QPAF | +0.0022 [-0.0018, +0.0062] 47/887/36 | n/a |
| vidoseek | f3_topk_hard | QARF | -0.0014 [-0.0036, +0.0007] 8/949/13 | n/a |
| vidoseek | f3_topk_hard | QPAF | +0.0007 [-0.0006, +0.0021] 15/942/13 | n/a |
