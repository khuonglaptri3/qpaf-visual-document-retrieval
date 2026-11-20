### Task 1: Shared data contracts, preparation, evaluation and offline CLI

Files: create src/qpaf/jev/{__init__,contracts,data,evaluation,cli}.py, scripts/run_jev.py, tests/test_jev_contracts.py, tests/test_jev_evaluation.py, tests/test_jev_cli.py, optional small synthetic fixture under tests/fixtures/jev/. No heavy runtime or dependency imports in core.

Interfaces: `load_pairs(path)->dict`, `sha256_file(path)->str`, `load_scores(path,pairs_path)->dict`, `write_scores(path,pairs_path,scores,manifest,details=None)->dict`; `evaluate(bundle,scores,qrels,k=10)->dict` with `mean` and `per_query`; `compare(left,right,seed=20260820,resamples=10000,groups=None)->dict`; `blend_scores(bundle,scores,lam)->list[float]`; `validate_splits(bundle,manifest)->dict`; `main(argv=None)->int`.

- [ ] Write tests first, observe intended RED, then implement contracts and stdlib atomic cache IO; duplicate pairs, missing text, score mismatch/NaN/hash and baseline-without-base_scores must reject.
- [ ] Implement candidate preparation using explicit supplied base/channel scores, preserve label-free top-K selection. Support importing byte-exact F9 pairs. Real F9 bundle bridge must not read sealed qrels or silently invent/re-fit fusion from evaluation labels. Input missing diagnostics should list paths/next command.
- [ ] Implement unit-aware metrics and per-query output; include gold outside pool and full cohort. Test hand-computed ranking, document pooling, duplicate/coverage errors, pure-vs-explicit blend and paired/group bootstrap cases.
- [ ] Implement doctor, prepare, evaluate, compare, demo CLI; doctor/demo/help require no torch/numpy/Modal. Demo data and result metadata clearly synthetic and use toy lexical/known fixture scoring, never Jev labels. Tests run subprocess CLI from arbitrary cwd.
- [ ] Run focused stdlib tests, record RED/GREEN evidence, self-review and commit own paths. Do not modify model/training modules reserved for Task 2.
