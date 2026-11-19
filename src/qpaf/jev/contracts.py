"""Validate shared files and write complete, byte-bound score caches."""
import hashlib
import json
import math
from numbers import Real
import os
from pathlib import Path
import tempfile


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _unique_keys(entries):
    result = {}
    for key, value in entries:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def decode_json(raw, source):
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
    except ValueError as exc:
        raise ValueError(f"{source}: {exc}") from exc


def read_json(path):
    return decode_json(Path(path).read_bytes(), path)


def atomic_write(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False)
    try:
        with temp:
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp.name, target)
    finally:
        Path(temp.name).unlink(missing_ok=True)


def encode_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value):
    atomic_write(path, encode_json(value))


def text_id(value):
    return isinstance(value, str) and bool(value.strip())


def number(value, name):
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            result = float(value)
            if math.isfinite(result):
                return result
        except OverflowError:
            pass
    raise ValueError(f"{name}: expected a finite number")


def positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name}: expected a positive integer")
    return value


def score_vector(scores, count, name="scores"):
    if not isinstance(scores, (list, tuple)) or len(scores) != count:
        raise ValueError(f"{name}: expected exactly {count} numbers in pair order")
    return [number(score, f"{name}[{index}]") for index, score in enumerate(scores)]


def validate_pairs(bundle):
    if not isinstance(bundle, dict) or not text_id(bundle.get("dataset")):
        raise ValueError("pairs: expected an object with a nonempty dataset name")
    positive_int(bundle.get("top_k"), "top_k")
    if "synthetic" in bundle and type(bundle["synthetic"]) is not bool:
        raise ValueError("pairs.synthetic must be boolean")
    queries, pages, pairs = (bundle.get(key) for key in ("queries", "pages", "pairs"))
    if not isinstance(queries, dict) or not queries:
        raise ValueError("queries: expected a nonempty mapping from query IDs to text")
    for query_id, query in queries.items():
        if not text_id(query_id) or not text_id(query):
            raise ValueError(f"query {query_id!r}: ID and query text must be nonempty strings")
    if not isinstance(pages, dict):
        raise ValueError("pages: expected a mapping from page IDs to OCR strings")
    for page_id, ocr in pages.items():
        if not text_id(page_id) or not isinstance(ocr, str):
            raise ValueError(f"page {page_id!r}: expected a page ID and OCR string (possibly empty)")
    if not isinstance(pairs, list):
        raise ValueError("pairs: expected ordered [query_id, page_id] rows")
    units = bundle.get("units")
    if "units" in bundle and (
        not isinstance(units, dict)
        or any(not text_id(page) or not text_id(unit) for page, unit in units.items())
    ):
        raise ValueError("units: expected a mapping from page IDs to nonempty label-unit IDs")
    seen, covered = set(), set()
    for row in pairs:
        if not isinstance(row, (list, tuple)) or len(row) != 2 or not all(map(text_id, row)):
            raise ValueError(f"invalid pair {row!r}: expected [query_id, page_id]")
        query_id, page_id = row
        if (query_id, page_id) in seen:
            raise ValueError(f"duplicate pair ({query_id!r}, {page_id!r})")
        if query_id not in queries or page_id not in pages:
            raise ValueError(f"missing query text or OCR for pair ({query_id!r}, {page_id!r})")
        if units is not None and page_id not in units:
            raise ValueError(f"units: missing label unit for page {page_id!r}")
        seen.add((query_id, page_id))
        covered.add(query_id)
    if missing := sorted(queries.keys() - covered):
        raise ValueError(f"pairs: no candidates for queries {missing}")
    if "base_scores" in bundle:
        score_vector(bundle["base_scores"], len(pairs), "base_scores")
    return bundle


def read_pairs_snapshot(path):
    raw = Path(path).read_bytes()
    try:
        bundle = validate_pairs(decode_json(raw, path))
    except ValueError as exc:
        raise ValueError(f"invalid pairs file {path}: {exc}") from exc
    return bundle, raw


def load_pairs(path):
    bundle, _ = read_pairs_snapshot(path)
    return bundle


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("score cache: manifest must be a JSON object")
    if "synthetic" in manifest and type(manifest["synthetic"]) is not bool:
        raise ValueError("score cache: manifest.synthetic must be boolean")


def decode_scores(raw, path, bundle, pairs_sha256):
    cache = decode_json(raw, path)
    if not isinstance(cache, dict):
        raise ValueError(f"{path}: expected a score cache object")
    if cache.get("pairs_sha256") != pairs_sha256:
        raise ValueError(f"{path}: pairs_sha256 does not match the bytes of the pairs file")
    validate_manifest(cache.get("manifest"))
    score_vector(cache.get("scores"), len(bundle["pairs"]))
    return cache


def load_scores(path, pairs_path):
    bundle, raw = read_pairs_snapshot(pairs_path)
    return decode_scores(Path(path).read_bytes(), path, bundle, hashlib.sha256(raw).hexdigest())


def write_scores(path, pairs_path, scores, manifest, details=None, *, expected_pairs_sha256=None):
    if Path(path).resolve() == Path(pairs_path).resolve():
        raise ValueError("score cache output must differ from its input pairs file")
    bundle, raw = read_pairs_snapshot(pairs_path)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_pairs_sha256 is not None and expected_pairs_sha256 != digest:
        raise ValueError("pairs file changed since scoring; retry with stable inputs")
    scores = score_vector(scores, len(bundle["pairs"]))
    validate_manifest(manifest)
    cache = {"pairs_sha256": digest, "manifest": manifest, "scores": scores}
    if details is not None:
        cache["details"] = details
    write_json(path, cache)
    return cache


def baseline_scores(bundle):
    if "base_scores" not in bundle:
        raise ValueError("baseline and blend require explicit aligned base_scores in pairs JSON")
    return score_vector(bundle["base_scores"], len(bundle["pairs"]), "base_scores")


def validate_splits(bundle, manifest):
    validate_pairs(bundle)
    if not isinstance(manifest, dict):
        raise ValueError("split manifest: expected a JSON object")
    splits, groups = manifest.get("splits"), manifest.get("groups")
    if not isinstance(splits, dict) or not isinstance(groups, dict):
        raise ValueError("split manifest: splits and groups must be mappings")
    if missing := sorted(bundle["queries"].keys() - splits.keys()):
        raise ValueError(f"split manifest: queries missing assignments: {missing}")
    if splits.keys() != groups.keys():
        difference = splits.keys() ^ groups.keys()
        raise ValueError(f"split manifest: splits and groups must cover the same queries: {difference}")
    roles = {}
    for query_id, split in splits.items():
        group = groups[query_id]
        if not text_id(query_id) or split not in ("train", "validation", "test") or not text_id(group):
            raise ValueError(f"split manifest: invalid split or group for query {query_id!r}")
        if roles.setdefault(group, split) != split:
            raise ValueError(f"split manifest: group {group!r} spans partitions")
    return manifest
