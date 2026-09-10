from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vimdoc_m3_prep", ROOT / "scripts/prepare_vimdoc_m3.py")
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)


def scores():
    return {
        "bm25": {"a_0": 10.0, "a_1": 10.0, "b_0": 0.0, "c_0": -100.0},
        "dense": {"a_0": 1.0, "a_1": 2.0, "b_0": 3.0, "c_0": -100.0},
        "visual": {"a_0": 0.5, "a_1": 0.5, "b_0": 0.5, "c_0": 0.5},
    }


def test_id_only_split_is_deterministic_disjoint_complete_and_namespaced():
    ids = [str(n) for n in range(20)]
    first = prep.propose_split(ids, "dev:20260820", 16)
    assert first == prep.propose_split(list(reversed(ids)), "dev:20260820", 16)
    assert not set(first["train_ids"]) & set(first["validation_ids"])
    assert set(first["train_ids"] + first["validation_ids"]) == set(ids)
    assert first != prep.propose_split(ids, "different:20260820", 16)
    assert first["status"] == "PROPOSED_NOT_ADOPTED"


@pytest.mark.parametrize("ids", [["x", "x"], ["x\ny"], [1, "2"], [], ["x\ty"]])
def test_ambiguous_or_duplicate_ids_rejected(ids):
    with pytest.raises(ValueError):
        prep.ids_sha256(ids)


@pytest.mark.parametrize("count", [0, 2, True])
def test_invalid_split_sizes_rejected(count):
    with pytest.raises(ValueError):
        prep.propose_split(["a", "b"], "dev", count)


def test_top_k_union_is_label_free_stable_and_uses_visual_not_dse():
    assert prep.candidate_union(scores(), 1) == ["a_0", "b_0"]
    reversed_input = {c: dict(reversed(list(s.items()))) for c, s in scores().items()}
    assert prep.candidate_union(reversed_input, 1) == ["a_0", "b_0"]
    bad = scores()
    bad["dse"] = bad.pop("visual")
    with pytest.raises(ValueError, match="DSE"):
        prep.candidate_union(bad)
    with pytest.raises(TypeError):
        prep.candidate_union(scores(), qrels={"a_0": 1})


def test_normalization_uses_only_union_and_zeroes_constant_channel():
    rows = prep.normalized_union(scores(), 1)
    assert rows == [
        {"page_id": "a_0", "scores": [1.0, 0.0, 0.0]},
        {"page_id": "b_0", "scores": [0.0, 1.0, 0.0]},
    ]


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), -float("inf"), True, "0"])
def test_nonfinite_or_nonnumeric_scores_rejected(bad_score):
    bad = scores()
    bad["dense"]["a_0"] = bad_score
    with pytest.raises(ValueError):
        prep.normalized_union(bad)


def test_missing_rescore_and_overflow_rejected():
    bad = scores()
    del bad["dense"]["a_0"]
    with pytest.raises(ValueError, match="universe"):
        prep.candidate_union(bad)
    bad = scores()
    bad["dense"].update({"a_0": 1e308, "a_1": -1e308})
    with pytest.raises(ValueError, match="overflow"):
        prep.normalized_union(bad)


def test_union_bound():
    supplied = {c: {f"d_{p:04}": float((p + shift) % 1000) for p in range(1000)}
                for c, shift in zip(prep.CHANNELS, (0, 300, 600))}
    assert len(prep.candidate_union(supplied)) == 600


def test_document_layout_retains_pages_and_deterministic_tie_order():
    layout = prep.document_layout(["long_doc_2", "b_0", "long_doc_10"])
    assert layout == {"page_ids": ["b_0", "long_doc_10", "long_doc_2"],
                      "document_ids": ["b", "long_doc"], "page_to_unit_groups": [0, 1, 1]}
    assert "relevance" not in layout  # No document labels fabricated onto pages.
    with pytest.raises(ValueError):
        prep.document_layout(["missing-suffix"])


def test_matched_configs_differ_only_in_granularity():
    config = json.loads((ROOT / prep.CONFIG).read_text())
    split = prep.propose_split(["a", "b", "c"], "test", 2)
    methods = prep.resolve_matched(config, split)
    assert methods["QARF"].pop("gate_granularity") == "query_masked_mean"
    assert methods["QPAF"].pop("gate_granularity") == "page"
    assert methods["QARF"] == methods["QPAF"]
    methods["QARF"]["shared_training"]["batch_size_queries"] = 1
    assert methods["QPAF"]["shared_training"]["batch_size_queries"] == 32
    config["matched_methods"]["QPAF"]["learning_rate"] = 0.1
    with pytest.raises(ValueError, match="granularity"):
        prep.resolve_matched(config, split)


def test_live_local_preflight_is_read_only_and_never_execution_ready():
    before = {p: prep.sha256_file(ROOT / p) for p in (*prep.INVENTORY, prep.MANIFEST)}
    result = prep.preflight(ROOT, include_ids=True)
    assert result["local_package_integrity"] == "PASS"
    assert result["ready_for_execution"] is False
    assert result["remote_state_verified"] is False
    assert result["real_score_cache_verified"] is False
    assert result["writes_performed"] is False
    split = result["split_proposal"]
    assert len(split["train_ids"]) == 1600 and len(split["validation_ids"]) == 400
    assert not set(split["train_ids"]) & set(split["validation_ids"])
    assert before == {p: prep.sha256_file(ROOT / p) for p in before}


@pytest.fixture
def package_copy(tmp_path):
    for relative in (*prep.INVENTORY, prep.MANIFEST):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def test_source_drift_and_manifest_inventory_omission_fail_closed(package_copy):
    source = package_copy / "src/oracle_study/learned/models.py"
    source.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash drift"):
        prep.preflight(package_copy)
    manifest = package_copy / prep.MANIFEST
    data = json.loads(manifest.read_text())
    data["files"] = data["files"][:-1]
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="inventory"):
        prep.preflight(package_copy)


@pytest.mark.parametrize("key,value", [("training_approved", True), ("approved_invocations", 1),
                                      ("modal_execution_approved", True), ("gpu_execution_approved", 0)])
def test_even_rehashed_config_cannot_enable_execution(package_copy, key, value):
    path = package_copy / prep.CONFIG
    config = json.loads(path.read_text())
    config["authorization"][key] = value
    path.write_text(json.dumps(config))
    manifest = package_copy / prep.MANIFEST
    data = json.loads(manifest.read_text())
    for entry in data["files"]:
        if entry["path"] == prep.CONFIG:
            entry["sha256"] = prep.sha256_file(path)
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="preparation ONLY"):
        prep.preflight(package_copy)


@pytest.mark.parametrize("argument", ["--train", "--extract", "--approve", "--modal", "--gpu"])
def test_cli_has_no_execution_switch(argument):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_vimdoc_m3.py"), argument],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_preparation_script_imports_only_small_standard_library_allowlist():
    tree = ast.parse((ROOT / "scripts/prepare_vimdoc_m3.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= {"__future__", "argparse", "copy", "hashlib", "json", "math", "pathlib"}
