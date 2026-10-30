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


@pytest.mark.skipif(sys.platform == "win32", reason="Executable test peer uses a POSIX shebang")
@pytest.mark.parametrize("frame", ["[]", "null", "1", "true", '"ready"', "{broken"])
def test_malformed_handshake_retains_blocked_evidence(tmp_path: Path, frame: str) -> None:
    peer = tmp_path / "malformed-repl"
    peer.write_text(f"#!{sys.executable}\nimport sys\nsys.stderr.write({'EREPL/1 ' + frame + chr(10)!r})\n")
    peer.chmod(0o755)
    output = tmp_path / "evidence"
    result = subprocess.run([sys.executable, str(RUNNER), "--repl", str(peer),
                             "--runtime-ref", "malformed-test-peer", "--output", str(output)],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 2, result.stderr
    report = json.loads((output / "provenance.json").read_text())
    assert report["outcome"].startswith("blocked")
    assert report["handshake"] == []
    assert frame in report["probe"]["stderr"]
    assert not (output / "junit.xml").exists()
