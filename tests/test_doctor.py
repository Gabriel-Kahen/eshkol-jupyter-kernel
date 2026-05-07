from __future__ import annotations

import sys
from pathlib import Path

from eshkol_kernel.doctor import (
    DoctorOptions,
    check_kernelspec,
    check_repl,
    exit_code,
    linux_dependency_hint,
    missing_shared_libraries,
    resolve_repl,
    resolve_repl_value,
    run_doctor,
)

FAKE_REPL = Path(__file__).with_name("fake_eshkol_repl.py")


class FakeKernelSpec:
    def __init__(self, env: dict[str, str]) -> None:
        self.env = env


class FakeKernelSpecManager:
    def __init__(self, env: dict[str, str]) -> None:
        self.env = env

    def get_kernel_spec(self, kernel_name: str) -> FakeKernelSpec:
        return FakeKernelSpec(self.env)


def test_doctor_passes_with_fake_repl() -> None:
    results = run_doctor(
        DoctorOptions(
            eshkol_repl=sys.executable,
            repl_args=(str(FAKE_REPL),),
            skip_kernelspec=True,
        )
    )

    assert exit_code(results) == 0
    assert {result.name: result.status for result in results}["execution smoke test"] == "pass"


def test_doctor_fails_missing_repl() -> None:
    repl = resolve_repl("/definitely/not/eshkol-repl")
    result = check_repl(repl)

    assert result.status == "fail"
    assert "Could not find" in result.message


def test_doctor_hint_includes_external_runtime_path(tmp_path: Path, monkeypatch) -> None:
    external = tmp_path / ".external" / "eshkol" / "bin" / "eshkol-repl"
    external.parent.mkdir(parents=True)
    external.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = check_repl(resolve_repl("/definitely/not/eshkol-repl"))

    assert str(external) in result.detail
    assert "--eshkol-repl" in result.detail


def test_resolve_repl_value_expands_home(tmp_path: Path, monkeypatch) -> None:
    repl = tmp_path / "eshkol" / "bin" / "eshkol-repl"
    repl.parent.mkdir(parents=True)
    repl.write_text("#!/bin/sh\n", encoding="utf-8")
    repl.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path))

    resolved = resolve_repl_value("~/eshkol/bin/eshkol-repl", "test")

    assert resolved.exists
    assert resolved.executable
    assert resolved.resolved == str(repl.resolve())


def test_kernelspec_unresolved_repl_warns(monkeypatch) -> None:
    monkeypatch.setattr(
        "eshkol_kernel.doctor.KernelSpecManager",
        lambda: FakeKernelSpecManager({"ESHKOL_REPL": "definitely-not-eshkol-repl"}),
    )

    result = check_kernelspec("eshkol", required=False)

    assert result.status == "warn"
    assert "unresolved ESHKOL_REPL" in result.message


def test_kernelspec_repl_mismatch_fails_when_required(tmp_path: Path, monkeypatch) -> None:
    smoke_repl = tmp_path / "smoke" / "eshkol-repl"
    spec_repl = tmp_path / "spec" / "eshkol-repl"
    for repl in [smoke_repl, spec_repl]:
        repl.parent.mkdir(parents=True)
        repl.write_text("#!/bin/sh\n", encoding="utf-8")
        repl.chmod(0o755)
    monkeypatch.setattr(
        "eshkol_kernel.doctor.KernelSpecManager",
        lambda: FakeKernelSpecManager({"ESHKOL_REPL": str(spec_repl)}),
    )

    result = check_kernelspec(
        "eshkol",
        required=True,
        expected_repl=resolve_repl_value(str(smoke_repl), "--eshkol-repl"),
    )

    assert result.status == "fail"
    assert "different ESHKOL_REPL" in result.message


def test_missing_shared_libraries_parses_ldd_output() -> None:
    output = """
    linux-vdso.so.1 (0x00007fff)
    libblas.so.3 => not found
    libLLVM.so.21.1 => not found
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6
    """

    assert missing_shared_libraries(output) == ["libLLVM.so.21.1", "libblas.so.3"]


def test_linux_dependency_hint_mentions_known_packages() -> None:
    hint = linux_dependency_hint(["libLLVM.so.21.1", "libblas.so.3", "liblapack.so.3"])

    assert "libllvm21" in hint
    assert "libblas3" in hint
    assert "liblapack3" in hint
