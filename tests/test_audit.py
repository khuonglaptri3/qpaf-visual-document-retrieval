"""Filesystem/CLI contracts for M1.4; fixtures are not research evidence."""

import csv
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_repository.py"
sys.path.insert(0, str(SCRIPT.parents[1] / "src"))
from qpaf import audit

ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "research"
        self.root.mkdir()
        self.output = self.root / "evidence" / "snapshot"

    def write(self, name, content=b"abc"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def generate(self):
        result = self.cli("--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / "audit_metadata.json").is_file())
        return json.loads((self.output / "audit_metadata.json").read_text("utf-8"))

    def rows(self, name):
        with (self.output / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_known_bytes_and_unicode_path_are_hashed(self):
        self.write("docs/dữ liệu.txt")
        self.generate()
        rows = self.rows("hash_manifest.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "docs/dữ liệu.txt")
        self.assertEqual(rows[0]["sha256"], ABC_SHA256)
        self.assertEqual(rows[0]["size_bytes"], "3")

    def test_real_assets_are_classified_without_claiming_provenance(self):
        self.write("src/qpaf/fusion.py")
        self.write("data/raw/pages.jsonl")
        self.write("configs/pilot.toml")
        self.write("results/run-001/predictions.csv")
        self.generate()
        self.assertEqual(self.rows("data_inventory.csv")[0]["path"], "data/raw/pages.jsonl")
        self.assertEqual(self.rows("config_inventory.csv")[0]["path"], "configs/pilot.toml")
        run = self.rows("run_inventory.csv")[0]
        self.assertEqual(run["path"], "results/run-001/predictions.csv")
        self.assertEqual(run["status"], "PROVENANCE_UNVERIFIED")

    def test_empty_research_folders_are_gaps_not_a_pass(self):
        for folder in ("data", "configs", "results"):
            self.write(folder + "/README.md", b"Instructions only")
        metadata = self.generate()
        self.assertEqual(metadata["status"], "PARTIAL")
        self.assertEqual(self.rows("data_inventory.csv"), [])
        gaps = (self.output / "gap_log.md").read_text("utf-8")
        for code in ("DATA_MISSING", "CONFIG_MISSING", "RUNS_MISSING", "PROVENANCE_REVIEW_REQUIRED"):
            self.assertIn(code, gaps)

    def test_audit_infrastructure_is_not_research_method_code(self):
        self.write("src/qpaf/audit.py")
        self.write("src/qpaf/__init__.py")
        self.write("scripts/audit_repository.py")
        self.generate()
        self.assertIn("RESEARCH_CODE_MISSING", (self.output / "gap_log.md").read_text("utf-8"))

    def test_credentials_and_generated_evidence_are_excluded(self):
        self.write("README.md")
        for name in (".env", ".env.local", "secrets/private.pem", ".git/config", ".venv/lib.py", "evidence/previous/report.csv"):
            self.write(name, b"do not include")
        self.generate()
        self.assertEqual([row["path"] for row in self.rows("hash_manifest.csv")], ["README.md"])

    def test_existing_output_is_preserved(self):
        self.write("README.md")
        self.generate()
        before = (self.output / "hash_manifest.csv").read_bytes()
        self.write("README.md", b"modified")
        result = self.cli("--output", self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exists", result.stderr.lower())
        self.assertEqual((self.output / "hash_manifest.csv").read_bytes(), before)

    def test_output_cannot_escape_root(self):
        outside = self.root.parent / "outside"
        result = self.cli("--output", outside)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root", result.stderr.lower())
        self.assertFalse(outside.exists())

    def test_nonexistent_root_is_rejected_without_creation(self):
        missing = self.root / "missing"
        result = self.cli("--root", missing, "--output", missing / "evidence")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("root must be an existing directory", result.stderr.lower())
        self.assertFalse(missing.exists())

    def test_verification_detects_modified_and_deleted_content(self):
        path = self.write("data/raw/page.txt")
        self.generate()
        manifest = self.output / "hash_manifest.csv"
        result = self.cli("--verify", manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        path.write_bytes(b"abd")
        result = self.cli("--verify", manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("data/raw/page.txt", result.stdout + result.stderr)
        path.unlink()
        result = self.cli("--verify", manifest)
        self.assertNotEqual(result.returncode, 0)

    def test_empty_or_malformed_manifest_is_rejected(self):
        manifest = self.write("manifest.csv", b"path,sha256,size_bytes\n")
        result = self.cli("--verify", manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty", (result.stdout + result.stderr).lower())
        manifest.write_text("wrong,columns\na,b\n", encoding="utf-8")
        result = self.cli("--verify", manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("column", (result.stdout + result.stderr).lower())

    def test_manifest_path_traversal_is_rejected(self):
        (self.root.parent / "outside.txt").write_bytes(b"abc")
        manifest = self.write("manifest.csv", f"path,sha256,size_bytes\n../outside.txt,{ABC_SHA256},3\n".encode())
        result = self.cli("--verify", manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe", (result.stdout + result.stderr).lower())

    def test_symlink_is_not_followed(self):
        outside = self.root.parent / "outside.txt"
        outside.write_bytes(b"abc")
        try:
            (self.root / "linked.txt").symlink_to(outside)
        except OSError:
            self.skipTest("Host does not permit unprivileged symlinks")
        self.write("README.md")
        self.generate()
        self.assertEqual([row["path"] for row in self.rows("hash_manifest.csv")], ["README.md"])

    @unittest.skipUnless(os.name == "nt", "Windows junction compatibility")
    def test_junction_is_excluded_without_path_is_junction(self):
        outside = self.root.parent / "external"
        outside.mkdir()
        (outside / "outside.txt").write_bytes(b"abc")
        link = self.root / "linked-directory"
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = f"$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction -Path {quote(link)} -Target {quote(outside)} | Out-Null"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=30)
        if result.returncode:
            self.skipTest("Host does not permit directory junctions: " + result.stderr.strip())
        self.write("README.md")
        # Emulate the missing Path helper on 3.11, while using a real junction.
        with patch.object(Path, "is_junction", return_value=False, create=True):
            rows, excluded, _ = audit.collect_files(self.root, self.output)
        self.assertEqual([row["path"] for row in rows], ["README.md"])
        self.assertIn("linked-directory/", excluded)

    def test_replaced_file_with_same_size_and_mtime_has_no_valid_hash(self):
        target = self.write("data/raw/page.txt")
        before = target.stat()
        replacement = self.root.parent / "replacement.txt"
        replacement.write_bytes(b"xyz")
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        original_open = Path.open

        @contextmanager
        def replacing_open(path, *args, **kwargs):
            with original_open(path, *args, **kwargs) as stream:
                yield stream
            if path == target:
                os.replace(replacement, target)

        # The real file changes immediately after its read handle closes.
        with patch.object(Path, "open", replacing_open):
            rows, _, errors = audit.collect_files(self.root, self.output)
        self.assertEqual(target.read_bytes(), b"xyz")
        self.assertEqual(rows[0]["status"], "ERROR")
        self.assertEqual(rows[0]["sha256"], "")
        self.assertTrue(errors)

    def test_path_and_descriptor_change_times_are_compared_separately(self):
        target = self.write("data/raw/page.txt")
        original_fstat = os.fstat

        def descriptor_stat(fd):
            info = original_fstat(fd)
            values = {key: getattr(info, key) for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")}
            # Windows stat and fstat can expose different ctime semantics.
            values["st_ctime_ns"] += 1_000_000
            return SimpleNamespace(**values)

        with patch.object(audit.os, "fstat", descriptor_stat):
            self.assertEqual(audit.digest_file(target), (3, ABC_SHA256))


if __name__ == "__main__":
    unittest.main()
