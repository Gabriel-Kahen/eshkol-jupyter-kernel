from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "scripts" / "run_compatibility.py"


@pytest.mark.parametrize("ref", ["latest", "main", "master", "HEAD"])
def test_runner_rejects_mutable_runtime_labels(tmp_path: Path, ref: str) -> None:
    result = subprocess.run([sys.executable, str(RUNNER), "--repl", sys.executable,
                             "--runtime-ref", ref, "--output", str(tmp_path / "evidence")],
                            text=True, capture_output=True)
    assert result.returncode == 2
    assert "fixed revision" in result.stderr
    assert not (tmp_path / "evidence").exists()


def test_missing_handshake_retains_blocked_evidence_without_running_pytest(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    result = subprocess.run([sys.executable, str(RUNNER), "--repl", sys.executable,
                             "--runtime-ref", "test-executable", "--output", str(output)],
                            text=True, capture_output=True)
    assert result.returncode == 2
    report = json.loads((output / "provenance.json").read_text())
    assert report["outcome"].startswith("blocked")
    assert report["handshake"] == []
    assert report["probe"]["returncode"] != 0
    assert report["kernel_head"]["returncode"] == 0
    assert not (output / "junit.xml").exists()
