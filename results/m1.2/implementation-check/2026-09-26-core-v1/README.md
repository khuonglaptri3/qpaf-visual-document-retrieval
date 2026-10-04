# M1.2 implementation check — 2026-09-26

**Software checks passed. Evidence kind: synthetic_software_verification.**
No dataset or pretrained model was downloaded, and no Modal compute was started.

## Evidence and commands

- [checks.json](checks.json): full-suite, verification CLI, compile, dependencies
  and tracked diff checks, with exact commands, UTC timestamps and exit codes.
- [full-tests.log](full-tests.log): 69 tests run, 68 passed, one existing audit
  test skipped because the Windows host does not allow unprivileged symlinks.
  All 25 M1.2 tests ran and passed.
- [local-verification.log](local-verification.log): 23 core/config checks plus
  the actual synthetic learning run for both gate granularities.
- [clean-checks.json](clean-checks.json): a new copy of current source files,
  a new virtualenv, CPU dependencies, non-editable package installation, all 25
  M1.2 tests and a second verification run. All commands exited 0.
- [installed-package.log](installed-package.log): module import from the new
  environment's `site-packages`, executed outside the copied source tree.
- [environment-parity.json](environment-parity.json): byte-identical feature,
  prediction, gate-parameter and learning-trace outputs across both environments.

The fresh environment intentionally installed only declared method dependencies.
PyTorch printed a warning about unavailable optional NumPy integration; no NumPy
conversion is used by this core. Its tests and output parity passed. The existing
workspace includes NumPy for Oracle tests. This is a fresh-environment check by
the implementer, not a claim of independent human review or remote CI execution.

## Tests-first record

[before.log](before.log) records the missing method modules before implementation.
[core-first-check.log](core-first-check.log) records the first 23 passing core
and config checks. [cli-before.log](cli-before.log) records the absent verification
CLI; [cli-after.log](cli-after.log) records both integration checks passing after
implementation. The earlier errors are retained reproduction/development evidence.

## What is checked

1. Thirteen features match hand arithmetic, including constant channels, one
   candidate, Unicode query length, ID-based ties, permutation and padding.
2. Nonfinite active values, duplicate IDs, malformed shapes/masks, unsupported
   features and invalid configuration fail explicitly.
3. QARF broadcasts one weight vector per query; QPAF can condition on each page.
   Both use the same parameter shapes and initial values for each architecture.
4. Simplex weights and fused scores match known arithmetic. Padded candidates
   have zero weights/scores and do not change real-page predictions.
5. Pairwise logistic loss matches its closed-form value/derivative, balances
   queries, records skipped queries and rejects an entire batch without pairs.
6. Backpropagation gives finite nonzero gate gradients on an informative fixture;
   input score/feature tensors receive no gradient or optimizer updates.
7. Float64 finite-difference checks pass for both QARF/QPAF with linear and MLP
   gates. A short synthetic SGD run reduces loss for both methods.
8. The CLI emits hash-valid evidence, rejects existing output without changing it,
   and rejects invalid config before creating an output directory.

## Retained runs

- [Local verification](../../local-core-2026-09-26-001/verification/20260925T185407-b9f9151b/verification.md).
- [Fresh-environment verification](clean-evidence/verification/20260925T185555-fe65eac0/verification.md).

The preset uses 42 trainable parameters for each linear gate. Loss values are
fixture sanity checks, not retrieval-quality metrics or QPAF-versus-QARF research
results. Seeds, feature schema, exact inputs, config, source hashes and package
versions are recorded in each run. Independent review is still `pending`.

`hashes.csv` covers this check directory (excluding itself); the two runs also
have their own receipts. `verified-inputs.json` binds the check to source, tests,
config, dependency declaration and CI configuration in the working tree.
