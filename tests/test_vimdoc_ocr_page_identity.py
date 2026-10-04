from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_vimdoc_ocr_page_identity.py"
SPEC = importlib.util.spec_from_file_location("vimdoc_identity", SCRIPT)
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row(path: str, data: bytes) -> dict:
    return identity.asset_row(path, digest(data), len(data))


def make_tar(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_page_identity_removes_one_extension_and_final_numeric_suffix_only():
    assert identity.page_identity("pages/report.v1_page_010.PNG") == (
        "report.v1_page_010", "report.v1_page", 10
    )
    for bad in ("/pages/a_1.png", "pages/sub/a_1.png", "pages/../a_1.png",
                "pages//a_1.png", "pages/a.png", "pages/a_x.png", "pages/a_1.gif",
                "pages\\a_1.png", "pages/a_1.png\x00"):
        with pytest.raises(ValueError):
            identity.page_identity(bad)


def test_identical_same_page_assets_collapse_with_utf8_path_tie_break():
    data = b"same-image"
    report = identity.resolve_assets([
        row("pages/doc_1.png", data), row("pages/doc_1.jpg", data), row("pages/doc_2.png", b"two")
    ])
    assert report["status"] == "PASS" and report["ready_for_ocr"] is True
    assert report["asset_count"] == 3 and report["page_id_count"] == 2
    assert [item["asset_path"] for item in report["assets"]] == [
        "pages/doc_1.jpg", "pages/doc_1.png", "pages/doc_2.png"
    ]
    assert report["extra_assets_sharing_page_id"] == 1
    first = report["pages"][0]
    assert first["page_id"] == "doc_1"
    assert first["canonical_asset_path"] == "pages/doc_1.jpg"
    assert first["alias_asset_paths"] == ["pages/doc_1.jpg", "pages/doc_1.png"]


def test_different_content_same_page_id_is_a_hard_block():
    report = identity.resolve_assets([
        row("pages/doc_1.jpg", b"first"), row("pages/doc_1.png", b"second")
    ])
    assert report["status"] == "BLOCKED_DIFFERENT_CONTENT_PAGE_ID_COLLISION"
    assert report["ready_for_ocr"] is False
    assert report["different_content_collision_count"] == 1
    assert report["canonical_page_count"] == 0


def test_same_content_different_page_ids_are_retained_and_reported():
    data = b"shared"
    report = identity.resolve_assets([
        row("pages/a_1.png", data), row("pages/b_1.png", data)
    ])
    assert [item["page_id"] for item in report["pages"]] == ["a_1", "b_1"]
    assert report["cross_page_duplicate_content_group_count"] == 1


def test_tar_inspection_hashes_uncompressed_bytes_and_never_extracts(tmp_path):
    archive = tmp_path / "pages.tar.gz"
    make_tar(archive, [("pages/b_2.png", b"B"), ("pages/a_1.jpg", b"A")])
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    report = identity.inspect_tar(archive)
    assert report["status"] == "PASS"
    assert report["archive_sha256"] == digest(archive.read_bytes())
    assert report["pages"][0]["asset_sha256"] == digest(b"A")
    assert before == sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))


def test_frozen_identity_contract_checks_archive_counts_and_conflicts():
    report = identity.resolve_assets([row("pages/a_1.png", b"A")])
    report.update({"archive_sha256": "a" * 64})
    protocol = {
        "source_alignment": {"dataset_archive_sha256": "a" * 64},
        "asset_identity": {"expected_asset_files": 1,
                           "expected_unique_page_ids_before_content_audit": 1,
                           "expected_extra_assets_sharing_page_id": 0,
                           "expected_document_ids": 1},
    }
    checked = identity.enforce_frozen_identity_contract(report, protocol)
    assert checked["frozen_counts_verified"] is True
    for key in ("asset_count", "page_id_count", "extra_assets_sharing_page_id", "document_count"):
        bad = dict(report)
        bad[key] += 1
        with pytest.raises(ValueError, match="mismatch"):
            identity.enforce_frozen_identity_contract(bad, protocol)


def test_tar_rejects_link_and_duplicate_member_paths(tmp_path):
    link_archive = tmp_path / "link.tar.gz"
    with tarfile.open(link_archive, "w:gz") as archive:
        info = tarfile.TarInfo("pages/a_1.png")
        info.type = tarfile.SYMTYPE
        info.linkname = "target"
        archive.addfile(info)
    with pytest.raises(ValueError, match="regular"):
        identity.inspect_tar(link_archive)
    duplicate_archive = tmp_path / "duplicate.tar.gz"
    make_tar(duplicate_archive, [("pages/a_1.png", b"A"), ("pages/a_1.png", b"A")])
    with pytest.raises(ValueError, match="Duplicate"):
        identity.inspect_tar(duplicate_archive)


def ocr_row(page: dict, text: str) -> dict:
    text = identity.normalize_ocr_text(text)
    return {"page_id": page["page_id"], "canonical_asset_path": page["canonical_asset_path"],
            "asset_sha256": page["asset_sha256"],
            "status": "SUCCESS_EMPTY" if text == "" else "SUCCESS_NONEMPTY", "text": text,
            "text_sha256": identity.sha256_text(text), "character_count": len(text)}


def test_ocr_validation_keeps_empty_distinct_from_error_and_binds_assets():
    report = identity.resolve_assets([row("pages/a_1.png", b"A"), row("pages/b_1.png", b"B")])
    rows = [ocr_row(report["pages"][0], "text\n"), ocr_row(report["pages"][1], "")]
    result = identity.validate_ocr_rows(report, rows)
    assert result["status"] == "PASS"
    assert result["nonempty_text_count"] == 1 and result["empty_text_count"] == 1
    bad = [dict(item) for item in rows]
    bad[1]["status"] = "ERROR"
    with pytest.raises(ValueError, match="masquerade"):
        identity.validate_ocr_rows(report, bad)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "wrong_hash", "crlf", "reordered"])
def test_ocr_validation_fails_closed(mutation):
    report = identity.resolve_assets([row("pages/a_1.png", b"A"), row("pages/b_1.png", b"B")])
    rows = [ocr_row(page, page["page_id"]) for page in report["pages"]]
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append({**rows[-1], "page_id": "extra_1"})
    elif mutation == "duplicate":
        rows.append(dict(rows[-1]))
    elif mutation == "wrong_hash":
        rows[0]["text_sha256"] = "0" * 64
    elif mutation == "crlf":
        rows[0]["text"] = "a\r\n"
    elif mutation == "reordered":
        rows.reverse()
    with pytest.raises(ValueError):
        identity.validate_ocr_rows(report, rows)


def test_frozen_spec_is_source_aligned_explicit_and_execution_closed():
    config = json.loads((ROOT / "configs/vimdoc_ocr_page_identity_v1.json").read_text())
    assert config["status"] == "FROZEN_LOCAL_SPECIFICATION_NOT_EXECUTED"
    assert config["source_alignment"]["heaven_revision"] == "3eea5ca61f492d3fa18594d455ee10024932f851"
    assert config["source_alignment"]["heaven_ocr_source_sha256"] == "eabe9cffc6d82f2634ec07d8b579c26dfd96acab4565fba5a5c9c618cac7922b"
    assert config["ocr"]["content_type"] == "plain_text_not_markdown"
    assert config["ocr"]["language"] == "eng"
    assert config["ocr"]["config"] == "--oem 3 --psm 3"
    assert config["ocr"]["consumers"] == ["BM25", "BGE-M3"]
    assert config["authorization"] == {
        "local_specification_only": True, "archive_audit_executed": False,
        "ocr_executed": False, "modal_execution_approved": False,
        "gpu_execution_approved": False, "approved_invocations": 0
    }


def test_validator_has_no_ocr_gpu_network_or_write_imports_and_no_run_switch():
    tree = ast.parse(SCRIPT.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= {"__future__", "argparse", "hashlib", "json", "pathlib", "tarfile", "typing"}
    for argument in ("--ocr", "--run", "--modal", "--gpu", "--write"):
        result = subprocess.run([sys.executable, str(SCRIPT), argument], capture_output=True, text=True)
        assert result.returncode == 2
