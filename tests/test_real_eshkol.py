from __future__ import annotations

import os
from pathlib import Path

import pytest
from jupyter_helpers import execute_and_collect, started_kernel

from eshkol_kernel.session import EshkolReplSession


def real_repl_path() -> Path:
    configured = os.environ.get("ESHKOL_REAL_REPL")
    if not configured:
        pytest.skip("Set ESHKOL_REAL_REPL=/path/to/eshkol-repl to run real Eshkol smoke tests.")
    path = Path(configured)
    if not path.exists():
        pytest.skip(f"ESHKOL_REAL_REPL does not exist: {path}")
    return path


def test_real_eshkol_session_smoke() -> None:
    repl = real_repl_path()
    session = EshkolReplSession(executable=str(repl), load_stdlib=False, timeout=10, start_timeout=10)
    try:
        result = session.execute("(+ 1 2 3)")
    finally:
        session.close()

    assert result.ok
    assert result.stdout == "6\n"


def test_real_eshkol_through_jupyter_client(tmp_path: Path) -> None:
    repl = real_repl_path()

    with started_kernel(
        tmp_path,
        kernel_name="eshkol-real",
        eshkol_repl=str(repl),
        repl_args="",
        load_stdlib=False,
    ) as client:
        reply, outputs = execute_and_collect(client, "(+ 1 2 3)")

    assert reply["status"] == "ok"
    assert outputs == [("stdout", "6\n")]
