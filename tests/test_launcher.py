from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "checkout with spaces"
        self.root.mkdir()
        self.launcher = self.root / "run"
        shutil.copy2(ROOT / "run", self.launcher)

    def test_uses_local_python_and_preserves_arguments_and_working_directory(self):
        python = self.root / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\nexit 7\n')
        python.chmod(0o755)
        result = subprocess.run(
            [str(self.launcher), "--plain", "--directory", "results with spaces"],
            cwd=self.directory.name, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.splitlines(), [
            str(Path(self.directory.name).resolve()), "-B",
            str(self.root / "exercise.py"), "--plain", "--directory",
            "results with spaces",
        ])
        self.assertEqual(result.stderr, "")

    def test_missing_virtualenv_has_setup_guidance(self):
        result = subprocess.run(
            [str(self.launcher)], cwd=self.directory.name,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("python3 -m venv .venv", result.stderr)
        self.assertIn(".venv/bin/python -m pip install -r requirements.txt", result.stderr)
        self.assertFalse((self.root / ".venv").exists())


if __name__ == "__main__":
    unittest.main()
