#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION_RE = re.compile(
    r"^v?(?P<version>[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?)$",
    re.IGNORECASE,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate release metadata before publishing.")
    parser.add_argument("--tag", help="Git tag or ref name, such as v0.1.0.")
    parser.add_argument("--allow-prerelease", action="store_true", help="Require and allow a pre-release version.")
    args = parser.parse_args(argv)

    version = project_version()
    if args.allow_prerelease and not is_prerelease(version):
        raise SystemExit(f"Expected a pre-release project version for TestPyPI, got {version!r}.")

    if args.tag:
        tag_version = normalize_tag(args.tag)
        if tag_version != version:
            raise SystemExit(f"Release tag {args.tag!r} does not match pyproject version {version!r}.")

    print(f"release metadata ok: {version}")
    return 0


def project_version() -> str:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', Path("pyproject.toml").read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("Could not find project.version in pyproject.toml.")
    return match.group(1)


def normalize_tag(tag: str) -> str:
    match = VERSION_RE.fullmatch(tag.removeprefix("refs/tags/"))
    if not match:
        raise SystemExit(f"Release tag must look like v0.1.0, got {tag!r}.")
    return match.group("version")


def is_prerelease(version: str) -> bool:
    return bool(re.search(r"(?:a|b|rc)[0-9]+", version, flags=re.IGNORECASE))


if __name__ == "__main__":
    raise SystemExit(main())
