"""Exercita o bloco de publicação real com Git local e gerador/rede simulados."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "Git e bash necessários")
class PublishRaceTests(unittest.TestCase):
    def run_git(self, cwd, *args):
        return subprocess.run([self.git, *args], cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def scenario(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            self.git = shutil.which("git")
            origin, worker, peer = [base / x for x in ("origin.git", "worker", "peer")]
            origin.mkdir()
            self.run_git(origin, "init", "--bare", "--initial-branch=main")
            self.run_git(base, "clone", str(origin), str(worker))
            self.run_git(worker, "config", "user.name", "Test")
            self.run_git(worker, "config", "user.email", "test@example.invalid")
            (worker / "data").mkdir()
            (worker / "data/lotofacil.csv").write_text("original\n")
            (worker / "scripts").mkdir()
            (worker / "scripts/upstream.txt").write_text("original code\n")
            self.run_git(worker, "add", ".")
            self.run_git(worker, "commit", "-m", "Initial")
            self.run_git(worker, "push", "origin", "main")
            self.run_git(base, "clone", str(origin), str(peer))
            self.run_git(peer, "config", "user.name", "Other writer")
            self.run_git(peer, "config", "user.email", "other@example.invalid")
            binary = base / "bin"
            binary.mkdir()
            # The data generator is deliberately simulated. Test the real
            # workflow's Git retry logic independently from updater unit tests.
            (binary / "python").write_text('#!/bin/bash\nset -e\nif [[ "$1" == "scripts/update_lotofacil_csv.py" && "${2:-}" != "--validate-only" ]]; then\n  grep -qxF generated data/lotofacil.csv || echo generated >> data/lotofacil.csv\nfi\n')
            (binary / "sleep").write_text("#!/bin/bash\nexit 0\n")
            (binary / "git").write_text('''#!/bin/bash
set -e
if [[ "$1" == "push" && ! -e "$MARKER" ]]; then
  touch "$MARKER"
  if [[ "$MODE" == "race" ]]; then
    echo concurrent >> "$PEER/data/lotofacil.csv"
    echo changed >> "$PEER/scripts/upstream.txt"
    "$REAL_GIT" -C "$PEER" add .
    "$REAL_GIT" -C "$PEER" commit -m "Concurrent upstream data and code"
    "$REAL_GIT" -C "$PEER" push origin main
  elif [[ "$MODE" == "lost-response" ]]; then
    "$REAL_GIT" "$@"
    exit 1
  fi
fi
exec "$REAL_GIT" "$@"
''')
            for path in binary.iterdir():
                path.chmod(0o755)
            workflow = (ROOT / ".github/workflows/update-lotofacil.yml").read_text()
            body = workflow.split("        run: |\n", 1)[1]
            script = "\n".join(line[10:] for line in body.splitlines())
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"], REAL_GIT=self.git, PEER=str(peer), MARKER=str(base / "once"), MODE=mode)
            output = subprocess.run(["bash", "-c", script], cwd=worker, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
            self.run_git(peer, "pull", "--ff-only")
            data = (peer / "data/lotofacil.csv").read_text().splitlines()
            self.assertEqual(data.count("original"), 1)
            self.assertEqual(data.count("generated"), 1)
            if mode == "race":
                self.assertEqual(data.count("concurrent"), 1)
                self.assertIn("changed", (peer / "scripts/upstream.txt").read_text())
            self.assertEqual(self.run_git(worker, "rev-parse", "HEAD"), self.run_git(peer, "rev-parse", "HEAD"))

    def test_concurrent_upstream_csv_and_code_are_preserved(self):
        self.scenario("race")

    def test_successful_push_with_lost_response_is_idempotent(self):
        self.scenario("lost-response")

    def test_single_writer_and_read_only_ci(self):
        updater = (ROOT / ".github/workflows/update-lotofacil.yml").read_text()
        ci = (ROOT / ".github/workflows/teste.yml").read_text()
        self.assertIn("group: lotofacil-csv-writer", updater)
        self.assertIn("cancel-in-progress: false", updater)
        self.assertNotIn("git pull", updater)
        self.assertNotIn("push --force", updater)
        self.assertNotIn("schedule:", ci)
        self.assertNotIn("contents: write", ci)
        self.assertIn("contents: read", ci)


if __name__ == "__main__":
    unittest.main()
