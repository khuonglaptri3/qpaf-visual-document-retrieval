from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from scripts import audit_vidoseek_coverage


def test_frozen_expanded_pool_can_rescue_initially_uncovered_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        audit_vidoseek_coverage,
        "INITIAL_DEPTHS",
        {"stage1": 1, "bm25": 1, "dense": 1},
    )
    monkeypatch.setattr(
        audit_vidoseek_coverage,
        "EXPANDED_DEPTHS",
        {"stage1": 2, "bm25": 2, "dense": 2},
    )
    query_ids = np.asarray(["q0", "q1"])
    page_ids = np.asarray(["p0", "p1", "p2"])
    scores = np.asarray(
        [
            [0.5, 1.0, 0.0],
            [0.0, 0.1, 1.0],
        ],
        dtype=float,
    )

    pools = audit_vidoseek_coverage.build_candidate_pools(
        query_ids,
        page_ids,
        scores,
        scores,
        scores,
    )
    result = audit_vidoseek_coverage.compare_candidate_coverage(
        query_ids,
        page_ids,
        pools,
        {("q0", "p0"): 1.0, ("q1", "p2"): 1.0},
        dataset_id="synthetic",
    )

    assert result["initial"]["coverage"] == 0.5
    assert result["initial"]["zero_relevant_query_ids"] == ["q0"]
    assert result["expanded"]["coverage"] == 1.0
    assert result["expanded"]["zero_relevant_query_ids"] == []
    assert result["rescued_query_ids"] == ["q0"]
    assert result["decision"] == "expanded_depths_satisfy_existing_gate"
    assert result["candidate_generation_used_qrels"] is False


def test_candidate_pool_builder_cannot_accept_qrels() -> None:
    assert "qrel" not in inspect.signature(
        audit_vidoseek_coverage.build_candidate_pools
    ).parameters


def test_persisted_audit_rejects_untrusted_protocol_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        audit_vidoseek_coverage.audit_persisted_vidoseek_coverage(
            {"datasets": []},
            tmp_path,
            "../wrong",
        )


def test_persisted_audit_reads_the_failed_run_cache_layout(tmp_path: Path) -> None:
    source_protocol_sha256 = "a" * 64
    volume_root = tmp_path / "vol"
    run_root = (
        volume_root
        / "score_extraction"
        / "vidoseek"
        / source_protocol_sha256
        / "full"
    )
    cache_dir = run_root / "cache"
    cache_dir.mkdir(parents=True)
    document_ids = ["b" * 40, "c" * 40]
    annotation_payload = {
        "examples": [
            {
                "uid": f"{document_ids[0]}_0",
                "query": "first",
                "meta_info": {
                    "file_name": f"{document_ids[0]}.pdf",
                    "reference_page": [1],
                },
            },
            {
                "uid": f"{document_ids[1]}_0",
                "query": "second",
                "meta_info": {
                    "file_name": f"{document_ids[1]}.pdf",
                    "reference_page": [1],
                },
            },
        ]
    }
    dataset_root = volume_root / "datasets" / "vidoseek" / "revision"
    dataset_root.mkdir(parents=True)
    annotation_path = dataset_root / "vidoseek.json"
    annotation_path.write_text(json.dumps(annotation_payload), encoding="utf-8")
    page_ids = [f"{document_ids[0]}_1", "d" * 40 + "_1", f"{document_ids[1]}_1"]
    preparation_path = run_root / "prepared_corpus" / "_PREPARED.json"
    preparation_path.parent.mkdir(parents=True)
    preparation_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "page_count": len(page_ids),
                "pages": [{"page_id": page_id} for page_id in page_ids],
            }
        ),
        encoding="utf-8",
    )
    scores = torch.tensor(
        [
            [1.0, 0.5, 0.0],
            [0.0, 0.5, 1.0],
        ],
        dtype=torch.float32,
    )
    for filename in audit_vidoseek_coverage.SCORE_CACHE_FILES.values():
        torch.save(scores, cache_dir / filename)
    dataset_config = {
        "datasets": [
            {
                "key": "vidoseek",
                "id": "Qiuchen-Wang/ViDoSeek",
                "revision": "revision",
                "local_dir": str(dataset_root),
                "qrels_metadata": {
                    "annotation_file_sha256": hashlib.sha256(
                        annotation_path.read_bytes()
                    ).hexdigest()
                },
                "discovery_extraction": {"annotation_file": annotation_path.name},
            }
        ]
    }

    result = audit_vidoseek_coverage.audit_persisted_vidoseek_coverage(
        dataset_config,
        volume_root,
        source_protocol_sha256,
    )

    assert result["status"] == "complete"
    assert result["gpu_used"] is False
    assert result["dataset"]["queries"] == 2
    assert result["dataset"]["pages"] == 3
    assert result["decision"] == "expanded_depths_satisfy_existing_gate"
    assert set(result["score_cache_sha256"]) == set(
        audit_vidoseek_coverage.SCORE_CACHE_FILES.values()
    )
