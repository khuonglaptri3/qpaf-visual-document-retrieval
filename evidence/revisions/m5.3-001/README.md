# M5.3 — matched QARF seed 20260821 (R3, first half)

**Owner:** Tấn Phát. **Status:** authorization `DRAFT_PENDING_APPROVAL`; nothing has been run.
The matched QPAF seed-2 run is a separate authorization (`m5.3-002`) that the supervisor refuses
until this QARF run carries an accepted independent review.

- [`authorization.json`](authorization.json): drafted from the approved seed-1 M3.2 authorization.
  The sealed inputs, metric, runtime, hardware, limits and command are copied exactly. Only the config
  path, the output root and the seed (`20260821`) differ.
- Seed config [`configs/m5.3/shared_base_seed_20260821.toml`](../../../configs/m5.3/shared_base_seed_20260821.toml)
  (SHA-256 `d34cb2ee…936c`): the frozen M4.3 `shared_base.toml` bytes with only the seed digits changed.
  Its parsed form equals the M5.2 receipt matrix entry for seed `20260821` (`cache_identity.json`
  `960aed61…3291`).

## What the supervisor adds to the M3.2 mechanics

`src/qpaf/m53/supervisor.py` reuses the M3.2 single-attempt helpers and the M3.4 section names
unchanged. Before the seal check it refuses unless:

- the M5.1 preregistration and confirmation, the M5.2 receipt and the M4.3 freeze match their pins;
- the ten frozen method sources still hash as in the M4.3 freeze;
- the config is the M5.2 receipt config for this seed and method;
- the authorization equals the seed-1 run of the same method in everything except the config and the output root.

For QPAF, it also needs an `ACCEPTANCE_RECORDED`/`PASS` review of the seed-2 QARF run. The QPAF
authorization may differ from that run's only in the method.

After the run, it requires the following before it writes `_SUCCESS.json`:

- the seed-1 `data_manifest.json`, byte for byte (`890f2709…8ddd`);
- the seed-1 provenance inputs, with only the config hash replaced;
- a fresh-process reload of `best.pt` and `last.pt` in a separate interpreter
  (`scripts/reload_m53_checkpoint.py`). Every value must be finite, and the validation scores, weights
  and metrics must match within `1e-7`. The reload report is stored inside `_SUCCESS.json`.

The reload worker reproduced both seed-1 runs exactly before this draft: QARF `e44ac1a4…0914` and
QPAF `e4b00ab4…5c8e`, with score, weight and metric differences all `0.0`.

## Checks

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_m53_supervisor -v
```

The test suite includes read-only checks against the real pins, so a drifted pin fails the tests.
No test trains a model or opens the sealed test qrels.
