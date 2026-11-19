"""Prepare candidate pools using only texts, IDs and explicit retriever scores."""
from collections import defaultdict
import csv
import math
from pathlib import Path
import re

from .contracts import (
    decode_json, number, positive_int, read_json, text_id, validate_pairs, validate_split_manifest,
)
from .evaluation import minmax


CHANNELS = ("bm25", "dense", "visual")
F9_PAIR_NAMES = ("f9_pairs.json", "test_pairs.json")


def f9_bundle_paths(dataset, folder, page_text, query_ids=None, *, use_default_ids=True):
    """Return only the label-free paths needed from the native F9 input layout."""
    folder = Path(folder)
    if dataset == "vidoseek":
        scores, queries = "raw_scores.parquet", "queries.json"
        default_ids = folder / "splits" / "test_ids.txt"
    elif dataset == "vimdoc":
        scores, queries = "candidate_scores.parquet", "queries.jsonl"
        root = Path(__file__).resolve().parents[3]
        default_ids = root / "evidence" / "revisions" / "m4.1-001" / "confirmation_ids.txt"
    else:
        raise ValueError("--f9-bundle requires --dataset vidoseek or vimdoc")
    paths = {"queries": folder / queries, "page_text": page_text, "raw_scores": folder / scores}
    if query_ids is not None or use_default_ids:
        paths["query_ids"] = query_ids or default_ids
    return paths


def f9_pairs_path(folder):
    valid = [Path(folder) / name for name in F9_PAIR_NAMES if (Path(folder) / name).is_file()]
    if len(valid) != 1:
        candidates = ", ".join(str(Path(folder) / name) for name in F9_PAIR_NAMES)
        raise ValueError(f"--f9-cache needs exactly one of {candidates}; use prepare --f9-pairs FILE")
    return valid[0]


def require_inputs(paths, hint):
    missing = [str(path) if path is not None else f"--{name.replace('_', '-')}"
               for name, path in paths.items() if path is None or not Path(path).is_file()]
    if missing:
        raise ValueError(f"missing required input(s): {', '.join(missing)}. Next command: {hint}")


def _jsonl(path):
    with Path(path).open("rb") as stream:
        for line_no, raw in enumerate(stream, 1):
            if raw.strip():
                yield decode_json(raw, f"{path}:{line_no}")


def load_texts(path, id_key, selected=None):
    if Path(path).suffix.lower() == ".jsonl":
        texts = {}
        for entry in _jsonl(path):
            if not isinstance(entry, dict) or not text_id(entry.get(id_key)):
                raise ValueError(f"{path}: each text row must have a nonempty {id_key}")
            key = entry[id_key]
            if selected is not None and key not in selected:
                continue
            if key in texts:
                raise ValueError(f"{path}: duplicate {id_key} {key!r}")
            texts[key] = entry.get("text")
    else:
        texts = read_json(path)
        if not isinstance(texts, dict):
            raise ValueError(f"{path}: expected an ID-to-text mapping")
    if selected is not None:
        missing = [key for key in selected if key not in texts]
        if missing:
            raise ValueError(f"{path}: missing text for IDs {missing}")
        texts = {key: texts[key] for key in selected}
    return texts


def load_query_ids(path):
    ids = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not ids or any(not text_id(key) or key.strip() != key for key in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{path}: expected unique nonempty query IDs, one per line")
    return ids


def _csv_rows(path, numeric, selected):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        if not rows.fieldnames or len(set(rows.fieldnames)) != len(rows.fieldnames):
            raise ValueError(f"{path}: missing CSV header or duplicate columns")
        for line, row in enumerate(rows, 2):
            if selected is not None and row.get("query_id") not in selected:
                continue
            if None in row or None in row.values():
                raise ValueError(f"{path}:{line}: wrong number of columns")
            for name in numeric:
                try:
                    row[name] = float(row[name])
                except (KeyError, ValueError) as exc:
                    raise ValueError(f"{path}:{line}: missing or invalid {name} column") from exc
            yield row


def _parquet_rows(path, numeric, selected, document_units):
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError(
            f"{path}: Parquet needs pyarrow. Install it in your Python environment or "
            "use prepare --raw-scores FILE.csv with the same columns"
        ) from exc
    columns = ["query_id", "page_id", *numeric]
    try:
        parquet = pq.ParquetFile(path)
        if document_units or (document_units is None and "document_id" in parquet.schema_arrow.names):
            columns.append("document_id")
        missing = set(columns) - set(parquet.schema_arrow.names)
        if missing:
            raise ValueError(f"missing columns {sorted(missing)}")
        if selected is not None:
            table = pq.read_table(path, columns=columns, filters=[("query_id", "in", sorted(selected))])
            batches = table.to_batches(max_chunksize=8192)
        else:
            batches = parquet.iter_batches(columns=columns, batch_size=8192)
        for batch in batches:
            yield from batch.to_pylist()
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f"{path}: cannot read required Parquet columns {columns}: {exc}") from exc


def load_raw_rows(path, weights=None, selected=None, native=None):
    """Read JSON arrays, JSONL, CSV or projected Parquet score rows."""
    numeric = ("base_score",) if weights is None else CHANNELS
    if native == "vidoseek":
        numeric = tuple(f"{channel}_score" for channel in CHANNELS)
    suffix = Path(path).suffix.lower()
    wanted = None if selected is None else set(selected)
    if suffix == ".parquet":
        yield from _parquet_rows(path, numeric, wanted, None if native is None else native == "vimdoc")
        return
    if suffix == ".csv":
        yield from _csv_rows(path, numeric, wanted)
        return
    if suffix == ".jsonl":
        rows = _jsonl(path)
    elif suffix == ".json":
        rows = read_json(path)
        if not isinstance(rows, list):
            raise ValueError(f"{path}: expected an array of raw score rows")
    else:
        raise ValueError(f"{path}: use .json, .jsonl, .csv or .parquet for raw score rows")
    for row in rows:
        if not isinstance(row, dict) or not text_id(row.get("query_id")):
            raise ValueError(f"{path}: raw rows require a nonempty query_id")
        if wanted is None or row["query_id"] in wanted:
            yield row


def prepare_candidates(dataset, queries, pages, rows, top_k, *, weights=None, units=None, synthetic=False):
    """Select by explicit scores; store the chosen rows in ascending page-ID order."""
    positive_int(top_k, "top_k")
    if weights is not None:
        if not isinstance(weights, (tuple, list)) or len(weights) != len(CHANNELS):
            raise ValueError("weights: supply BM25, dense and visual weights")
        weights = [number(value, f"{channel} weight") for channel, value in zip(CHANNELS, weights, strict=True)]
        if any(weight < 0 or weight > 1 for weight in weights) or not math.isclose(sum(weights), 1):
            raise ValueError("weights: nonnegative BM25, dense and visual weights must sum to 1")
    if units is not None and not isinstance(units, dict):
        raise ValueError("units: expected a page-to-unit mapping")
    page_units = {} if units is None else dict(units)
    grouped = defaultdict(dict)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("raw scores: expected objects with query_id and page_id")
        query, page = row.get("query_id"), row.get("page_id")
        if not text_id(query) or not text_id(page) or query not in queries:
            raise ValueError(f"raw scores: unknown query or invalid page for ({query!r}, {page!r})")
        if page in grouped[query]:
            raise ValueError(f"raw scores: duplicate pair ({query!r}, {page!r})")
        if "document_id" in row:
            unit = row["document_id"]
            if not text_id(unit) or page_units.setdefault(page, unit) != unit:
                raise ValueError(f"raw scores: invalid or conflicting document ID for page {page!r}")
        if weights is None:
            value = number(row.get("base_score"), f"{query}/{page} base_score")
        else:
            value = tuple(
                number(row.get(channel, row.get(f"{channel}_score")), f"{query}/{page} {channel}")
                for channel in CHANNELS
            )
        grouped[query][page] = value

    pairs, base_scores = [], []
    for query in queries:
        candidates = grouped[query]
        if not candidates:
            raise ValueError(f"raw scores: no candidates for query {query!r}")
        ordered = sorted(candidates)
        if weights is None:
            scores = candidates
        else:
            columns = zip(*(candidates[page] for page in ordered), strict=True)
            normalized = [minmax(column) for column in map(list, columns)]
            scores = {
                page: sum(weight * score for weight, score in zip(weights, row, strict=True))
                for page, row in zip(ordered, zip(*normalized, strict=True), strict=True)
            }
        chosen = sorted(ordered, key=scores.get, reverse=True)[:top_k]
        for page in sorted(chosen):
            pairs.append([query, page])
            base_scores.append(scores[page])

    selected_pages = dict.fromkeys(page for _, page in pairs)
    for page in selected_pages:
        if page not in pages or not isinstance(pages[page], str):
            raise ValueError(f"page {page!r}: missing OCR text; an explicit empty string is allowed")
    bundle = {
        "dataset": dataset, "synthetic": synthetic, "top_k": top_k,
        "queries": queries, "pages": {page: pages[page] for page in selected_pages},
        "pairs": pairs, "base_scores": base_scores,
    }
    if units is not None or page_units:
        bundle["units"] = {page: page_units[page] for page in selected_pages if page in page_units}
    return validate_pairs(bundle)


def partition_query_ids(manifest, partition, selected_ids=None):
    """Resolve the expected population before reading candidate rows."""
    validate_split_manifest(manifest)
    if partition not in ("train", "validation", "test"):
        raise ValueError("partition must be train, validation or test")
    assigned = [query for query, role in manifest["splits"].items() if role == partition]
    if selected_ids is not None:
        unrelated = sorted(set(selected_ids) - set(assigned))
        if unrelated:
            raise ValueError(f"query IDs are not assigned to partition {partition!r}: {unrelated}")
        assigned = selected_ids
    if not assigned:
        raise ValueError(f"partition {partition!r} contains no selected queries")
    return assigned


def subset_partition(bundle, manifest, partition, selected_ids=None):
    """Return a leakage-checked subset and its indices into original score vectors."""
    validate_pairs(bundle)
    expected = set(partition_query_ids(manifest, partition, selected_ids))
    missing = sorted(expected - bundle["queries"].keys())
    if missing:
        raise ValueError(f"pairs lack required queries for partition {partition!r}: {missing}")
    queries = {query: text for query, text in bundle["queries"].items() if query in expected}
    indices = [index for index, (query, _) in enumerate(bundle["pairs"]) if query in queries]
    pairs = [bundle["pairs"][index] for index in indices]
    pages = dict.fromkeys(page for _, page in pairs)
    subset = {
        "dataset": bundle["dataset"], "top_k": bundle["top_k"], "synthetic": bundle.get("synthetic", False),
        "partition": partition, "queries": queries, "pairs": pairs,
        "pages": {page: bundle["pages"][page] for page in pages},
    }
    if "base_scores" in bundle:
        subset["base_scores"] = [bundle["base_scores"][index] for index in indices]
    if "units" in bundle:
        subset["units"] = {page: bundle["units"][page] for page in pages}
    return subset, indices


def lexical_scores(bundle):
    """Toy exact-word overlap for the offline demo."""
    tokens = {query: set(re.findall(r"\w+", text.casefold())) for query, text in bundle["queries"].items()}
    pages = {page: set(re.findall(r"\w+", text.casefold())) for page, text in bundle["pages"].items()}
    return [float(len(tokens[query] & pages[page])) for query, page in bundle["pairs"]]
