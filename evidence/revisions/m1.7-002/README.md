# M1.7 successor governance event for A003

[`governance_events.jsonl`](governance_events.jsonl) adds event
`QPAF-REG-20261021-0015` for the A003 amendment, its frozen protocol hash,
Research Lead approval, Thanh's independent sign-off and effective policy ID.
It is a `governance` / `governance_record` acceptance event, not an experiment
or execution authorization.

The historical M1.7 `experiment_registry.csv` is included by SHA-256 in
`protocol_freeze_manifest.json`. Appending to that file would invalidate the
frozen manifest. This create-once successor ledger follows the existing
`m1.5-002/governance_events.jsonl` pattern and leaves every old row and hash
unchanged. Event `0015` follows the historical registry's `0014`.
