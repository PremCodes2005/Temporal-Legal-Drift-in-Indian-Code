from __future__ import annotations

import gzip
import subprocess
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import canonical_json_bytes
from temporal_legal_drift.reproducibility.builder import restore_release_inputs, verify_release


ROOT = Path(__file__).resolve().parents[2]


class ReleaseRefusalTests(unittest.TestCase):
    def test_existing_releases_are_never_recut(self) -> None:
        for release_id in ("v0.1.0", "v0.2.0"):
            with self.assertRaises(FileExistsError):
                verify_release(ROOT, release_id)

    def test_dirty_working_tree_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = lambda *args: subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)  # noqa: E731
            git("init", "-q")
            (root / "file.txt").write_text("committed\n")
            git("add", "file.txt")
            git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "x")
            (root / "file.txt").write_text("uncommitted\n")
            with self.assertRaisesRegex(ValueError, "clean working tree"):
                verify_release(root, "v9.9.9")

    def test_tampered_release_input_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "data/releases/reproducibility-vtest"
            (release / "inputs/data/interim").mkdir(parents=True)
            (release / "inputs/data/interim/x.json.gz").write_bytes(gzip.compress(b"tampered", mtime=0))
            (release / "manifest.json").write_bytes(canonical_json_bytes(
                {"release_inputs": {"data/interim/x.json": sha256(b"original").hexdigest()}}
            ))
            (root / "data/releases/active_release.json").write_bytes(canonical_json_bytes({
                "release_id": "vtest", "manifest_path": "data/releases/reproducibility-vtest/manifest.json",
            }))
            with self.assertRaisesRegex(ValueError, "does not match its declared hash"):
                restore_release_inputs(root)
            self.assertFalse((root / "data/interim/x.json").exists())


if __name__ == "__main__":
    unittest.main()
