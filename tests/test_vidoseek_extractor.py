from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts import vidoseek_dataset


ROOT = Path(__file__).resolve().parents[1]


def _example(document: str, suffix: str, query: str, pages: list[int]) -> dict[str, object]:
    return {
        "uid": f"{document}_{suffix}",
        "query": query,
        "reference_answer": "must not enter retrieval inputs",
        "meta_info": {
            "file_name": f"pdf/{document}.pdf",
            "reference_page": pages,
            "source_type": "report",
            "query_type": "text",
        },
    }


def test_annotations_map_uid_and_one_based_reference_pages_to_binary_qrels() -> None:
    first_document = "a" * 40
    second_document = "b" * 40
    annotations = vidoseek_dataset.parse_annotations(
        {
            "examples": [
                _example(second_document, "1", "second query", [2]),
                _example(first_document, "0", "first query", [1, 3]),
            ]
        }
    )

    assert annotations.query_ids.tolist() == [f"{first_document}_0", f"{second_document}_1"]
    assert annotations.query_texts == ["first query", "second query"]
    assert annotations.query_sources == [
        "source_type=report|query_type=text",
        "source_type=report|query_type=text",
    ]
    assert annotations.qrel_lookup == {
        (f"{first_document}_0", f"{first_document}_1"): 1.0,
        (f"{first_document}_0", f"{first_document}_3"): 1.0,
        (f"{second_document}_1", f"{second_document}_2"): 1.0,
    }


@pytest.mark.parametrize("page", [0, -1, 1.5, True])
def test_page_ids_reject_non_positive_or_non_integer_pages(page: object) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        vidoseek_dataset.page_id("a" * 40, page)  # type: ignore[arg-type]


def test_annotations_reject_duplicate_query_ids() -> None:
    document = "a" * 40
    with pytest.raises(ValueError, match="query IDs must be unique"):
        vidoseek_dataset.parse_annotations(
            {
                "examples": [
                    _example(document, "0", "first", [1]),
                    _example(document, "0", "duplicate", [2]),
                ]
            }
        )


def test_extraction_protocol_stops_until_text_policy_is_approved() -> None:
    config = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    dataset = next(item for item in config["datasets"] if item["key"] == "vidoseek")

    with pytest.raises(RuntimeError, match="requires human approval"):
        vidoseek_dataset.extraction_protocol(dataset)

    approved = copy.deepcopy(dataset)
    approved["discovery_extraction"]["protocol_status"] = "approved"
    protocol = vidoseek_dataset.extraction_protocol(approved)
    assert protocol["page_renderer"] == "poppler_pdftoppm"
    assert protocol["render_dpi"] == 200
    assert protocol["render_intermediate_format"] == "ppm"
    assert protocol["jpeg_encoder"] == "pillow_default"
    assert protocol["text_source"] == "native_pdf_text_not_ocr"
    assert protocol["pdf_archive_sha256"] == (
        "3b999a798ceab38703118e4cc7d9b852f86538d5bb7caad64eb545251ee00454"
    )


def test_calibration_selects_only_queries_connected_to_rendered_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_document = "a" * 40
    second_document = "b" * 40
    payload = {
        "examples": [
            _example(first_document, "0", "not rendered", [1]),
            _example(second_document, "1", "rendered", [2]),
        ]
    }
    annotation_path = tmp_path / "vidoseek.json"
    annotation_path.write_text(json.dumps(payload), encoding="utf-8")
    archive_path = tmp_path / "vidoseek_pdf_document.zip"
    archive_path.write_bytes(b"synthetic archive")
    text_path = tmp_path / "page.txt"
    text_path.write_text("page text", encoding="utf-8")
    image_path = tmp_path / "page.jpg"
    image_path.write_bytes(b"not opened by this test")
    dataset = {
        "local_dir": str(tmp_path),
        "qrels_metadata": {
            "annotation_file_sha256": hashlib.sha256(annotation_path.read_bytes()).hexdigest()
        },
        "discovery_extraction": {
            "protocol_status": "approved",
            "annotation_file": annotation_path.name,
            "pdf_archive": archive_path.name,
            "pdf_archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "expected_archive_pdf_count": 2,
            "expected_query_count": 2,
            "expected_referenced_document_count": 2,
            "expected_reference_pair_count": 2,
            "page_renderer": "poppler_pdftoppm",
            "render_dpi": 200,
            "render_intermediate_format": "ppm",
            "render_format": "jpeg",
            "jpeg_encoder": "pillow_default",
            "page_numbering": "one_based",
            "text_extractor": "poppler_pdftotext_layout",
            "text_source": "native_pdf_text_not_ocr",
            "official_reference": {},
            "qrels_use": "coverage_and_evaluation_only",
        },
    }
    record = {
        "page_id": f"{second_document}_2",
        "document_id": second_document,
        "page_number": 2,
        "image": str(image_path),
        "text": str(text_path),
        "text_nonempty": True,
    }
    monkeypatch.setattr(
        vidoseek_dataset,
        "_prepare_corpus",
        lambda *args, **kwargs: ([record], {"pages": [record], "page_count": 1}),
    )

    inputs = vidoseek_dataset.load_vidoseek_inputs(
        dataset=dataset,
        run_root=tmp_path / "run",
        commit=lambda: None,
        query_limit=1,
        page_limit=1,
    )

    assert inputs.query_ids.tolist() == [f"{second_document}_1"]
    assert inputs.query_texts == ["rendered"]
    assert inputs.qrel_lookup == {(f"{second_document}_1", f"{second_document}_2"): 1.0}
    assert inputs.metadata["selected_qrel_count"] == 1
    assert "pages" not in inputs.metadata


def test_pdftotext_split_requires_exact_page_count() -> None:
    assert vidoseek_dataset._split_pdftotext_pages("first\fsecond\f", 2) == [
        "first",
        "second",
    ]
    with pytest.raises(RuntimeError, match="expected 3"):
        vidoseek_dataset._split_pdftotext_pages("first\fsecond\f", 3)
