# M2.7 Matched QARF/QPAF Configs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze one shared base config plus a matched manifest for QARF/QPAF and prove, fail-closed, that the only semantic difference is gate granularity.

**Architecture:** `configs/m2.7/shared_base.toml` (M2.4 schema, M2.4 values) is run by both methods; `configs/m2.7/matched.json` pins hashes, seeds, runtime and budget. `src/qpaf/m27/matched.py` loads/validates/resolves and runs seven parity checks; `scripts/verify_m27_matched.py` writes create-once evidence to `evidence/revisions/m2.7-001/`.

**Tech Stack:** Python 3.13 stdlib (`tomllib`, `json`, `hashlib`), PyTorch (checks 5–6 only), `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-20-m27-matched-configs-design.md`

## Global Constraints

- Branch `feature/m2-7-matched-configs`; commits carry no Claude/Co-Authored-By attribution lines (user rule).
- Experiment ID `QPAF-M2_7-MTH-001`; status string `FROZEN_CONFIG_PENDING_M2.8_INPUTS`; pending sentinel `PENDING_M2.8`.
- Base values identical to `configs/m2.4/pipeline.toml` except `experiment_id`; loss authority `QPAF-M1.5-A001`.
- Seeds: development gate `20260820`; robustness `[20260820, 20260821, 20260822]`; override path `training.seed`; valid range `[0, 2**32)`, `int` only (not `bool`).
- Split manifest SHA-256 `ea5a19f93dce07cce375d6fb6afed630606e00916c5daa10938562aee9cddfad`; M2.5 freeze SHA-256 `317b4333968ae4250e0e9bc71846d37f47e5f958872c8cf27949a0c0d8c3579c`.
- Budget: `wall_time_minutes_per_run = 60`, one invocation per method per seed, zero retries without new authorization, shared by methods.
- Every failure raises `ParityError(ValueError)`; the verifier never reports a partial pass.
- Config files are LF-only and byte-pinned (`/configs/m2.7/** -text -eol`).
- Do not modify the M2.4 runner, M2.4 config, `POAI_Milestone_Group01.xlsx`, `TOM_TAT_GAP_GIANG_VIEN_QPAF.md` or `AGENTS.md`; stage files by explicit path only.
- Tests: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`; full suite `python -m unittest discover -s tests`.

## Review Focus

- Torch not installed → verifier raises `ParityError`, never a report with checks 5–6 missing (test in Task 2).
- Config checked out with CRLF on another machine → base hash mismatch; committed config bytes must contain no `\r` (test in Task 1).
- Seed given as JSON `true` (Python `bool` is an `int`) → rejected (test in Task 1).
- Manifest with a duplicated key (e.g. two `"QPAF"` entries, where `json` silently keeps the last) → rejected (test in Task 1).
- Script run from a different working directory → manifest-relative paths resolve against the repo root, not the cwd (test in Task 3).

---

### Task 1: Frozen configs, manifest loader and semantic diff

**Files:**
- Create: `configs/m2.7/shared_base.toml`, `configs/m2.7/matched.json`, `src/qpaf/m27/__init__.py`, `src/qpaf/m27/matched.py`
- Modify: `.gitattributes` (append after the `/configs/m2.6/full_ocr.toml -text -eol` line)
- Test: `tests/test_m27_matched.py`

**Interfaces:**
- Produces:
  - `class ParityError(ValueError)`
  - `PENDING = 'PENDING_M2.8'`
  - `load_manifest(path: Path) -> dict` — parses with duplicate-key rejection, validates strictly
  - `semantic_diff(left: dict, right: dict) -> dict[str, list]` — dotted path → `[left_value, right_value]`; a one-sided path uses `None` for the missing side
  - `load_base(manifest: dict, root: Path, seed: int | None = None) -> dict` — M2.4-valid config via `qpaf.m24.config.load_config(root/manifest['base_config']['path'])`; when `seed` is given, sets `training.seed` and calls `validate`
  - `resolve(manifest: dict, method: str, seed: int, root: Path) -> dict` — `load_base(...)` plus top-level `gate_granularity` from `manifest['methods'][method]`; unknown method → `ParityError`

- [ ] **Step 0: Record the baseline suite on develop's code**

Run: `python -m unittest discover -s tests > <workspace>/baseline-suite.txt 2>&1; tail -5 <workspace>/baseline-suite.txt`
Expected: a final `OK` or `FAILED (...)` line; record the counts in the ledger as the "no worse than develop" reference.

- [ ] **Step 1: Write the configs**

`configs/m2.7/shared_base.toml`: copy `configs/m2.4/pipeline.toml` byte-for-byte, then change only line 1–2 comment to state "M2.7 frozen shared base for matched QARF/QPAF; `--method` selects gate granularity and nothing else (see configs/m2.7/matched.json)" and `experiment_id = "QPAF-M2_7-MTH-001"`. LF line endings.

Compute `sha256sum configs/m2.7/shared_base.toml` and write `configs/m2.7/matched.json` with exactly the keys and values of the spec's two `matched.json` tables (`base_config.sha256` = the computed hash), indent 2, trailing LF.

Append to `.gitattributes`: `/configs/m2.7/** -text -eol`.

- [ ] **Step 2: Write failing tests** in `tests/test_m27_matched.py`

Header mirrors `tests/test_m24_pipeline.py` (`ROOT`, `sys.path.insert`, `HAS_TORCH`); `MANIFEST = ROOT/'configs/m2.7/matched.json'`. Helper `write_manifest(tmp: Path, data) -> Path` dumps a dict (or raw text) to a temp file.

```python
class ManifestTests(unittest.TestCase):
    def test_committed_manifest_loads(self):
        m = load_manifest(MANIFEST)
        self.assertEqual(m['methods'], {'QARF': {'gate_granularity': 'query'},
                                        'QPAF': {'gate_granularity': 'page'}})
        self.assertEqual(m['allowed_semantic_diff'], ['gate_granularity'])
        self.assertEqual(m['seeds']['robustness'], [20260820, 20260821, 20260822])
        self.assertEqual(m['budget']['wall_time_minutes_per_run'], 60)
        self.assertEqual(m['status'], 'FROZEN_CONFIG_PENDING_M2.8_INPUTS')

    def test_config_files_are_lf_only(self):
        for name in ('shared_base.toml', 'matched.json'):
            self.assertNotIn(b'\r', (ROOT/'configs/m2.7'/name).read_bytes(), name)

    def test_rejects_invalid_manifests(self):
        # each case: (label, mutate(dict) -> None); every one must raise ParityError
        cases = [
            ('unknown top-level key', lambda m: m.update(extra=1)),
            ('missing top-level key', lambda m: m.pop('budget')),
            ('unknown nested key', lambda m: m['runtime'].update(gpu='a100')),
            ('allowed diff widened', lambda m: m.update(allowed_semantic_diff=['gate_granularity', 'training.learning_rate'])),
            ('method set changed', lambda m: m['methods'].pop('QPAF')),
            ('bad granularity', lambda m: m['methods']['QARF'].update(gate_granularity='doc')),
            ('bool seed', lambda m: m['seeds']['robustness'].__setitem__(1, True)),
            ('negative seed', lambda m: m['seeds']['robustness'].__setitem__(1, -1)),
            ('seed too large', lambda m: m['seeds']['robustness'].__setitem__(1, 2**32)),
            ('dev seed outside robustness', lambda m: m['seeds'].update(development_gate=1)),
            ('pending replaced by fake hash', lambda m: m['shared_inputs'].update(qrels='0'*64)),
            ('pending input missing', lambda m: m['shared_inputs'].pop('score_cache')),
            ('bad sha format', lambda m: m['base_config'].update(sha256='ABC')),
        ]
        for label, mutate in cases:
            with self.subTest(label):
                data = json.loads(MANIFEST.read_text(encoding='utf-8'))
                mutate(data)
                with self.assertRaises(ParityError):
                    load_manifest(write_manifest(self.tmp, data))

    def test_rejects_duplicate_keys(self):
        text = MANIFEST.read_text(encoding='utf-8').replace(
            '"QPAF": {', '"QPAF": {"gate_granularity": "query"}, "QPAF": {', 1)
        with self.assertRaises(ParityError):
            load_manifest(write_manifest(self.tmp, text))


class DiffAndResolveTests(unittest.TestCase):
    def test_semantic_diff(self):
        self.assertEqual(semantic_diff({'a': {'b': 1}}, {'a': {'b': 1}}), {})
        self.assertEqual(semantic_diff({'a': {'b': 1}}, {'a': {'b': 2}}), {'a.b': [1, 2]})
        self.assertEqual(semantic_diff({'a': 1}, {'a': 1, 'c': 3}), {'c': [None, 3]})
        self.assertEqual(semantic_diff({'x': {'y': {'z': 'q'}}}, {'x': {'y': {'z': 'p'}}}), {'x.y.z': ['q', 'p']})

    def test_resolve_applies_seed_and_granularity_only(self):
        m = load_manifest(MANIFEST)
        resolved = resolve(m, 'QARF', 20260821, ROOT)
        self.assertEqual(resolved['training']['seed'], 20260821)
        self.assertEqual(resolved['gate_granularity'], 'query')
        validate(load_base(m, ROOT, 20260821))  # still M2.4-valid
        with self.assertRaises(ParityError):
            resolve(m, 'CARF', 20260820, ROOT)
```

`ManifestTests.setUp` creates `self.tmp` via `tempfile.TemporaryDirectory()` + `addCleanup`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'qpaf.m27'`

- [ ] **Step 4: Implement `src/qpaf/m27/__init__.py` and the Task 1 interfaces in `src/qpaf/m27/matched.py`**

`__init__.py`: one docstring line like `src/qpaf/m25/__init__.py` ("M2.7 matched QARF/QPAF configs and parity checks."). In `load_manifest`, parse with `json.loads(..., object_pairs_hook=...)` that raises on a repeated key; validate exact key sets at every level against the spec tables; seeds use `type(x) is int`; hashes match `^[0-9a-f]{64}$`; `json.JSONDecodeError`/`OSError` re-raise as `ParityError`. Style follows `qpaf/m24/config.py` (single quotes, compact checks).

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`
Expected: all Task 1 tests OK.

- [ ] **Step 6: Commit**

```bash
git add .gitattributes configs/m2.7/shared_base.toml configs/m2.7/matched.json src/qpaf/m27/__init__.py src/qpaf/m27/matched.py tests/test_m27_matched.py
git commit -m "feat(m2.7): freeze shared base and matched manifest with strict loader"
```

---

### Task 2: Parity checks

**Files:**
- Modify: `src/qpaf/m27/matched.py`
- Test: `tests/test_m27_matched.py`

**Interfaces:**
- Consumes: Task 1's `load_manifest`, `semantic_diff`, `load_base`, `resolve`, `ParityError`, `PENDING`.
- Produces: `check_parity(manifest: dict, root: Path) -> dict` with exactly these keys:
  - `base_config_sha256: str`
  - `m24_drift: {'experiment_id': ['QPAF-M2_4-PIPELINE-001', 'QPAF-M2_7-MTH-001']}`
  - `pairs: {'20260820': {'gate_granularity': ['query', 'page']}, ...}` (one per robustness seed, string keys)
  - `methods_match_runner: True`
  - `initialization: {'<seed>': {'identical': True, 'parameter_count': int}}`
  - `data_order: {'identical': True, 'steps': int, 'fixture': 'qpaf.m24.synthetic:20260820'}`
  - `shared_inputs: {'split_manifest': {'path': str, 'sha256': str, 'verified': True}, 'm25_freeze': {...same...}}`
  - `pending_inputs: ['candidate_set', 'qrels', 'score_cache']`

Check order and failure messages follow spec §Checks 1–7. Checks 5–6 import `torch` and `qpaf.m24.trainer` inside the function and call `trainer.build_model` / `trainer.train` through the module (so tests can patch them); `ImportError` → `ParityError('torch is required for initialization and data-order parity')`. Check 6 trains one epoch per method (base config with `training.epochs = 1`) on `build_records(*make_fixture(seed), ('train', 'validation'), positive_threshold=..., max_candidates=...)` in a `tempfile.TemporaryDirectory`, under `torch.use_deterministic_algorithms(True)`, comparing `[(s['valid_queries'], s['pairs']) for s in result['steps']]`.

- [ ] **Step 1: Write failing tests**

Helper `make_root(tmp: Path) -> Path` copies into a temp root: `configs/m2.7/shared_base.toml`, `configs/m2.7/matched.json`, `configs/m2.4/pipeline.toml`, `configs/m2.5/freeze.json`, `evidence/revisions/m2.1-002/data_split_manifest.json` (byte copies). Helper `rehash(root)` rewrites `matched.json`'s `base_config.sha256` to the current base bytes.

```python
class ParityChecksTests(unittest.TestCase):  # setUp: self.tmp temp dir
    @unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for parity checks')
    def test_committed_configs_pass(self):
        report = check_parity(load_manifest(MANIFEST), ROOT)
        self.assertEqual(report['m24_drift'], {'experiment_id': ['QPAF-M2_4-PIPELINE-001', 'QPAF-M2_7-MTH-001']})
        self.assertEqual(report['pairs'], {str(s): {'gate_granularity': ['query', 'page']}
                                           for s in (20260820, 20260821, 20260822)})
        self.assertTrue(report['methods_match_runner'])
        for seed, item in report['initialization'].items():
            self.assertEqual(item, {'identical': True, 'parameter_count': 42}, seed)
        self.assertTrue(report['data_order']['identical'])
        self.assertGreater(report['data_order']['steps'], 0)
        self.assertEqual(report['pending_inputs'], ['candidate_set', 'qrels', 'score_cache'])
        self.assertTrue(all(v['verified'] for v in report['shared_inputs'].values()))

    def test_edited_base_fails_hash(self):        # append '\n# edit\n' to base; no rehash
    def test_base_drift_from_m24_fails(self):    # learning_rate = 0.02 in base; rehash
    def test_swapped_granularity_fails(self):    # manifest QARF->page, QPAF->query; message mentions METHODS
    def test_split_manifest_hash_mismatch_fails(self):  # append a byte to the copied split manifest
    def test_second_differing_field_fails(self):
        # patch qpaf.m27.matched.resolve so QPAF gets training.learning_rate 0.02
    @unittest.skipUnless(HAS_TORCH, ...)
    def test_initialization_mismatch_fails(self):  # patch qpaf.m24.trainer.build_model: QPAF seeded seed+1
    @unittest.skipUnless(HAS_TORCH, ...)
    def test_data_order_mismatch_fails(self):      # patch qpaf.m24.trainer.train: QPAF steps reversed
    def test_missing_torch_fails_closed(self):
        with mock.patch.dict(sys.modules, {'torch': None}):
            with self.assertRaisesRegex(ParityError, 'torch is required'):
                check_parity(load_manifest(MANIFEST), ROOT)
```

Each failure test asserts `ParityError` (with `assertRaisesRegex` on a distinctive word from the check's message: `sha256`, `M2.4`, `METHODS`, `split_manifest`, `gate_granularity`, `initialization`, `data order`). Failure tests that fail before checks 5–6 do not need torch.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`
Expected: Task 2 tests ERROR with `ImportError: cannot import name 'check_parity'`; Task 1 tests still OK.

- [ ] **Step 3: Implement `check_parity(manifest: dict, root: Path) -> dict` in `src/qpaf/m27/matched.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`
Expected: all tests OK (none skipped locally; torch is installed).

- [ ] **Step 5: Commit**

```bash
git add src/qpaf/m27/matched.py tests/test_m27_matched.py
git commit -m "feat(m2.7): verify matched QARF/QPAF parity fail-closed"
```

---

### Task 3: Verifier script

**Files:**
- Create: `scripts/verify_m27_matched.py`
- Test: `tests/test_m27_matched.py`

**Interfaces:**
- Consumes: `load_manifest`, `check_parity`, `ParityError`.
- Note: `--manifest` is an addition beyond the spec. It exists only so the exit-2 path is testable without touching committed files; with no arguments the script behaves exactly as the spec says.
- Produces: `main(argv=None) -> int`. CLI: `--manifest PATH` (default `ROOT/'configs/m2.7/matched.json'`; relative paths resolve against `ROOT`) and `--output PATH` (relative to `ROOT`, like M2.5; create-once). The repo root passed to `check_parity` is always `ROOT`. Report = `check_parity(...)` merged with: `task_id`, `experiment_id`, `status` (from manifest), `manifest_sha256`, `source_sha256` for `src/qpaf/m27/matched.py`, `src/qpaf/m24/config.py`, `src/qpaf/m24/trainer.py`, `scripts/verify_m27_matched.py`, `wall_time_cap_minutes` (from `budget`), `independent_review: 'PENDING'`. Output: `json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)+'\n'`, written UTF-8 with `newline='\n'`. `__main__` block copies `scripts/run_m24_pipeline.py:159-167`, catching `(ParityError, FileExistsError)` → `Error: ...` on stderr, exit 2.

- [ ] **Step 1: Write failing tests**

```python
@unittest.skipUnless(HAS_TORCH, 'install requirements-learned-local.txt for the verifier CLI')
class ScriptTests(unittest.TestCase):  # setUp: self.tmp temp dir
    def run_script(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT/'scripts/verify_m27_matched.py'), *args],
                              capture_output=True, text=True, encoding='utf-8', cwd=cwd)

    def test_prints_report_from_any_cwd(self):
        result = self.run_script(cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['independent_review'], 'PENDING')
        self.assertEqual(report['wall_time_cap_minutes'], 60)
        self.assertEqual(report['status'], 'FROZEN_CONFIG_PENDING_M2.8_INPUTS')
        self.assertEqual(set(report['source_sha256']), {'src/qpaf/m27/matched.py', 'src/qpaf/m24/config.py',
                                                        'src/qpaf/m24/trainer.py', 'scripts/verify_m27_matched.py'})

    def test_output_is_create_once(self):
        target = self.tmp/'verification.json'
        self.assertEqual(self.run_script('--output', str(target)).returncode, 0)
        first = target.read_bytes()
        self.assertNotIn(b'\r', first)
        again = self.run_script('--output', str(target))
        self.assertEqual(again.returncode, 2)
        self.assertIn('Error:', again.stderr)
        self.assertEqual(target.read_bytes(), first)

    def test_parity_error_exits_2(self):
        data = json.loads(MANIFEST.read_text(encoding='utf-8')); data['extra'] = 1
        result = self.run_script('--manifest', str(write_manifest(self.tmp, data)))
        self.assertEqual(result.returncode, 2)
        self.assertIn('Error:', result.stderr)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched.ScriptTests -v`
Expected: FAIL — non-zero return code / "can't open file ... verify_m27_matched.py".

- [ ] **Step 3: Implement `scripts/verify_m27_matched.py`** per the Interfaces block; module docstring states it is read-only and opens no labels.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m unittest tests.test_m27_matched -v`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_m27_matched.py tests/test_m27_matched.py
git commit -m "feat(m2.7): add create-once matched-config verifier"
```

---

### Task 4: Evidence and documentation

**Files:**
- Create: `evidence/revisions/m2.7-001/verification.json` (generated), `evidence/revisions/m2.7-001/README.md`, `docs/03_method/m2.7-matched-configs.md`
- Modify: `docs/03_method/README.md` (append one bullet after the M2.4 line), `docs/03_method/m2.4-learned-pipeline.md:7-8` (link "matched config (M2.7)" to `m2.7-matched-configs.md`), `docs/superpowers/README.md` (add an `## M2.7` section above `## M2.6` with spec/plan/evidence links)

- [ ] **Step 1: Run the full suite**

Run: `python -m unittest discover -s tests > <workspace>/task4-suite.txt 2>&1; tail -5 <workspace>/task4-suite.txt`
Expected: no new failures or errors versus Step 0 of Task 1.

- [ ] **Step 2: Generate the evidence from the committed code**

Run: `git status --porcelain -- configs/m2.7 src/qpaf/m27 src/qpaf/m24 scripts/verify_m27_matched.py` → Expected: empty (hashed sources committed).
Run: `PYTHONPATH=src python scripts/verify_m27_matched.py --output evidence/revisions/m2.7-001/verification.json`
Expected: exit 0; file exists; `pairs` has three seeds each `{"gate_granularity": ["query", "page"]}`; `independent_review` `PENDING`.

- [ ] **Step 3: Write the docs** (Vietnamese, style of `docs/03_method/m2.5-baselines-statistics-leakage.md` and `evidence/revisions/m2.5-001/README.md`)

`m2.7-matched-configs.md` sections: header line (Owner: Tấn Phát · Phụ thuộc: G1, M2.4, M2.5 · Config links); matched rule (protocol §4, A001); the two artifacts and what each pins; the seven checks; pilot commands for M3.2/M3.4 exactly as in the spec; seed rule for M5.3/M5.4; wall-time cap 60 minutes with the ~2.4 s/epoch probe measurement labelled synthetic-shape, this machine; verification commands (unittest + script); limits (inputs `PENDING_M2.8`, no real training, review PENDING for M2.10). Evidence README: what `verification.json` records, its create-once nature, status and pending inputs.

- [ ] **Step 4: Verify links resolve**

Run: `python -I -c "import re,pathlib,sys;bad=[(f,l) for f in sys.argv[1:] for l in re.findall(r'\]\(([^)#]+)\)',pathlib.Path(f).read_text(encoding='utf-8')) if not l.startswith('http') and not (pathlib.Path(f).parent/l).exists()];print(bad or 'links OK')" docs/03_method/m2.7-matched-configs.md docs/03_method/README.md docs/03_method/m2.4-learned-pipeline.md docs/superpowers/README.md evidence/revisions/m2.7-001/README.md`
Expected: `links OK`

- [ ] **Step 5: Commit**

```bash
git add evidence/revisions/m2.7-001/verification.json evidence/revisions/m2.7-001/README.md docs/03_method/m2.7-matched-configs.md docs/03_method/README.md docs/03_method/m2.4-learned-pipeline.md docs/superpowers/README.md
git commit -m "docs(m2.7): record matched-config verification evidence"
```

**Evidence revision rule:** if the final whole-branch review's fix pass changes any file hashed in `verification.json` (`configs/m2.7/*`, `src/qpaf/m27/matched.py`, `src/qpaf/m24/config.py`, `src/qpaf/m24/trainer.py`, `scripts/verify_m27_matched.py`), do not overwrite m2.7-001: generate `evidence/revisions/m2.7-002/` and point the docs to it, per the repo's "revision mới khi sửa" rule.
