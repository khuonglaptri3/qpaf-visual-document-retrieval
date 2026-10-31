| Dataset | Variant | Queries | static | QARF | QPAF | QPAF − QARF |
|---|---|---:|---:|---:|---:|---|
| vidoseek | baseline | 970 | 0.8655 | 0.8657 | 0.8609 | -0.0049 [-0.0096, -0.0002] 30/887/53 |
| vidoseek | f1_content | 970 | 0.8655 | 0.8633 | 0.8601 | -0.0032 [-0.0084, +0.0019] 38/883/49 |
| vidoseek | f1_content_mlp | 970 | 0.8655 | 0.8632 | 0.8596 | -0.0036 [-0.0092, +0.0021] 46/870/54 |
| vimdoc | baseline | 2000 | 0.9586 | 0.9611 | 0.9613 | +0.0002 [-0.0027, +0.0032] 42/1910/48 |
| vimdoc | f1_content | 2000 | 0.9586 | 0.9609 | 0.9590 | -0.0019 [-0.0052, +0.0014] 39/1911/50 |
| vimdoc | f1_content_mlp | 2000 | 0.9586 | 0.9602 | 0.9568 | -0.0034 [-0.0074, +0.0006] 56/1884/60 |

Delta so với `baseline` cùng method: mean [CI95] W/T/L, rồi verdict.

| Dataset | Variant | Method | Delta vs reference | Verdict |
|---|---|---|---|---|
| vidoseek | f1_content | QARF | -0.0024 [-0.0059, +0.0010] 18/922/30 | n/a |
| vidoseek | f1_content | QPAF | -0.0008 [-0.0041, +0.0024] 23/917/30 | n/a |
| vidoseek | f1_content_mlp | QARF | -0.0025 [-0.0065, +0.0015] 23/916/31 | n/a |
| vidoseek | f1_content_mlp | QPAF | -0.0013 [-0.0046, +0.0020] 28/918/24 | n/a |
| vimdoc | f1_content | QARF | -0.0002 [-0.0031, +0.0027] 41/1923/36 | n/a |
| vimdoc | f1_content | QPAF | -0.0023 [-0.0055, +0.0008] 43/1911/46 | n/a |
| vimdoc | f1_content_mlp | QARF | -0.0010 [-0.0041, +0.0022] 43/1909/48 | n/a |
| vimdoc | f1_content_mlp | QPAF | -0.0046 [-0.0085, -0.0007] 53/1888/59 | n/a |
