# M4.2 c?a Kh??ng ? ho?n th?nh g?i baseline tr?n d? li?u ch?nh

Ng?y: 23/10/2026. Nh?nh: `feature/m4-2-baseline-freeze`.
Source commit: `363db3f18252a794c5edd9cec4803e1fecccbf83`.
Run: `RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01`.

**Ho?n th?nh k? thu?t deliverable M4.2 tr?n active primary ViDoSeek:** g?i ??u
v?o d?ng chung ?? seal, static fitting tr?n train th?t ?? ch?y, tr?ng s? v?
thi?t l?p c? b?y baseline ?? kh?a v? replay. Owner acceptance ??
`PENDING_USER_REVIEW`, kh?ng t? k? thay Kh??ng.

## 1. M4.2 l? nhi?m v? g??

Workbook Milestones h?ng 49 giao Kh??ng ??ng b?ng baseline inputs v? train-only
settings, b?n giao shared baseline bundle c? ki?m tra static/RRF settings.
Nh?n ??ng cache/candidates/splits M3, ki?m hash v? fairness, fit static tr?n
train, gi? RRF k=60, r?i b?n giao cho Ph?t l?m M4.3/M4.4.

Ph?m vi theo [A002 ?? duy?t](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/amendments_after_import.md)
v? [M2.5](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/docs/03_method/m2.5-baselines-statistics-leakage.md).
L??t ??u g?n thi?u cache ViMDoc th?nh blocker cho to?n M4.2 l? nh?m ph?m vi.
`m4.2-001` gi? nguy?n nh? preparation ViMDoc l?ch s?; k?t qu? active-primary
th?c t? ???c append ri?ng ? **m4.2-002**.

## 2. K?t qu? fit th?t

| Th?ng s? | K?t qu? |
|---|---:|
| Train query | 799 |
| Train candidate rows | 386.390 |
| Grid ?? duy?t | 66 b?, b??c 0.1 |
| **BM25 weight** | **0.0** |
| **BGE-M3 weight** | **0.1** |
| **ColQwen2.5 weight** | **0.9** |
| **Mean train page nDCG@10** | **0.8642244283102866** |
| Train relevant-page recall | 1.0 |
| Uncovered train queries | 0 |
| Th?i gian seal/load/fit | 265,69 gi?y, CPU local |

G?i nguy?n `qpaf.m25.baselines.fit_static_on_train` v? evaluator M2.4, kh?ng
??i grid/objective/tie rule ?? ch?n k?t qu?. Replay ??c l?p b?ng NumPy tr?n
**c?ng 66 ?i?m** cho ??ng tr?ng s?; objective l?ch **3.33e-16**, d??i 1e-12.
[To?n b? 66 ?i?m](../results/m4.2/verification/independent-grid-replay/train_grid.csv).

??y l? objective train ?? ch?n tham s?, kh?ng ph?i held-out performance,
strongest-baseline selection hay k?t lu?n QPAF ?? v??t baseline.

## 3. G?i b?n giao ?? kh?a

- ??ng `EXPANSION-001` M3.1: **551.764 rows / 1.142 query**; 2.075 trang b? sung;
  t?i ?a 579 candidates/query, d??i cap 600.
- Raw/normalized/candidate/top-list hashes kh?p byte. Normalization replay l?ch
  l?n nh?t **0.0**; top-list raw scores c?ng ??i chi?u v?i common cache.
- Split **799 train / 171 validation / 172 test**. Fitter ch? nh?n train IDs v?
  train records. Development qrels ???c ki?m role; validation kh?ng t?nh metric
  ho?c d?ng ?? ch?n tr?ng s?.
- ?? **b?y contracts** c?ng shared-input SHA-256: BM25, BGE-M3, ColQwen2.5,
  uniform CombSUM, RRF k60, train-fitted static v? learned QARF.
- QARF bind checkpoint ?? ???c Thanh ch?p nh?n ? M3.3, seed 20260820, SHA-256
  `e44ac1a4f3887700a70914fdba8a3e7b35330244e746253d1cd828508be30914`.
- Bundle ch?a cache, candidates, top lists, expansion log, development qrels,
  query texts, split IDs, checkpoint v? manifest. Test qrels ch? ???c hash,
  **kh?ng deserialize v? kh?ng ??a v?o archive**.

Run manifest SHA-256:
`4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86`.

- [Verification m4.2-002](../evidence/revisions/m4.2-002/verification.json).
- [Run manifest](../results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/manifest.json).
- [Tr?ng s?](../results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/train_fit.json).
- [B?y contracts](../results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01/baseline_contracts.json).
- [Archive b?n giao v? checksum](../evidence/revisions/m4.2-002/delivery.json).

Archive n?m ? `.cache/m42-delivery/`, g?m c? Parquet/checkpoint ?ang ???c Git
ignore, kh?ng ch? metadata. CRC archive ?? ki?m.

## 4. Ki?m th? v? review

**45/45 test li?n quan PASS**, g?m active-primary runner, M2.5, M4.1 v? g?i
preparation c?. Review ??c l?p ph?t hi?n m?t l?i provenance khi nh?n root kh?c
executing checkout; ?? t?i hi?n RED, s?a v? ki?m GREEN. B? sung ki?m top-list
score/common cache theo c?ng chu tr?nh.

Full suite: **894 passed, 29 failed, 2 skipped; 310 subtests passed**. Ch?y l?i
??ng 28 failing test nodes tr?n base s?ch `5bbb2de` trong c?ng m?i tr??ng cho
**29 failed, 1 passed**, c?ng t?p failure. S?u failure do PDFium cache 5.14.0
kh?c c?u h?nh c? 4.30.0; 23 c?n l?i l? historical hash/environment drift.
Full suite kh?ng ???c ghi l? xanh. [Log](../results/m4.2/verification/active-primary-full-pytest.txt),
[base comparison](../results/m4.2/verification/active-primary-base-comparison.json).

L?nh fit ?? l?u manifest v? `_SUCCESS.json`, sau ?? CLI exit 1 v? default
Windows charmap kh?ng in ???c t?n ti?ng Vi?t. Kh?ng ch?y l?i fit. SHA-256,
selected objective v? to?n grid ??u ?? replay; verify v?i `-X utf8` exit 0.
[Execution receipt](../evidence/revisions/m4.2-002/execution_receipt.json) gi?
nguy?n l?i reporting, kh?ng che invocation ban ??u.

L?nh verify ch? ??c:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/run_m42_active_primary.py --output results/m4.2/RUN-QPAF-M4_2-CAL-001-20261023T150631Z-A01 --verify --expected-manifest-sha256 4752eef37d7c6cf73eb36717bd352e21192d112b1464a3f5a61dab86bcc76b86
```

## 5. Ngu?n ?? ?p d?ng

- [M2.5 freeze](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/configs/m2.5/freeze.json):
  grid, roster, objective, tie v? RRF settings c?a d? ?n.
- [Cormack et al., SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf):
  c?ng th?c RRF, k=60 c? ??nh sau pilot trong nghi?n c?u g?c.
- [scikit-learn Data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage):
  fitted component ch? h?c t? train, d? li?u ??nh gi? ? ngo?i fitting.
- [A003 fairness](https://github.com/khuonglaptri3/qpaf-visual-document-retrieval/blob/5bbb2ded966ac53328109358420c9bc9f731eb58/evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A003.md):
  baseline d?ng c?ng expanded pool v?i matched learned runs.

## 6. Ranh gi?i b?n giao

G?i M4.2 active-primary s?n s?ng ?? Ph?t nh?n l?m M4.3/M4.4. Validation ch?n
strongest baseline, ??nh gi? test v? scientific claim ch?a ???c ch?y ? ??y.
ViMDoc confirmation v?n ??ng theo M4.1; ngh?a v? baseline ViMDoc trong seal
c? v?n pending cho execution ri?ng. K?t qu? ViDoSeek kh?ng ??ng ngh?a v? ??.
Gi? nguy?n sign-off l?ch s? M3.1/A003. Ch?a push, m? PR ho?c merge.
