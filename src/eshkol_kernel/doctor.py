from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from shutil import which
from typing import Any

from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel

from . import __version__
from .session import EshkolReplSession, EshkolSessionError

PASS = "pass"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str
    detail: str = ""


@dataclass(frozen=True)
class DoctorOptions:
    eshkol_repl: str | None = None
    repl_args: tuple[str, ...] = ()
    kernel_name: str = "eshkol"
    load_stdlib: bool = False
    timeout: float = 10.0
    start_timeout: float = 10.0
    skip_kernelspec: bool = False
    require_kernelspec: bool = False
    skip_smoke: bool = False


@dataclass(frozen=True)
class ReplResolution:
    requested: str
    resolved: str | None
    source: str
    exists: bool
    executable: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose an Eshkol Jupyter kernel installation.")
    parser.add_argument("--eshkol-repl", help="Path or command name for eshkol-repl.")
    parser.add_argument(
        "--repl-arg",
        action="append",
        default=[],
        help="Extra argument passed to the REPL. May be repeated.",
    )
    parser.add_argument("--kernel-name", default="eshkol", help="Jupyter kernelspec name to inspect.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-cell smoke-test timeout in seconds.")
    parser.add_argument("--start-timeout", type=float, default=10.0, help="REPL startup timeout in seconds.")
    parser.add_argument("--load-stdlib", action="store_true", help="Load Eshkol stdlib during the smoke test.")
    parser.add_argument("--skip-kernelspec", action="store_true", help="Skip kernelspec inspection.")
    parser.add_argument("--require-kernelspec", action="store_true", help="Fail if the kernelspec is not installed.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip executing a real REPL expression.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = DoctorOptions(
        eshkol_repl=args.eshkol_repl,
        repl_args=tuple(args.repl_arg) if args.repl_arg else tuple(env_repl_args()),
        kernel_name=args.kernel_name,
        load_stdlib=args.load_stdlib,
        timeout=args.timeout,
        start_timeout=args.start_timeout,
        skip_kernelspec=args.skip_kernelspec,
        require_kernelspec=args.require_kernelspec,
        skip_smoke=args.skip_smoke,
    )
    results = run_doctor(options)
    if args.json:
        print(json.dumps({"ok": exit_code(results) == 0, "checks": [asdict(result) for result in results]}, indent=2))
    else:
        print_results(results)
    return exit_code(results)


def run_doctor(options: DoctorOptions) -> list[CheckResult]:
    results = [
        CheckResult("eshkol-kernel package", PASS, f"eshkol-kernel {__version__} is importable."),
        check_platform(),
    ]
    repl = resolve_repl(options.eshkol_repl)
    results.append(check_repl(repl))
    if repl.resolved:
        results.append(check_shared_libraries(Path(repl.resolved)))
    else:
        results.append(
            CheckResult(
                "shared libraries",
                SKIP,
                "Skipped because no eshkol-repl executable was resolved.",
            )
        )

    if options.skip_kernelspec:
        results.append(CheckResult("Jupyter kernelspec", SKIP, "Skipped by --skip-kernelspec."))
    else:
        results.append(check_kernelspec(options.kernel_name, required=options.require_kernelspec, expected_repl=repl))

    if options.skip_smoke:
        results.append(CheckResult("execution smoke test", SKIP, "Skipped by --skip-smoke."))
    elif repl.resolved and repl.executable and not is_failing(results):
        results.append(check_smoke(Path(repl.resolved), options))
    elif repl.resolved and repl.executable:
        results.append(
            CheckResult(
                "execution smoke test",
                SKIP,
                "Skipped because an earlier required check failed.",
            )
        )
    else:
        results.append(
            CheckResult(
                "execution smoke test",
                SKIP,
                "Skipped because no runnable eshkol-repl executable was resolved.",
            )
        )
    return results


def check_platform() -> CheckResult:
    if sys.platform.startswith("win"):
        return CheckResult(
            "platform",
            FAIL,
            "This kernel currently requires a Unix-like pseudo-terminal.",
            "Use macOS or Linux for the PTY-backed wrapper.",
        )
    if importlib.util.find_spec("pexpect") is None:
        return CheckResult(
            "platform",
            FAIL,
            "pexpect is not installed.",
            "Install the package with `python -m pip install eshkol-kernel` or `python -m pip install -e .`.",
        )
    return CheckResult("platform", PASS, f"{sys.platform} with pexpect available.")


def resolve_repl(configured: str | None) -> ReplResolution:
    requested = configured or os.environ.get("ESHKOL_REPL") or "eshkol-repl"
    source = "--eshkol-repl" if configured else "ESHKOL_REPL" if os.environ.get("ESHKOL_REPL") else "PATH"
    return resolve_repl_value(requested, source)


def check_repl(repl: ReplResolution) -> CheckResult:
    if not repl.resolved or not repl.exists:
        external = Path.cwd() / ".external" / "eshkol" / "bin" / "eshkol-repl"
        detail = "Run `eshkol-kernel-fetch-runtime --output .external/eshkol` or set ESHKOL_REPL."
        if external.exists():
            detail = (
                f"Found local runtime candidate: {external}. "
                f'Install with `eshkol-kernel-install --user --eshkol-repl "{external}"`.'
            )
        return CheckResult(
            "eshkol-repl executable",
            FAIL,
            f"Could not find {repl.requested!r} from {repl.source}.",
            detail,
        )
    if not repl.executable:
        return CheckResult("eshkol-repl executable", FAIL, f"{repl.resolved} exists but is not executable.")
    return CheckResult("eshkol-repl executable", PASS, f"{repl.resolved} resolved from {repl.source}.")


def check_shared_libraries(executable: Path) -> CheckResult:
    command = library_probe_command(executable)
    if command is None:
        return CheckResult("shared libraries", SKIP, f"No shared-library probe is configured for {sys.platform}.")
    if which(command[0]) is None:
        return CheckResult("shared libraries", SKIP, f"{command[0]} is not available.")

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    missing = missing_shared_libraries(output)
    if missing:
        return CheckResult(
            "shared libraries",
            FAIL,
            "Missing shared libraries: " + ", ".join(missing),
            linux_dependency_hint(missing),
        )
    if completed.returncode != 0:
        return CheckResult(
            "shared libraries",
            WARN,
            f"{command[0]} exited with status {completed.returncode}.",
            output,
        )
    return CheckResult("shared libraries", PASS, "No missing shared libraries reported.")


def library_probe_command(executable: Path) -> list[str] | None:
    if sys.platform.startswith("linux"):
        return ["ldd", str(executable)]
    if sys.platform == "darwin":
        return ["otool", "-L", str(executable)]
    return None


def missing_shared_libraries(output: str) -> list[str]:
    missing: list[str] = []
    for line in output.splitlines():
        if "not found" not in line:
            continue
        name = line.strip().split("=>", 1)[0].strip()
        if name:
            missing.append(name)
    return sorted(set(missing))


def linux_dependency_hint(missing: Sequence[str]) -> str:
    packages: list[str] = []
    if any(name.startswith("libblas") for name in missing):
        packages.append("libblas3")
    if any(name.startswith("liblapack") for name in missing):
        packages.append("liblapack3")
    if any(name.startswith("libLLVM") for name in missing):
        packages.append("libllvm21 from apt.llvm.org")
    if not packages:
        return "Install the missing runtime libraries for your distribution."
    return "On Ubuntu, install: " + ", ".join(packages) + "."


def check_kernelspec(
    kernel_name: str,
    *,
    required: bool,
    expected_repl: ReplResolution | None = None,
) -> CheckResult:
    manager = KernelSpecManager()
    try:
        spec = manager.get_kernel_spec(kernel_name)
    except NoSuchKernel:
        status = FAIL if required else WARN
        detail = f"Install it with `eshkol-kernel-install --user --name {kernel_name}`."
        return CheckResult("Jupyter kernelspec", status, f"Kernelspec {kernel_name!r} is not installed.", detail)

    env = spec.env or {}
    repl = env.get("ESHKOL_REPL")
    if repl:
        spec_repl = resolve_repl_value(repl, "kernelspec")
        if not spec_repl.exists:
            status = FAIL if required else WARN
            detail = "Reinstall it with `eshkol-kernel-install --user --eshkol-repl /path/to/eshkol-repl`."
            return CheckResult(
                "Jupyter kernelspec",
                status,
                f"Kernelspec {kernel_name!r} points at an unresolved ESHKOL_REPL: {repl}",
                detail,
            )
        if not spec_repl.executable:
            return CheckResult(
                "Jupyter kernelspec",
                FAIL,
                f"Kernelspec {kernel_name!r} points at a non-executable ESHKOL_REPL: {spec_repl.resolved}",
            )
        if expected_repl and expected_repl.resolved and spec_repl.resolved:
            expected_path = Path(expected_repl.resolved).resolve()
            spec_path = Path(spec_repl.resolved).resolve()
            if expected_path != spec_path:
                status = FAIL if required else WARN
                return CheckResult(
                    "Jupyter kernelspec",
                    status,
                    f"Kernelspec {kernel_name!r} uses a different ESHKOL_REPL than the smoke test.",
                    f"Smoke test used {expected_path}; kernelspec uses {spec_path}.",
                )
        return CheckResult("Jupyter kernelspec", PASS, f"Kernelspec {kernel_name!r} sets ESHKOL_REPL={repl}.")

    if expected_repl and expected_repl.source == "--eshkol-repl":
        status = FAIL if required else WARN
        return CheckResult(
            "Jupyter kernelspec",
            status,
            f"Kernelspec {kernel_name!r} does not set ESHKOL_REPL.",
            "The smoke test used --eshkol-repl, but Jupyter will resolve eshkol-repl from its launch environment.",
        )
    return CheckResult(
        "Jupyter kernelspec",
        PASS,
        f"Kernelspec {kernel_name!r} is installed and will resolve eshkol-repl from the launch environment.",
    )


def is_path_like(value: str) -> bool:
    return value.startswith("~") or os.path.sep in value or (os.path.altsep is not None and os.path.altsep in value)


def resolve_repl_value(requested: str, source: str) -> ReplResolution:
    if is_path_like(requested):
        path = Path(requested).expanduser()
        resolved = str(path.resolve()) if path.exists() else str(path)
    else:
        resolved = which(requested)

    exists = bool(resolved and Path(resolved).exists())
    executable = bool(exists and os.access(str(resolved), os.X_OK))
    return ReplResolution(
        requested=requested,
        resolved=resolved,
        source=source,
        exists=exists,
        executable=executable,
    )


def check_smoke(executable: Path, options: DoctorOptions) -> CheckResult:
    session = EshkolReplSession(
        executable=str(executable),
        argv=list(options.repl_args),
        load_stdlib=options.load_stdlib,
        timeout=options.timeout,
        start_timeout=options.start_timeout,
    )
    try:
        result = session.execute("(+ 1 2 3)")
    except EshkolSessionError as exc:
        return CheckResult(
            "execution smoke test",
            FAIL,
            "Could not execute `(+ 1 2 3)`.",
            humanize_session_error(str(exc)),
        )
    finally:
        session.close()

    if not result.ok:
        return CheckResult("execution smoke test", FAIL, "Eshkol returned an error.", result.stderr.strip())
    if result.stdout.strip() != "6":
        return CheckResult(
            "execution smoke test",
            FAIL,
            "Unexpected smoke-test output.",
            f"Expected 6, got {result.stdout.strip()!r}.",
        )
    return CheckResult("execution smoke test", PASS, "Eshkol executed `(+ 1 2 3)` and returned 6.")


def humanize_session_error(text: str) -> str:
    missing = missing_shared_libraries(text)
    if missing:
        return "Missing shared libraries: " + ", ".join(missing) + ". " + linux_dependency_hint(missing)
    return text


def env_repl_args() -> list[str]:
    return shlex.split(os.environ.get("ESHKOL_KERNEL_REPL_ARGS", ""))


def is_failing(results: Sequence[CheckResult]) -> bool:
    return any(result.status == FAIL for result in results)


def exit_code(results: Sequence[CheckResult]) -> int:
    return 1 if is_failing(results) else 0


def print_results(results: Sequence[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        print(f"{result.status.upper():<4} {result.name:<{width}} {result.message}")
        if result.detail:
            print(f"     {result.detail}")


def results_as_dicts(results: Sequence[CheckResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]


if __name__ == "__main__":
    raise SystemExit(main())
