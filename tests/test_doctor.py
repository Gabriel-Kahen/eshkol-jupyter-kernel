from __future__ import annotations

import sys
from pathlib import Path

from eshkol_kernel.doctor import (
    DoctorOptions,
    check_repl,
    exit_code,
    linux_dependency_hint,
    missing_shared_libraries,
    resolve_repl,
    run_doctor,
)

FAKE_REPL = Path(__file__).with_name("fake_eshkol_repl.py")


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
