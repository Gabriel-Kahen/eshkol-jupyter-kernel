from __future__ import annotations

import json
from pathlib import Path

from eshkol_kernel.install import install_kernel_spec


def test_install_kernel_spec_to_prefix(tmp_path: Path) -> None:
    destination = install_kernel_spec(
        prefix=str(tmp_path),
        name="eshkol-test",
        display_name="Eshkol Test",
        eshkol_repl="/opt/eshkol/bin/eshkol-repl",
        load_stdlib=False,
    )
    kernel_json = Path(destination) / "kernel.json"
    data = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert data["display_name"] == "Eshkol Test"
    assert data["language"] == "eshkol"
    assert data["argv"][1:3] == ["-m", "eshkol_kernel"]
    assert data["env"]["ESHKOL_REPL"] == "/opt/eshkol/bin/eshkol-repl"
    assert data["env"]["ESHKOL_KERNEL_LOAD_STDLIB"] == "0"


def test_install_kernel_spec_normalizes_relative_repl_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    destination = install_kernel_spec(
        prefix=str(tmp_path / "jupyter-prefix"),
        name="eshkol-relative",
        eshkol_repl=".external/eshkol/bin/eshkol-repl",
    )

    kernel_json = Path(destination) / "kernel.json"
    data = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert data["env"]["ESHKOL_REPL"] == str((tmp_path / ".external/eshkol/bin/eshkol-repl").resolve())


def test_install_kernel_spec_expands_home_repl_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    destination = install_kernel_spec(
        prefix=str(tmp_path / "jupyter-prefix"),
        name="eshkol-home",
        eshkol_repl="~/eshkol/bin/eshkol-repl",
    )

    kernel_json = Path(destination) / "kernel.json"
    data = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert data["env"]["ESHKOL_REPL"] == str((tmp_path / "eshkol/bin/eshkol-repl").resolve())
