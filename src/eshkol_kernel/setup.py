from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .doctor import CheckResult, DoctorOptions, exit_code, print_results, resolve_repl, run_doctor
from .fetch_runtime import DEFAULT_TIMEOUT, install_release_runtime
from .install import install_kernel_spec


@dataclass(frozen=True)
class SetupOptions:
    user: bool = True
    prefix: str | None = None
    name: str = "eshkol"
    display_name: str = "Eshkol"
    eshkol_repl: str | None = None
    download: bool = True
    runtime_dir: Path | None = None
    tag: str = "latest"
    flavor: str = "lite"
    fetch_timeout: float = DEFAULT_TIMEOUT
    load_stdlib: bool = True
    doctor_timeout: float = 10.0
    start_timeout: float = 10.0
    skip_smoke: bool = False


@dataclass(frozen=True)
class SetupResult:
    repl: Path
    kernelspec: str
    checks: list[CheckResult]
    downloaded: bool


class SetupError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up the Eshkol Jupyter kernel.")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--user", action="store_true", default=True, help="Install for the current user.")
    location.add_argument("--sys-prefix", action="store_true", help="Install into sys.prefix.")
    location.add_argument("--prefix", help="Install into an explicit prefix.")
    parser.add_argument("--name", default="eshkol", help="Kernel spec name.")
    parser.add_argument("--display-name", default="Eshkol", help="Display name shown in Jupyter.")
    parser.add_argument("--eshkol-repl", help="Use this eshkol-repl path or command instead of searching/downloading.")
    download = parser.add_mutually_exclusive_group()
    download.add_argument("--download", action="store_true", default=True, help="Download Eshkol if no REPL is found.")
    download.add_argument(
        "--no-download",
        action="store_true",
        help="Fail instead of downloading when no REPL is found.",
    )
    parser.add_argument("--runtime-dir", type=Path, default=None, help="Directory for downloaded Eshkol runtime.")
    parser.add_argument("--tag", default="latest", help="Eshkol release tag to download, or 'latest'.")
    parser.add_argument("--flavor", default="lite", choices=["lite", "xla", "cuda"], help="Eshkol release flavor.")
    parser.add_argument("--fetch-timeout", type=float, default=DEFAULT_TIMEOUT, help="Network timeout in seconds.")
    stdlib = parser.add_mutually_exclusive_group()
    stdlib.add_argument("--load-stdlib", action="store_true", default=True, help="Load Eshkol stdlib on startup.")
    stdlib.add_argument("--no-load-stdlib", action="store_true", help="Do not load Eshkol stdlib on startup.")
    parser.add_argument("--doctor-timeout", type=float, default=10.0, help="Doctor execution timeout in seconds.")
    parser.add_argument("--start-timeout", type=float, default=10.0, help="REPL startup timeout in seconds.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip the doctor execution smoke test.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prefix = args.prefix
    user = args.user
    if args.sys_prefix:
        prefix = sys.prefix
        user = False

    options = SetupOptions(
        user=user,
        prefix=prefix,
        name=args.name,
        display_name=args.display_name,
        eshkol_repl=args.eshkol_repl,
        download=not args.no_download,
        runtime_dir=args.runtime_dir,
        tag=args.tag,
        flavor=args.flavor,
        fetch_timeout=args.fetch_timeout,
        load_stdlib=not args.no_load_stdlib,
        doctor_timeout=args.doctor_timeout,
        start_timeout=args.start_timeout,
        skip_smoke=args.skip_smoke,
    )

    try:
        result = setup_kernel(options)
    except SetupError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    print(f"Using Eshkol runtime: {result.repl}")
    if result.downloaded:
        print(f"Downloaded Eshkol runtime to: {result.repl.parents[1]}")
    print(f"Installed Eshkol kernelspec to: {result.kernelspec}")
    print_results(result.checks)
    if exit_code(result.checks) == 0:
        print_next_steps()
    return exit_code(result.checks)


def setup_kernel(options: SetupOptions) -> SetupResult:
    repl, downloaded = resolve_or_fetch_runtime(options)
    kernelspec = install_kernel_spec(
        user=options.user,
        prefix=options.prefix,
        name=options.name,
        display_name=options.display_name,
        eshkol_repl=str(repl),
        load_stdlib=options.load_stdlib,
    )
    checks = run_doctor(
        DoctorOptions(
            eshkol_repl=str(repl),
            kernel_name=options.name,
            load_stdlib=options.load_stdlib,
            timeout=options.doctor_timeout,
            start_timeout=options.start_timeout,
            require_kernelspec=True,
            skip_smoke=options.skip_smoke,
            kernelspec_dir=str(Path(kernelspec).parent),
        )
    )
    return SetupResult(repl=repl, kernelspec=kernelspec, checks=checks, downloaded=downloaded)


def resolve_or_fetch_runtime(options: SetupOptions) -> tuple[Path, bool]:
    repl = resolve_repl(options.eshkol_repl)
    if repl.resolved and repl.exists and repl.executable:
        return Path(repl.resolved), False

    if options.eshkol_repl:
        raise SetupError(f"Could not use requested eshkol-repl: {options.eshkol_repl}")
    if not options.download:
        raise SetupError("Could not find eshkol-repl. Re-run without --no-download or pass --eshkol-repl.")

    output = options.runtime_dir or default_runtime_dir()
    cached = output.expanduser().resolve() / "bin" / "eshkol-repl"
    if cached.exists() and os.access(cached, os.X_OK):
        return cached, False

    fetched = install_release_runtime(
        tag=options.tag,
        flavor=options.flavor,
        output=output,
        timeout=options.fetch_timeout,
    )
    if not fetched.exists():
        raise SetupError(f"Downloaded runtime did not contain eshkol-repl at {fetched}")
    return fetched, True


def default_runtime_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "eshkol-kernel" / "eshkol"
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "eshkol-kernel" / "eshkol"


def print_next_steps() -> None:
    print("Setup complete.")
    print("Next:")
    if importlib.util.find_spec("jupyterlab") is None:
        print("  python -m pip install jupyterlab")
    print("  python -m jupyter lab")


if __name__ == "__main__":
    raise SystemExit(main())
