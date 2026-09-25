# M1 repository and audit design

## Intent and authorization

The user approved the research repository structure and name
`qpaf-visual-document-retrieval`, asked to restart their work using the
23–27 September schedule in `TIMELINE_fixed.md`, and requested Gitflow.
Implement that agreed scope directly. Preserve both supplied files.

This is a new repository. Bootstrap it in the supplied workspace; there is
no previous Git history to isolate or reset. Initialize `main`, create
`develop`, implement on `feature/m1-repository-audit`, and integrate the
verified feature into `develop`. Main keeps the initial stable bootstrap.
Future releases and hotfixes follow CONTRIBUTING.md.

## Deliverables and truthful state

Create a Python research skeleton, a runnable M1.4 inventory/hash utility,
tests, an M1 handover structure, and explicit M1.6/M1.8 preparation documents.
Do not implement training, choose a dataset, claim historical experiments,
invent OCR calibration numbers, or sign G1 on another owner's behalf.

Only two planning files were supplied. Missing research code, corpus,
experiment configs and historical runs are gaps in the initial audit.
Empty inventories are not successful research validation. M1.4 remains
PARTIAL until actual assets and provenance are reviewed. M1.6 remains
BLOCKED until corpus/splits/qrels exist; M1.8 policies remain DRAFT until
calibration and protocol inputs are available. Sign-off stays NOT SIGNED.

## Structure

Use `src/qpaf/`, `scripts/`, `tests/`, `configs/`, `data/`, `manifests/`,
`results/`, `docs/` and `evidence/M1_FINAL/`. Preserve the exact seven
handover directory names from the timeline. Other members' directories
contain ownership notes, not fabricated deliverables.

## Audit interface

Python >=3.11; standard library only at runtime and for tests.

`python scripts/audit_repository.py --root . --output
evidence/M1_FINAL/01_repository_audit` creates a new snapshot. It inventories
observed files, emits seven requested files plus machine-readable audit
metadata, and records actual UTC generation time and Git state.

Source/config/data/run classifications describe observed file locations,
not scientific correctness. Research code is still missing when only audit
infrastructure has been authored. Run provenance requires human review.

Hash real bytes with SHA-256 and stream reads. Exclude Git internals,
environments, caches, credentials, generated evidence, and linked paths.
Do not follow symlinks or Windows directory junctions. Reject output outside
the root, refuse an existing output, and record unreadable/changing inputs
as gaps. Never overwrite a previous snapshot.

`--verify <hash_manifest.csv>` recomputes bytes and detects edits, deleted
files, malformed/empty manifests and paths escaping the audited root.
Generation exit 0 means files were generated; it is not M1 acceptance.
Verification exits nonzero for a failed integrity check.

## Verification and publishing

Exercise real filesystem/CLI behavior: known hashes, Unicode paths,
classification, missing assets, exclusion of secrets/output, overwrite
refusal, invalid/outside paths, and tamper detection. Use temporary fixtures.
Run the complete suite and verify the actual generated manifest before
publishing. Snapshot the committed implementation, then commit evidence;
the snapshot commit is the audited source revision, not its own later
evidence commit.

Create a private GitHub repo under the verified active account, push `main`
and `develop`, and make `develop` the default working branch. Do not claim
branch protection, collaborator access, OCR calibration or G1 approval.

