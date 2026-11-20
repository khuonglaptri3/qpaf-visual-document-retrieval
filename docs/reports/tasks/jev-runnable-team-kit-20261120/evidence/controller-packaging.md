# Controller packaging verification, 2026-11-20

Applied the installed Superpowers 7.0.1 `systematic-debugging/SKILL.md` before correcting administrative helpers. These are evidence-packaging checks, not product TDD or additional model execution.

- `finalize_artifacts.py --write` initially passed its working-tree checks, but subsequent `git diff --cached --check` exited 2 on the generated JSON. Raw-byte inspection found 41/41 lines in validation.json and 436/436 in hashes.json used CRLF, while the helper source and `verify_delivery.py` used LF. The finalizer's `Path.write_text` lacked the explicit LF argument already used by the other administrative helpers. Added `newline="\n"` to both writes, regenerated the two outputs, and checked the full delivered diff against the pinned F9 base. `git diff --cached --check` then exited 0. No historical source/evidence bytes were normalized.
- A separate fresh shallow local clone reproduced missing-base availability: `git cat-file -e 842176c5b707298672629738390a09e222f47e86` exited 1 after depth-one clone. The finalizer needs this exact base for frozen-source comparison. Fetching only that pinned base from the same local source changed the command to exit 0. The delivery helper now records that explicit local fetch before validation; it does not fetch models or corpus data.

The common bundle's seven initial layout/link/provenance/source/whitespace checks passed after correction. Owner output validation and publication remain subsequent checks, recorded separately when executed.
