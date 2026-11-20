# Task 3 implementation report

On 2026-11-20, the controller authorized resuming Task 3 in the managed worktree on `implementation/jev-team-kit-20261120` at `3362d388e369f0cf48c31a5737ebd3b6ab6ecae9`. The work used the agreed [task brief](task-3-brief.md), [spec](../../superpowers/spec.md), and [plan](../../superpowers/plan.md). The earlier agent left a partial test file and no Task 3 implementation. I retained the tests, corrected the missing-map test so it passes the incomplete map to the CLI, and added an embedded-map case before implementation.

Read Superpowers 7.0.1 `using-superpowers/SKILL.md` and `using-superpowers/references/codex-tools.md` from `C:/Users/lanph/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/`. Applied `test-driven-development/SKILL.md` with `test-driven-development/writing-good-tests.md` for the subprocess regressions and `verification-before-completion/SKILL.md` for the final commands. The controller owns the agreed planning and review phases. Read Modal skill 1.5.5 from `.agents/skills/modal/SKILL.md` in the source workspace. The runbook uses the installed Modal SDK command help and official documentation. [Modal Volumes](https://modal.com/docs/guide/volumes) · [Modal CLI](https://modal.com/docs/reference/cli/volume)

## Delivered

- All three wrappers use Python 3.11 standard-library workflows and work with an arbitrary working directory. The default run creates a unique Git-ignored evidence folder for its owner. Explicit shared CLI subcommands use the caller's file arguments. A manual demo output directory must be new.
- Phát's demo partitions a synthetic F9 pairs file, emits prepared pairs, a split/group manifest and a byte-bound baseline cache, then runs doctor on the cache. Thanh's demo compares an explicit supplied baseline with lexical overlap. Its per-query JSON and paired CSV are synthetic. Khương's demo exports one positive and one negative train page and produces matched dry-run argv for Kev and base initialization.
- `evaluate --qrels-format vimdoc-dev` reads only the explicit file at `--qrels`. It requires development roles `train` and `validation`, a complete page-to-document map, and positive document ID lists. Sources with duplicate JSON keys, queries appearing in both roles, repeated documents in a query or disagreement with the prepared partition fail. The adapter preserves out-of-pool positives, and the evaluator max-pools page scores by document. Existing flat inputs and train-page labels retain their own formats.
- `compare` rejects different external `units_sha256` values when both reports know the hash. A missing or unknown hash preserves compatibility with legacy reports.
- The Vietnamese [runbook](../../README.md) links from the root README and docs index. It specifies private inputs and separate Python 3.13 runtimes for Parquet, models, and Modal. It gives Windows and Linux setup, baseline cache use, ViMDoc native development evaluation, local/Modal scoring, matched train commands, and the upstream one-cycle edge at exactly ten effective steps. Concurrent Modal jobs use separate Volumes, including their model caches.

## Verification

- RED. `python -I -S -m unittest discover -s tests -p test_jev_owner_workflows.py` on Python 3.11.16 exited 1. Ten test methods produced 18 failures with parameterized subtests. Absent wrapper scripts and the unsupported format flag accounted for workflow and adapter failures. Compare also returned success with two different known unit-map hashes. On this Windows host the `py` launcher was unavailable, so this recorded run used the installed uv Python 3.11 interpreter directly. [RED log](../task-3-red.log)
- GREEN. The same focused test command passed all ten tests. `python -I -S -m unittest discover -s tests -p "test_jev_*.py" -v` exited 0 on Python 3.11.16 with 60 passes, four skips and 64 total. Skips covered the optional model integration, Windows directory-symlink permissions, and two native Parquet tests. [Isolated suite log](../task-3-green.log)
- `python -I -m unittest discover -s tests -p "test_jev_*.py" -v` exited 0 with the existing Python 3.13.7 and PyArrow 26.0.1 runtime. Both native Parquet tests passed. The result was 62 passes and two skips for model opt-in and Windows symlink permissions. [Parquet suite log](../task-3-parquet.log)
- `python -I -S scripts/run_jev_phat.py`, `python -I -S scripts/run_jev_thanh.py`, and `python -I -S scripts/run_jev_khuong.py` each exited 0 with their default evidence paths. Independently inspected synthetic flags, pairs/cache SHA-256 alignment, Thanh's toy metric values, Khương's label counts and dry plans, and absence of checkpoint directories. Both runbook Modal previews exited 0 without an SDK. [Demo and preview log](../task-3-demos.log)

Self-review checked the accepted scope against the staged paths, source bytes, whitespace, task layout, artifact links, and two planning entry points. Task 1 has the legacy full-project suite's named failures and environment limits. Task 2 has prior real CPU forward passes and a one-step train/reload using small synthetic models. This task reran the Jev suite and Parquet fixtures. [Task 1 report](task-1-report.md) · [Task 2 report](task-2-report.md)

Private data paths, full-size model weights, GPU jobs, and model quality remain unverified. The controller owns independent review, owner brief updates, fresh clone smoke, publication, and remote verification.

## Source and evidence SHA-256

~~~text
9c8154e9e4d89eedcdb93b13bda176eadf76a497408b3347aa7a4cb4bee57938  README.md
4efaa1cab15d926368e3807c107685026b174d1085246ca88bf8128147309cc7  docs/README.md
a5b3de96e78ebe97ef4e1b871feaa0efcfa00a9b72b3fd65ea550691923b00b0  docs/reports/tasks/jev-runnable-team-kit-20261120/README.md
127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933  docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/.gitignore
2302bd4b9bd7203ab6009533493e8b636ee558011bda1801476767927b544c9b  docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/task-3-red.log
6da24444ae12925358c61bda5faaae8377f952e12614f36e779538080d5df865  docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/task-3-green.log
f45d6d346a041306b5ceffb1493667d2c55697c10efcb59e4c71ef64753a158b  docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/task-3-parquet.log
9b1f803c729fbbb2f88d6f59546639ae62de46248e79e4b8784e1972fa617ee7  docs/reports/tasks/jev-runnable-team-kit-20261120/evidence/task-3-demos.log
97e66ea6b0f22aed9fb3a6a341afc89312e66633bd285f165211658983e65afe  configs/jev/phat.json
b43b93e47058b5c088c2bc626639d37dcc01fb9b4415b9b7b770fd3a4c1c862e  configs/jev/thanh.json
74b3c2459525bf4307e179b24d2c54e12becbd680dcafdb0a4b445478c49a7c9  configs/jev/khuong.json
2789173a2588a2c24ab8abcb24cdae3182e261eeab14bae90fc985f1a19207a9  scripts/run_jev_phat.py
e1fbfbcbb373df35b1c9fe35080eaa6fae4cc17e0dbc2ae2140355649d8ccc0d  scripts/run_jev_thanh.py
37f84fa4fe89b57abb50d88625c5ce2eff89c3fd07cdb4183ebd76e0154d2cf4  scripts/run_jev_khuong.py
4ee0e8f1a99c8c8e38a5fde46a1f85e3d2e277b4bd282d804959229b22aa9fcf  src/qpaf/jev/cli.py
3f78caf1d7cdfb183676cdd7310f1b813536a358fcb9dd8be6c74ba8873e9db5  src/qpaf/jev/data.py
98885d2485e54922107240b50837c22f345bebda8b5d918f969c03ca3a05fc51  src/qpaf/jev/evaluation.py
d43f4ae2b96503e0a54176dd2c6aae548c1b83145e6ad335337002bfd3567575  src/qpaf/jev/owners.py
c7ae0e78606be97b2d15ca46ba061da4e14a33c034a4bf1338bdd1d2d8e2e66e  tests/test_jev_owner_workflows.py
~~~

## Review fix round 1

On 2026-11-20, the [Task 3 review](task-3-review.md) identified that the documented matched baseline read a saved score cache and reported `score_mode: pure`. I followed Superpowers 7.0.1 `receiving-code-review/SKILL.md` and `subagent-driven-development/references/fix-loop.md`. The runbook now records the matched baseline via `--baseline` and checks the separately saved cache with `doctor`. The saved-cache reuse explanation documents its mode.

Using Python 3.11.16 under `-I -S`, I ran the following commands. `$run` was the ignored synthetic run directory printed by Thanh's wrapper and `$priv` pointed to the same directory. I copied `$run/qrels.json` to `$priv/dev-page-qrels.json` to run the documented path.

~~~powershell
python -I -S scripts/run_jev_thanh.py
Copy-Item -LiteralPath "$run/qrels.json" -Destination "$priv/dev-page-qrels.json"
python -I -S scripts/run_jev.py score --backend baseline --pairs "$run/prepared/pairs.json" --out "$run/base.json"
python -I -S scripts/run_jev.py evaluate --pairs "$run/prepared/pairs.json" --scores "$run/base.json" --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/baseline-eval.json"
python -I -S scripts/run_jev.py doctor --pairs "$run/prepared/pairs.json" --scores "$run/base.json"
python -I -S scripts/run_jev.py evaluate --pairs "$run/prepared/pairs.json" --baseline --qrels "$priv/dev-page-qrels.json" --k 10 --out "$run/baseline-eval.json"
~~~

Each CLI invocation exited 0. Score wrote four values. Doctor printed `Score length, values and input hash verified.` The two evaluation runs wrote `baseline-eval.json`. The following values were read from the successive JSON reports. Per-query metrics also matched exactly. The fixture reports had `synthetic: true`.

~~~text
--scores report: {"score_mode":"pure","mean":{"ndcg@10":0.5088912804029996,"mrr@10":0.5,"recall@10":0.75,"recall@20":0.75}}
--baseline report: {"score_mode":"baseline","mean":{"ndcg@10":0.5088912804029996,"mrr@10":0.5,"recall@10":0.75,"recall@20":0.75}}
~~~

The fix changed runbook text and this evidence report. The focused CLI verification covers the changed example. Staged whitespace verification passed.

~~~text
b31fbf2e36abfcfebf0d698be6731e66b742fda5d95af46bbd38205c737fa8e6  docs/reports/tasks/jev-runnable-team-kit-20261120/README.md
~~~
