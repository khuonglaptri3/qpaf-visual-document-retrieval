from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "vidore_v3_short_oracle.ipynb"
KAGGLE_NOTEBOOK = ROOT / "notebooks" / "vidore_v3_short_oracle_kaggle.ipynb"


class ViDoReShortOracleNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.all_source = "\n".join(
            "".join(cell["source"]) for cell in cls.notebook["cells"]
        )

    def test_notebook_is_clean_and_code_cells_parse(self) -> None:
        self.assertEqual(self.notebook["nbformat"], 4)
        for index, cell in enumerate(self.notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            self.assertIsNone(cell["execution_count"])
            self.assertEqual(cell["outputs"], [])
            source = "".join(cell["source"])
            if not source.lstrip().startswith("%pip"):
                ast.parse(source, filename=f"notebook-cell-{index}")

    def test_pinned_scope_and_preflight_are_present(self) -> None:
        self.assertIn("vidore/vidore_v3_finance_en", self.all_source)
        self.assertIn("7f432c176d82e27546501ad8064a713ac3071809", self.all_source)
        self.assertIn("gpu_gb < 23.5", self.all_source)
        self.assertIn("assert len(query_ids) == 309", self.all_source)
        self.assertIn("assert len(corpus_ids) == 2942", self.all_source)

    def test_registered_candidate_and_oracle_contract_is_present(self) -> None:
        self.assertIn("make_candidate_indices(200, 100, 100)", self.all_source)
        self.assertIn("make_candidate_indices(300, 200, 200)", self.all_source)
        self.assertIn("if final_coverage < 0.95", self.all_source)
        self.assertIn('grids=("w7",)', self.all_source)
        self.assertIn("n_bootstrap=2_000", self.all_source)
        self.assertIn("delta_qarf_vs_global", self.all_source)
        self.assertIn("delta_qpaf_vs_qarf", self.all_source)

    def test_images_are_loaded_lazily(self) -> None:
        self.assertIn("class LazyCorpusImages", self.all_source)
        self.assertNotIn(
            'corpus_images = [row["image"].convert("RGB") for row in corpus]',
            self.all_source,
        )


class ViDoReShortOracleKaggleNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.notebook = json.loads(KAGGLE_NOTEBOOK.read_text(encoding="utf-8"))
        cls.all_source = "\n".join(
            "".join(cell["source"]) for cell in cls.notebook["cells"]
        )

    def test_kaggle_notebook_is_clean_and_code_cells_parse(self) -> None:
        for index, cell in enumerate(self.notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            self.assertIsNone(cell["execution_count"])
            self.assertEqual(cell["outputs"], [])
            source = "".join(cell["source"])
            if not source.lstrip().startswith("%pip"):
                ast.parse(source, filename=f"kaggle-notebook-cell-{index}")

    def test_kaggle_storage_and_download_contract(self) -> None:
        self.assertIn("/kaggle/working/vidore_v3_finance_en_short_oracle", self.all_source)
        self.assertIn("/kaggle/temp/vidore_v3_finance_en_short_oracle", self.all_source)
        self.assertIn("/kaggle/input/vidore-v3-short-oracle-cache", self.all_source)
        self.assertIn("shutil.make_archive", self.all_source)
        self.assertIn('write_json(success, "/kaggle/working/_SUCCESS.json")', self.all_source)
        self.assertIn("artifact_manifest.json", self.all_source)
        self.assertIn("PILOT_FEASIBILITY.md", self.all_source)
        self.assertNotIn("google.colab", self.all_source)
        self.assertNotIn("/content/drive", self.all_source)

    def test_kaggle_finalizer_requires_every_public_artifact(self) -> None:
        for filename in [
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
        ]:
            self.assertIn(f'"{filename}"', self.all_source)
        self.assertIn("if missing_artifacts", self.all_source)
        self.assertIn("file_sha256", self.all_source)

    def test_kaggle_version_preserves_registered_protocol(self) -> None:
        self.assertIn("gpu_gb < 23.5", self.all_source)
        self.assertIn("make_candidate_indices(200, 100, 100)", self.all_source)
        self.assertIn("make_candidate_indices(300, 200, 200)", self.all_source)
        self.assertIn('grids=("w7",)', self.all_source)
        self.assertIn("n_bootstrap=2_000", self.all_source)


if __name__ == "__main__":
    unittest.main()
