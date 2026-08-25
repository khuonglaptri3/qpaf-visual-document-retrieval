from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notebooks" / "vidore_v3_short_oracle.ipynb"
OUTPUT = ROOT / "notebooks" / "vidore_v3_short_oracle_kaggle.ipynb"


def cell_text(cell: dict) -> str:
    return "".join(cell["source"])


def set_cell_text(cell: dict, text: str) -> None:
    cell["source"] = text.splitlines(keepends=True)


notebook = json.loads(SOURCE.read_text(encoding="utf-8"))

intro = cell_text(notebook["cells"][0])
intro = intro.replace("Short QARF/QPAF Oracle", "Short QARF/QPAF Oracle — Kaggle")
intro = intro.replace(
    "Run every cell in order. The only interactive step is authorizing Google Drive.",
    "Enable Internet and select an accelerator with at least 24 GB VRAM, then run every cell in order. "
    "All outputs are written under `/kaggle/working`.",
)
set_cell_text(notebook["cells"][0], intro)

environment_cell = next(
    cell for cell in notebook["cells"] if "SEED = 20260820" in cell_text(cell)
)
environment = cell_text(environment_cell)
environment = environment.replace("from google.colab import drive\n", "")
old_storage = '''drive.mount("/content/drive")
RUN_ROOT = Path("/content/drive/MyDrive/vidore_v3_finance_en_short_oracle")
CACHE_DIR = RUN_ROOT / "cache"
OUTPUT_DIR = RUN_ROOT / "output"
HF_HOME = RUN_ROOT / "hf_cache"
HF_HUB_CACHE = HF_HOME / "hub"
HF_DATASETS_CACHE = HF_HOME / "datasets"
for directory in [CACHE_DIR, OUTPUT_DIR, HF_HOME, HF_HUB_CACHE, HF_DATASETS_CACHE]:
    directory.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(HF_HOME)
os.environ["HF_HUB_CACHE"] = str(HF_HUB_CACHE)
os.environ["HF_DATASETS_CACHE"] = str(HF_DATASETS_CACHE)
'''
new_storage = '''RUN_ROOT = Path("/kaggle/working/vidore_v3_finance_en_short_oracle")
TEMP_ROOT = Path("/kaggle/temp/vidore_v3_finance_en_short_oracle")
WORK_CACHE_DIR = TEMP_ROOT / "cache"
INPUT_CACHE_DIR = Path("/kaggle/input/vidore-v3-short-oracle-cache")
OUTPUT_DIR = RUN_ROOT / "output"
HF_HOME = TEMP_ROOT / "hf_cache"
HF_HUB_CACHE = HF_HOME / "hub"
HF_DATASETS_CACHE = HF_HOME / "datasets"
for directory in [RUN_ROOT, WORK_CACHE_DIR, OUTPUT_DIR, HF_HOME, HF_HUB_CACHE, HF_DATASETS_CACHE]:
    directory.mkdir(parents=True, exist_ok=True)

class CacheResolver:
    # Prefer a checkpoint created in this run, then an optional read-only Kaggle input.
    def __truediv__(self, filename):
        working = WORK_CACHE_DIR / filename
        attached = INPUT_CACHE_DIR / filename
        return working if working.exists() or not attached.exists() else attached

CACHE_DIR = CacheResolver()
os.environ["HF_HOME"] = str(HF_HOME)
os.environ["HF_HUB_CACHE"] = str(HF_HUB_CACHE)
os.environ["HF_DATASETS_CACHE"] = str(HF_DATASETS_CACHE)
'''
if old_storage not in environment:
    raise RuntimeError("Colab storage block changed; update the Kaggle transformation")
environment = environment.replace(old_storage, new_storage)
environment = environment.replace(
    "model and dataset downloads persist on Drive",
    "large model and embedding caches remain outside the saved Kaggle output",
)
environment = environment.replace(
    'print(f"Persistent run directory: {RUN_ROOT}")',
    'print(f"Saved Kaggle output directory: {RUN_ROOT}")\n'
    'print(f"Temporary cache directory: {TEMP_ROOT}")\n'
    'print(f"Optional attached cache: {INPUT_CACHE_DIR}")',
)
set_cell_text(environment_cell, environment)

visual_cell = next(
    cell for cell in notebook["cells"] if "colqwen25_candidate_scores.pt" in cell_text(cell)
)
visual = cell_text(visual_cell)
old_visual_cache = '''visual_score_path = CACHE_DIR / "colqwen25_candidate_scores.pt"
if visual_score_path.exists():
    visual_scores = load_torch(visual_score_path).numpy()
else:
    visual_scores = np.full((len(query_ids), len(corpus_ids)), np.nan, dtype=np.float32)
'''
new_visual_cache = '''visual_score_path = WORK_CACHE_DIR / "colqwen25_candidate_scores.pt"
visual_score_read_path = CACHE_DIR / "colqwen25_candidate_scores.pt"
if visual_score_read_path.exists():
    visual_scores = load_torch(visual_score_read_path).numpy()
else:
    visual_scores = np.full((len(query_ids), len(corpus_ids)), np.nan, dtype=np.float32)
'''
if old_visual_cache not in visual:
    raise RuntimeError("ColQwen cache block changed; update the Kaggle transformation")
visual = visual.replace(old_visual_cache, new_visual_cache)
set_cell_text(visual_cell, visual)

final_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": '''import datetime
import hashlib
import shutil

required_artifacts = [
    "run_manifest.yaml",
    "coverage_report.json",
    "retrieval_scores.parquet",
    "fusion_oracle_results.jsonl",
    "fusion_oracle_summary.json",
    "fusion_oracle_subgroups.csv",
    "fusion_oracle_query_summary.parquet",
    "global_qarf_qpaf_oracle.png",
    "pilot_feasibility.json",
    "pilot_feasibility.md",
]
missing_artifacts = [name for name in required_artifacts if not (OUTPUT_DIR / name).is_file()]
if missing_artifacts:
    raise RuntimeError(f"Cannot finalize Kaggle output; missing artifacts: {missing_artifacts}")

def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

artifact_inventory = {
    "study": "vidore_v3_finance_en_short_oracle",
    "status": "complete",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "files": [
        {
            "name": name,
            "bytes": (OUTPUT_DIR / name).stat().st_size,
            "sha256": file_sha256(OUTPUT_DIR / name),
        }
        for name in required_artifacts
    ],
}
write_json(artifact_inventory, OUTPUT_DIR / "artifact_manifest.json")

archive_base = "/kaggle/working/vidore_v3_finance_en_short_oracle_results"
archive_path = Path(shutil.make_archive(archive_base, "zip", root_dir=OUTPUT_DIR))

# Top-level copies make the main conclusion and plot visible in Kaggle's Output panel.
shutil.copy2(OUTPUT_DIR / "pilot_feasibility.md", "/kaggle/working/PILOT_FEASIBILITY.md")
shutil.copy2(OUTPUT_DIR / "fusion_oracle_summary.json", "/kaggle/working/fusion_oracle_summary.json")
shutil.copy2(OUTPUT_DIR / "global_qarf_qpaf_oracle.png", "/kaggle/working/global_qarf_qpaf_oracle.png")

results_readme = """# Saved outputs

The run completed only if `_SUCCESS.json` is present.

- Start with `PILOT_FEASIBILITY.md` for the QARF/QPAF feasibility decision.
- Inspect `global_qarf_qpaf_oracle.png` for the three-level comparison.
- Download `vidore_v3_finance_en_short_oracle_results.zip` for every result artifact.
- Use `fusion_oracle_summary.json` for machine-readable aggregate metrics.

Large model and embedding caches are intentionally kept under `/kaggle/temp` and are
not included in Save Version. To reuse caches across versions, publish the cache folder
as a private Kaggle Dataset named `vidore-v3-short-oracle-cache` and attach it as input.
"""
Path("/kaggle/working/README_RESULTS.md").write_text(results_readme, encoding="utf-8")

success = {
    "study": "vidore_v3_finance_en_short_oracle",
    "status": "complete",
    "archive": archive_path.name,
    "archive_bytes": archive_path.stat().st_size,
    "archive_sha256": file_sha256(archive_path),
    "artifact_count": len(required_artifacts),
}
write_json(success, "/kaggle/working/_SUCCESS.json")

print(feasibility_markdown(feasibility))
print(f"Verified {len(required_artifacts)} required artifacts")
print(f"Download from Kaggle Output: {archive_path}")
print("Run completion marker: /kaggle/working/_SUCCESS.json")
'''.splitlines(keepends=True),
}
notebook["cells"].append(final_cell)
notebook["metadata"].pop("colab", None)
notebook["metadata"]["kaggle"] = {
    "accelerator": "gpu",
    "dataSources": [],
    "dockerImageVersionId": None,
    "isInternetEnabled": True,
    "language": "python",
    "sourceType": "notebook",
}

OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(OUTPUT)
