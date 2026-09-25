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
