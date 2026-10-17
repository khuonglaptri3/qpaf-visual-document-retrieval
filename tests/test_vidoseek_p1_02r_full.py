from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import torch

from scripts import extract_vidoseek_p1_02r
from scripts.extract_vidore_baseline import _dataframe_sha256


def test_chunk_bounds_are_contiguous_bounded_and_cover_the_frozen_shapes() -> None:
    assert extract_vidoseek_p1_02r.chunk_bounds(10, 4) == [(0, 4), (4, 8), (8, 10)]
    query_bounds = extract_vidoseek_p1_02r.chunk_bounds(1_142, 8)
    page_bounds = extract_vidoseek_p1_02r.chunk_bounds(5_385, 512)

    assert len(query_bounds) == 143
    assert len(page_bounds) == 11
    assert query_bounds[0] == (0, 8) and query_bounds[-1] == (1_136, 1_142)
    assert page_bounds[0] == (0, 512) and page_bounds[-1] == (5_120, 5_385)
    assert max(end - start for start, end in query_bounds) == 8
    assert max(end - start for start, end in page_bounds) == 512
    with pytest.raises(ValueError, match="positive integer"):
        extract_vidoseek_p1_02r.chunk_bounds(10, 0)


def test_streamed_outputs_match_the_full_reference_without_a_full_row_table(
    tmp_path: Path,
) -> None:
    query_ids = np.asarray(["q0", "q1", "q2"])
    page_ids = np.asarray(["p2", "p0", "p4", "p1", "p3"])
    query_sources = ["s0", "s1", "s2"]
    source_scores = {
        "bm25_score": torch.arange(15, dtype=torch.float32).reshape(3, 5),
        "dense_score": torch.arange(15, 30, dtype=torch.float32).reshape(3, 5),
        "stage1_score": torch.arange(30, 45, dtype=torch.float32).reshape(3, 5),
    }
    visual = torch.arange(45, 60, dtype=torch.float32).reshape(3, 5)
    qrels = {("q0", "p4"): 1.0, ("q1", "p1"): 1.0, ("q2", "p3"): 1.0}
    visual_chunks = []
    for start, end in [(0, 2), (2, 4), (4, 5)]:
        path = tmp_path / f"visual_{start}_{end}.pt"
        torch.save(visual[:, start:end], path)
        visual_chunks.append((start, end, path))

    artifacts = extract_vidoseek_p1_02r.stream_all_corpus_outputs(
        output_dir=tmp_path / "output",
        dataset_id="synthetic",
        query_ids=query_ids,
        page_ids=page_ids,
        query_sources=query_sources,
        qrel_lookup=qrels,
        source_scores=source_scores,
        visual_score_chunks=visual_chunks,
        query_chunk_size=2,
        candidate_provenance="all_corpus_p1_02r_v1",
    )

    raw_path = tmp_path / "output" / "candidate_raw_scores.parquet"
    retrieval_path = tmp_path / "output" / "retrieval_scores.parquet"
    raw = pd.read_parquet(raw_path)
    retrieval = pd.read_parquet(retrieval_path)
    keys = ["dataset", "query_id", "page_id"]
    assert len(raw) == len(retrieval) == 15
    assert raw[keys].values.tolist() == raw.sort_values(keys)[keys].values.tolist()
    assert raw["candidate_provenance"].eq("all_corpus_p1_02r_v1").all()
    assert raw["relevance"].sum() == 3.0
    assert pq.ParquetFile(raw_path).metadata.num_row_groups == 2
    assert pq.ParquetFile(retrieval_path).metadata.num_row_groups == 2
    assert not list((tmp_path / "output").glob("*.tmp"))

    expected_raw_parts = []
    expected_retrieval_parts = []
    for query_index, query_id in enumerate(query_ids):
        expected_raw, expected_retrieval = extract_vidoseek_p1_02r._build_query_frames(
            dataset_id="synthetic",
            query_id=str(query_id),
            query_source=query_sources[query_index],
            page_ids=page_ids,
            qrel_lookup=qrels,
            bm25_scores=source_scores["bm25_score"][query_index].numpy(),
            dense_scores=source_scores["dense_score"][query_index].numpy(),
            stage1_scores=source_scores["stage1_score"][query_index].numpy(),
            visual_scores=visual[query_index].numpy(),
            candidate_provenance="all_corpus_p1_02r_v1",
        )
        expected_raw_parts.append(expected_raw)
        expected_retrieval_parts.append(expected_retrieval)
    expected_raw = (
        pd.concat(expected_raw_parts, ignore_index=True)
        .sort_values(keys)
        .reset_index(drop=True)
    )
    expected_retrieval = (
        pd.concat(expected_retrieval_parts, ignore_index=True)
        .sort_values(keys)
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(raw, expected_raw)
    pd.testing.assert_frame_equal(retrieval, expected_retrieval)
    assert artifacts["candidate_raw_scores.parquet"]["content_sha256"] == (
        _dataframe_sha256(expected_raw, keys)
    )
    assert artifacts["retrieval_scores.parquet"]["content_sha256"] == (
        _dataframe_sha256(expected_retrieval, keys)
    )


def test_streaming_rejects_noncontiguous_visual_chunks(tmp_path: Path) -> None:
    path = tmp_path / "visual.pt"
    torch.save(torch.ones((1, 1)), path)
    with pytest.raises(ValueError, match="contiguously"):
        extract_vidoseek_p1_02r.stream_all_corpus_outputs(
            output_dir=tmp_path / "output",
            dataset_id="synthetic",
            query_ids=np.asarray(["q0"]),
            page_ids=np.asarray(["p0", "p1"]),
            query_sources=["source"],
            qrel_lookup={},
            source_scores={
                "bm25_score": torch.ones((1, 2)),
                "dense_score": torch.ones((1, 2)),
                "stage1_score": torch.ones((1, 2)),
            },
            visual_score_chunks=[(1, 2, path)],
            query_chunk_size=1,
            candidate_provenance="all_corpus_p1_02r_v1",
        )


def test_full_runner_is_separate_resumable_and_qrels_enter_only_after_scoring() -> None:
    source = inspect.getsource(extract_vidoseek_p1_02r.run_chunked_full_extraction)

    assert "run_extraction" not in source
    assert "build_all_corpus_candidates" not in source
    assert "_valid_embedding_cache" in source
    assert "_valid_score_cache" in source
    assert "LazyPageImages(image_paths[start:end])" in source
    assert "stream_all_corpus_outputs" in source
    assert "parse_annotations(annotation_payload)" in source
    assert source.index("parse_annotations(annotation_payload)") > source.index(
        "_atomic_torch_save(score_tensor, score_path)"
    )
