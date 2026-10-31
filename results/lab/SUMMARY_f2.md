| Dataset | Variant | Queries | static | QARF | QPAF | QPAF − QARF |
|---|---|---:|---:|---:|---:|---|
| vidoseek | baseline | 970 | 0.8655 | 0.8657 | 0.8609 | -0.0049 [-0.0096, -0.0002] 30/887/53 |
| vidoseek | f2_pwl | 970 | 0.8655 | 0.8625 | 0.8613 | -0.0012 [-0.0051, +0.0026] 39/891/40 |
| vidoseek | f2_pwl_rrf | 970 | 0.8655 | 0.8634 | 0.8607 | -0.0027 [-0.0066, +0.0011] 35/894/41 |
| vimdoc | baseline | 2000 | 0.9586 | 0.9611 | 0.9613 | +0.0002 [-0.0027, +0.0032] 42/1910/48 |
| vimdoc | f2_pwl | 2000 | 0.9586 | 0.9623 | 0.9602 | -0.0021 [-0.0042, +0.0000] 16/1948/36 |
| vimdoc | f2_pwl_rrf | 2000 | 0.9586 | 0.9622 | 0.9614 | -0.0007 [-0.0032, +0.0017] 32/1929/39 |

Delta so với `baseline` cùng method: mean [CI95] W/T/L, rồi verdict.

| Dataset | Variant | Method | Delta vs reference | Verdict |
|---|---|---|---|---|
| vidoseek | f2_pwl | QARF | -0.0032 [-0.0066, +0.0001] 18/920/32 | n/a |
| vidoseek | f2_pwl | QPAF | +0.0004 [-0.0041, +0.0050] 56/865/49 | n/a |
| vidoseek | f2_pwl_rrf | QARF | -0.0024 [-0.0051, +0.0002] 19/926/25 | n/a |
| vidoseek | f2_pwl_rrf | QPAF | -0.0002 [-0.0046, +0.0040] 47/883/40 | n/a |
| vimdoc | f2_pwl | QARF | +0.0012 [-0.0008, +0.0032] 31/1947/22 | n/a |
| vimdoc | f2_pwl | QPAF | -0.0011 [-0.0026, +0.0003] 14/1965/21 | n/a |
| vimdoc | f2_pwl_rrf | QARF | +0.0010 [-0.0011, +0.0033] 33/1936/31 | n/a |
| vimdoc | f2_pwl_rrf | QPAF | +0.0001 [-0.0017, +0.0020] 33/1936/31 | n/a |
