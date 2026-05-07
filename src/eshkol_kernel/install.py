from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from jupyter_client.kernelspec import KernelSpecManager


def install_kernel_spec(
    *,
    user: bool = True,
    prefix: str | None = None,
    name: str = "eshkol",
    display_name: str = "Eshkol",
    eshkol_repl: str | None = None,
    load_stdlib: bool | None = None,
) -> str:
    kernel_json = {
        "argv": [sys.executable, "-m", "eshkol_kernel", "-f", "{connection_file}"],
        "display_name": display_name,
        "language": "eshkol",
        "interrupt_mode": "signal",
        "metadata": {"debugger": False},
    }
    env = {}
    if eshkol_repl:
        env["ESHKOL_REPL"] = eshkol_repl
    if load_stdlib is not None:
        env["ESHKOL_KERNEL_LOAD_STDLIB"] = "1" if load_stdlib else "0"
    if env:
        kernel_json["env"] = env

    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir)
        (spec_dir / "kernel.json").write_text(json.dumps(kernel_json, indent=2), encoding="utf-8")
        destination = KernelSpecManager().install_kernel_spec(
            str(spec_dir),
            kernel_name=name,
            user=user if prefix is None else False,
            prefix=prefix,
        )
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the Eshkol Jupyter kernelspec.")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--user", action="store_true", default=True, help="Install for the current user.")
    location.add_argument("--sys-prefix", action="store_true", help="Install into sys.prefix.")
    location.add_argument("--prefix", help="Install into an explicit prefix.")
    parser.add_argument("--name", default="eshkol", help="Kernel spec name.")
    parser.add_argument("--display-name", default="Eshkol", help="Display name shown in Jupyter.")
    parser.add_argument("--eshkol-repl", help="Path to eshkol-repl to bake into kernel.json.")
    stdlib = parser.add_mutually_exclusive_group()
    stdlib.add_argument("--load-stdlib", action="store_true", help="Load Eshkol stdlib when the kernel starts.")
    stdlib.add_argument(
        "--no-load-stdlib",
        action="store_true",
        help="Do not load Eshkol stdlib when the kernel starts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prefix = args.prefix
    user = args.user
    if args.sys_prefix:
        prefix = sys.prefix
        user = False
    load_stdlib = None
    if args.load_stdlib:
        load_stdlib = True
    elif args.no_load_stdlib:
        load_stdlib = False
    destination = install_kernel_spec(
        user=user,
        prefix=prefix,
        name=args.name,
        display_name=args.display_name,
        eshkol_repl=args.eshkol_repl,
        load_stdlib=load_stdlib,
    )
    print(f"Installed Eshkol kernelspec to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
