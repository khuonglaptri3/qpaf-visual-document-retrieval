from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image


DATASET_KEY = "vidoseek"
DATASET_ID = "Qiuchen-Wang/ViDoSeek"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class VidoseekAnnotations:
    query_ids: np.ndarray
    query_texts: list[str]
    query_sources: list[str]
    qrel_lookup: dict[tuple[str, str], float]
    relevant_document_ids: set[str]


@dataclass(frozen=True)
class VidoseekInputs:
    query_ids: np.ndarray
    page_ids: np.ndarray
    query_texts: list[str]
    corpus_texts: list[str]
    query_sources: list[str]
    images: Any
    qrel_lookup: dict[tuple[str, str], float]
    metadata: dict[str, Any]


class LazyPageImages:
    def __init__(self, paths: list[Path]):
        self.paths = paths

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int | slice) -> Image.Image | list[Image.Image]:
        if isinstance(index, slice):
            return [self[position] for position in range(*index.indices(len(self)))]
        with Image.open(self.paths[int(index)]) as image:
            return image.convert("RGB")

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def document_id_from_uid(uid: str) -> str:
    document_id, separator, suffix = str(uid).rpartition("_")
    if not separator or not suffix or not HEX40.fullmatch(document_id):
        raise ValueError(f"Invalid ViDoSeek uid: {uid!r}")
    return document_id


def page_id(document_id: str, page_number: int) -> str:
    if not HEX40.fullmatch(str(document_id)):
        raise ValueError(f"Invalid ViDoSeek document ID: {document_id!r}")
    if isinstance(page_number, bool) or int(page_number) != page_number or int(page_number) < 1:
        raise ValueError(f"ViDoSeek page numbers must be positive integers: {page_number!r}")
    return f"{document_id}_{int(page_number)}"


def parse_annotations(payload: dict[str, Any]) -> VidoseekAnnotations:
    examples = payload.get("examples")
    if not isinstance(examples, list) or not examples:
        raise ValueError("ViDoSeek annotations require a non-empty top-level examples list")

    rows = []
    qrel_lookup: dict[tuple[str, str], float] = {}
    for example in examples:
        if not isinstance(example, dict):
            raise ValueError("Every ViDoSeek example must be an object")
        uid = str(example.get("uid", ""))
        query = str(example.get("query", "")).strip()
        meta = example.get("meta_info")
        if not query or not isinstance(meta, dict):
            raise ValueError(f"ViDoSeek example {uid!r} is missing query/meta_info")
        document_id = document_id_from_uid(uid)
        annotated_document_id = Path(str(meta.get("file_name", ""))).stem
        if annotated_document_id != document_id:
            raise ValueError(
                f"ViDoSeek example {uid!r} file_name does not match its document ID"
            )
        reference_pages = meta.get("reference_page")
        if not isinstance(reference_pages, list) or not reference_pages:
            raise ValueError(f"ViDoSeek example {uid!r} has no reference pages")
        source = (
            f"source_type={meta.get('source_type') or 'unknown'}|"
            f"query_type={meta.get('query_type') or 'unknown'}"
        )
        for reference_page in reference_pages:
            key = (uid, page_id(document_id, reference_page))
            if key in qrel_lookup:
                raise ValueError(f"Duplicate ViDoSeek qrel: {key}")
            qrel_lookup[key] = 1.0
        rows.append((uid, query, source, document_id))

    rows.sort(key=lambda row: row[0])
    query_ids = [row[0] for row in rows]
    if len(set(query_ids)) != len(query_ids):
        raise ValueError("ViDoSeek query IDs must be unique")
    return VidoseekAnnotations(
        query_ids=np.asarray(query_ids),
        query_texts=[row[1] for row in rows],
        query_sources=[row[2] for row in rows],
        qrel_lookup=qrel_lookup,
        relevant_document_ids={row[3] for row in rows},
    )


def extraction_protocol(dataset: dict[str, Any], require_approved: bool = True) -> dict[str, Any]:
    config = dataset.get("discovery_extraction")
    if not isinstance(config, dict):
        raise RuntimeError("ViDoSeek discovery_extraction config is missing")
    status = config.get("protocol_status")
    approval = config.get("protocol_approval")
    if require_approved and status != "approved":
        raise RuntimeError(
            "ViDoSeek extraction protocol requires human approval: "
            f"status={status!r}, blocker={config.get('review_blocker')!r}"
        )
    if status == "approved" and not isinstance(approval, dict):
        raise RuntimeError("Approved ViDoSeek extraction protocol is missing approval provenance")
    return {
        "protocol_status": status,
        "protocol_approval": approval,
        "full_extraction_gpu_approval": config["full_extraction_gpu_approval"],
        "annotation_file": config["annotation_file"],
        "annotation_file_sha256": dataset["qrels_metadata"]["annotation_file_sha256"],
        "pdf_archive": config["pdf_archive"],
        "pdf_archive_sha256": config["pdf_archive_sha256"],
        "expected_archive_pdf_count": int(config["expected_archive_pdf_count"]),
        "expected_query_count": int(config["expected_query_count"]),
        "expected_referenced_document_count": int(config["expected_referenced_document_count"]),
        "expected_reference_pair_count": int(config["expected_reference_pair_count"]),
        "page_renderer": config["page_renderer"],
        "render_dpi": int(config["render_dpi"]),
        "render_intermediate_format": config["render_intermediate_format"],
        "render_format": config["render_format"],
        "jpeg_encoder": config["jpeg_encoder"],
        "page_numbering": config["page_numbering"],
        "text_extractor": config["text_extractor"],
        "text_source": config["text_source"],
        "official_reference": config["official_reference"],
        "qrels_use": config["qrels_use"],
    }


def _pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    if not match or int(match.group(1)) < 1:
        raise RuntimeError(f"pdfinfo did not report a positive page count for {pdf_path.name}")
    return int(match.group(1))


def _split_pdftotext_pages(value: str, expected_pages: int) -> list[str]:
    pages = value.replace("\r\n", "\n").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != expected_pages:
        raise RuntimeError(
            f"pdftotext returned {len(pages)} pages; expected {expected_pages}"
        )
    return [page.strip() for page in pages]


def _render_pdf(
    pdf_path: Path,
    output_root: Path,
    document_id: str,
    page_count: int,
    dpi: int,
) -> list[dict[str, Any]]:
    render_prefix = pdf_path.parent / "rendered"
    subprocess.run(
        [
            "pdftoppm",
            "-r",
            str(dpi),
            "-f",
            "1",
            "-l",
            str(page_count),
            str(pdf_path),
            str(render_prefix),
        ],
        check=True,
        capture_output=True,
        timeout=3_600,
    )
    rendered = sorted(
        pdf_path.parent.glob("rendered-*.ppm"),
        key=lambda path: int(path.stem.rsplit("-", 1)[1]),
    )
    if len(rendered) != page_count:
        raise RuntimeError(f"pdftoppm rendered {len(rendered)} pages; expected {page_count}")
    text_result = subprocess.run(
        [
            "pdftotext",
            "-layout",
            "-f",
            "1",
            "-l",
            str(page_count),
            str(pdf_path),
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=1_800,
    )
    texts = _split_pdftotext_pages(text_result.stdout, page_count)

    page_root = output_root / "pages"
    page_root.mkdir(parents=True, exist_ok=True)
    records = []
    for one_based_page, (rendered_path, text) in enumerate(zip(rendered, texts), start=1):
        identifier = page_id(document_id, one_based_page)
        image_path = page_root / f"{identifier}.jpg"
        text_path = page_root / f"{identifier}.txt"
        image_temporary = image_path.with_suffix(".jpg.tmp")
        text_temporary = text_path.with_suffix(".txt.tmp")
        with Image.open(rendered_path) as image:
            image.convert("RGB").save(image_temporary, format="JPEG")
        text_temporary.write_text(text, encoding="utf-8")
        image_temporary.replace(image_path)
        text_temporary.replace(text_path)
        records.append(
            {
                "page_id": identifier,
                "document_id": document_id,
                "page_number": one_based_page,
                "image": str(image_path),
                "text": str(text_path),
                "text_nonempty": bool(text),
            }
        )
    return records


def _prepare_corpus(
    archive_path: Path,
    output_root: Path,
    protocol: dict[str, Any],
    relevant_document_ids: set[str],
    page_limit: int,
    commit: Callable[[], None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    marker_path = output_root / "_PREPARED.json"
    if marker_path.is_file():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("page_limit") == page_limit and all(
            Path(record["image"]).is_file() and Path(record["text"]).is_file()
            for record in marker.get("pages", [])
        ):
            return marker["pages"], marker

    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            [name for name in archive.namelist() if not name.endswith("/") and name.lower().endswith(".pdf")],
            key=lambda name: Path(name).stem,
        )
        stems = [Path(name).stem for name in members]
        if len(members) != protocol["expected_archive_pdf_count"] or len(set(stems)) != len(stems):
            raise RuntimeError("ViDoSeek PDF archive count/uniqueness does not match the frozen contract")
        missing_documents = sorted(relevant_document_ids - set(stems))
        if missing_documents:
            raise RuntimeError(f"ViDoSeek qrels reference missing PDFs: {missing_documents[:20]}")

        records: list[dict[str, Any]] = []
        for member, document_id in zip(members, stems):
            if page_limit and len(records) >= page_limit:
                break
            with tempfile.TemporaryDirectory(prefix="vidoseek_pdf_") as temporary_dir:
                pdf_path = Path(temporary_dir) / f"{document_id}.pdf"
                with archive.open(member) as source, pdf_path.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                available_pages = _pdf_page_count(pdf_path)
                selected_pages = (
                    min(available_pages, page_limit - len(records)) if page_limit else available_pages
                )
                records.extend(
                    _render_pdf(
                        pdf_path,
                        output_root,
                        document_id,
                        selected_pages,
                        protocol["render_dpi"],
                    )
                )
                commit()

    marker = {
        "schema_version": 1,
        "status": "complete",
        "page_limit": page_limit,
        "archive_pdf_count": len(members),
        "referenced_document_count": len(relevant_document_ids),
        "page_count": len(records),
        "nonempty_text_pages": sum(record["text_nonempty"] for record in records),
        "text_source": protocol["text_source"],
        "pages": records,
    }
    _atomic_json(marker, marker_path)
    commit()
    return records, marker


def load_vidoseek_inputs(
    dataset: dict[str, Any],
    run_root: Path,
    commit: Callable[[], None],
    query_limit: int = 0,
    page_limit: int = 0,
) -> VidoseekInputs:
    protocol = extraction_protocol(dataset, require_approved=True)
    dataset_root = Path(dataset["local_dir"])
    annotation_path = dataset_root / protocol["annotation_file"]
    archive_path = dataset_root / protocol["pdf_archive"]
    if _file_sha256(annotation_path) != protocol["annotation_file_sha256"]:
        raise RuntimeError("ViDoSeek annotation file hash does not match the frozen contract")
    if _file_sha256(archive_path) != protocol["pdf_archive_sha256"]:
        raise RuntimeError("ViDoSeek PDF archive hash does not match the frozen contract")
    annotations = parse_annotations(json.loads(annotation_path.read_text(encoding="utf-8")))
    if (
        len(annotations.query_ids) != protocol["expected_query_count"]
        or len(annotations.relevant_document_ids) != protocol["expected_referenced_document_count"]
        or len(annotations.qrel_lookup) != protocol["expected_reference_pair_count"]
    ):
        raise RuntimeError("ViDoSeek annotation counts do not match the frozen contract")

    records, corpus_metadata = _prepare_corpus(
        archive_path,
        run_root / "prepared_corpus",
        protocol,
        annotations.relevant_document_ids,
        page_limit,
        commit,
    )
    page_ids = np.asarray([record["page_id"] for record in records])
    selected_page_set = set(page_ids.tolist())
    if page_limit:
        eligible_query_ids = {
            query_id
            for query_id, relevant_page_id in annotations.qrel_lookup
            if relevant_page_id in selected_page_set
        }
        selected_indices = [
            index
            for index, query_id in enumerate(annotations.query_ids)
            if query_id in eligible_query_ids
        ]
        if query_limit and len(selected_indices) < query_limit:
            raise RuntimeError(
                "ViDoSeek calibration corpus has only "
                f"{len(selected_indices)} qrel-connected queries; requested {query_limit}"
            )
    else:
        selected_indices = list(range(len(annotations.query_ids)))
    if query_limit:
        selected_indices = selected_indices[:query_limit]
    query_ids = annotations.query_ids[selected_indices]
    selected_query_set = set(query_ids.tolist())
    qrel_lookup = {
        key: relevance
        for key, relevance in annotations.qrel_lookup.items()
        if key[0] in selected_query_set and key[1] in selected_page_set
    }
    if not page_limit:
        expected_keys = {
            key for key in annotations.qrel_lookup if key[0] in selected_query_set
        }
        missing_qrels = sorted(expected_keys - set(qrel_lookup))
        if missing_qrels:
            raise RuntimeError(f"ViDoSeek full corpus is missing qrels pages: {missing_qrels[:20]}")

    return VidoseekInputs(
        query_ids=query_ids,
        page_ids=page_ids,
        query_texts=[annotations.query_texts[index] for index in selected_indices],
        corpus_texts=[Path(record["text"]).read_text(encoding="utf-8") for record in records],
        query_sources=[annotations.query_sources[index] for index in selected_indices],
        images=LazyPageImages([Path(record["image"]) for record in records]),
        qrel_lookup=qrel_lookup,
        metadata={
            **{key: value for key, value in corpus_metadata.items() if key != "pages"},
            "selected_query_count": len(query_ids),
            "selected_qrel_count": len(qrel_lookup),
            "protocol": protocol,
        },
    )
