# Repository bootstrap decisions and verification

This record describes software preparation, not research acceptance.

- The user approved the repository name/structure, instructed the M1 restart,
  and requested Gitflow. Implementation is in the supplied new workspace,
  with `main` as bootstrap and the feature integrated into `develop`.
- Both supplied planning files are preserved byte-for-byte. Their hashes are
  part of M1.4; dates are actual execution timestamps, not backdated evidence.
- GitHub visibility defaults to private because public visibility was not
  requested. The owner can change this later. No collaborator identity is
  invented, and documented review rules are not claimed as enforced protection.
- Git writes require the host execution context because `.git` is read-only
  in the sandbox. The two Windows contexts use different accounts, so host Git
  commands trust only this exact repository per command; no global Git trust
  or global author settings were changed.
- A fresh software reviewer found two issues: Python 3.11 junction exclusion
  and a stale hash after same-size/mtime file replacement. Both were reproduced
  by regression tests before fixes. The fix pass also covered differing Windows
  `stat`/`fstat` change-time semantics. No Minor findings were deferred.
- Local suite after fixes: 15 tests, 14 passed, 1 skipped because this host
  disallows unprivileged symlinks. A real junction test passes. CI includes
  Ubuntu/Python 3.11 and Windows/Python 3.11/3.14; its actual results are separate
  from these local results and must be checked on GitHub.
- Actual snapshot hashes and remote branch identity are verified after creation.
  The software review cannot substitute for Thanh's independent evidence audit
  or Phát's protocol/G1 approval. Missing assets remain explicit gaps.

If these assumptions change, update the relevant docs on a new feature branch
and generate a new audit snapshot; preserve existing snapshots.

## Team handoff from M1.1 and M1.2

The owner subsequently requested publication of the research documents and
detailed README assignments for Thanh (M1.1) and Phát (M1.2). This is a
documentation/reference handoff; method core, Oracle reproduction and data
payloads are deliverables for the assigned teammates.

- The earlier environment/Git notes above describe bootstrap execution.
- The supplied workbook and timeline remain unchanged. Current handoff
  status is explicit in README and `docs/m1-restart-handoff.md`, because
  the historical Done cells are not a verification of this checkout.
- A later supplied Oracle progress report contains reported ViDoSeek
  results. Its original bytes are stored in `results/m1.1/reference/`,
  with an import timestamp and SHA-256. Import time is not run time.
- Reported aggregate metrics remain separate from reproduced per-query
  evidence. No raw Oracle outputs, corpus, method implementation or
  independent QA sign-off are fabricated.
- The handoff uses a feature branch from `develop`. A new snapshot at
  `evidence/revisions/m1.4-002-handoff/` records the committed source tree;
  its evidence commit follows the audited source commit.
- The original audit snapshot is preserved. Verify historical snapshots
  against their recorded source revision, not a later modified README.
