from __future__ import annotations

import json
from pathlib import Path

import pytest

from eshkol_kernel import setup as setup_cli
from eshkol_kernel.doctor import CheckResult, ReplResolution, exit_code
from eshkol_kernel.setup import SetupError, SetupOptions, SetupResult, setup_kernel


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_setup_uses_explicit_repl_and_installs_kernelspec(tmp_path: Path) -> None:
    repl = make_executable(tmp_path / "eshkol" / "bin" / "eshkol-repl")

    result = setup_kernel(
        SetupOptions(
            prefix=str(tmp_path / "jupyter-prefix"),
            name="eshkol-test",
            display_name="Eshkol Test",
            eshkol_repl=str(repl),
            load_stdlib=False,
            skip_smoke=True,
        )
    )

    kernel_json = Path(result.kernelspec) / "kernel.json"
    data = json.loads(kernel_json.read_text(encoding="utf-8"))
    assert data["display_name"] == "Eshkol Test"
    assert data["env"]["ESHKOL_REPL"] == str(repl.resolve())
    assert data["env"]["ESHKOL_KERNEL_LOAD_STDLIB"] == "0"
    assert not result.downloaded
    assert exit_code(result.checks) == 0


def test_setup_fetches_runtime_when_repl_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fetched_repl = tmp_path / "downloaded" / "bin" / "eshkol-repl"
    seen: dict[str, object] = {}

    def fake_resolve_repl(configured: str | None) -> ReplResolution:
        return ReplResolution(
            requested=configured or "eshkol-repl",
            resolved=None,
            source="PATH",
            exists=False,
            executable=False,
        )

    def fake_install_release_runtime(*, tag: str, flavor: str, output: Path | str, timeout: float) -> Path:
        seen.update({"tag": tag, "flavor": flavor, "output": Path(output), "timeout": timeout})
        return make_executable(fetched_repl)

    monkeypatch.setattr(setup_cli, "resolve_repl", fake_resolve_repl)
    monkeypatch.setattr(setup_cli, "install_release_runtime", fake_install_release_runtime)

    result = setup_kernel(
        SetupOptions(
            prefix=str(tmp_path / "jupyter-prefix"),
            runtime_dir=tmp_path / "downloaded",
            tag="v1.2.3",
            flavor="lite",
            fetch_timeout=12.0,
            skip_smoke=True,
        )
    )

    assert seen == {"tag": "v1.2.3", "flavor": "lite", "output": tmp_path / "downloaded", "timeout": 12.0}
    assert result.repl == fetched_repl
    assert result.downloaded
    assert exit_code(result.checks) == 0


def test_setup_reuses_cached_runtime_before_fetching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cached_repl = make_executable(tmp_path / "cached" / "bin" / "eshkol-repl")

    def fake_resolve_repl(configured: str | None) -> ReplResolution:
        return ReplResolution(
            requested=configured or "eshkol-repl",
            resolved=None,
            source="PATH",
            exists=False,
            executable=False,
        )

    def fail_fetch(**kwargs: object) -> Path:
        raise AssertionError("setup should reuse cached runtime")

    monkeypatch.setattr(setup_cli, "resolve_repl", fake_resolve_repl)
    monkeypatch.setattr(setup_cli, "install_release_runtime", fail_fetch)

    result = setup_kernel(
        SetupOptions(
            prefix=str(tmp_path / "jupyter-prefix"),
            runtime_dir=tmp_path / "cached",
            skip_smoke=True,
        )
    )

    assert result.repl == cached_repl.resolve()
    assert not result.downloaded
    assert exit_code(result.checks) == 0


def test_setup_no_download_fails_when_runtime_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_repl(configured: str | None) -> ReplResolution:
        return ReplResolution(
            requested=configured or "eshkol-repl",
            resolved=None,
            source="PATH",
            exists=False,
            executable=False,
        )

    monkeypatch.setattr(setup_cli, "resolve_repl", fake_resolve_repl)

    with pytest.raises(SetupError, match="Could not find eshkol-repl"):
        setup_kernel(SetupOptions(download=False))


def test_setup_main_returns_doctor_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repl = make_executable(tmp_path / "eshkol-repl")

    def fake_setup_kernel(options: SetupOptions) -> SetupResult:
        return SetupResult(
            repl=repl,
            kernelspec=str(tmp_path / "kernelspec"),
            checks=[CheckResult("execution smoke test", "fail", "bad")],
            downloaded=False,
        )

    monkeypatch.setattr(setup_cli, "setup_kernel", fake_setup_kernel)

    assert setup_cli.main(["--eshkol-repl", str(repl)]) == 1


def test_default_runtime_dir_uses_xdg_cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_cli.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert setup_cli.default_runtime_dir() == tmp_path / "eshkol-kernel" / "eshkol"
