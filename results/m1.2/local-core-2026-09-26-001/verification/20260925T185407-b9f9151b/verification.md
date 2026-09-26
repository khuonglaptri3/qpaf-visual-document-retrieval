# M1.2 method-core verification

**Software verification: PASS. Kind: synthetic_software_verification.**

Unit tests: 23, failures: 0, errors: 0, skipped: 0.
Feature schema: qpaf13_v1; 13 label-free features.
Gate: linear; query pooling for QARF, per-page conditioning for QPAF.
Inputs, feature construction, parameter budget, initial parameters and loss are matched.
Checks include hand arithmetic, ties/padding, finite differences for both gate architectures,
query-balanced pairwise loss, gradient flow and frozen retriever boundaries.

| Method | Parameters | Initial fixture loss | Final fixture loss | Initial gradient L1 |
| --- | --- | --- | --- | --- |
| QARF | 42 | 0.57053744 | 0.51900761 | 0.74386731 |
| QPAF | 42 | 0.57472797 | 0.51932824 | 0.78539255 |

These losses only demonstrate that the implementation can learn on the fixture.
They do not measure retrieval quality or show learned QPAF superiority.
Real-data trainer/evaluator: M2.4. Matched learned pilot: M3.
Independent review / reproduction by another member: PENDING.
Source, config, fixture hashes, command and environment: provenance.json.
Output integrity: hashes.csv and receipt.json; complete.json links the receipt.
