#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


REPO = "tsotchke/eshkol"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download an Eshkol release binary for local kernel testing.")
    parser.add_argument("--tag", default="latest", help="Release tag to download, or 'latest'.")
    parser.add_argument("--flavor", default="lite", choices=["lite", "xla", "cuda"], help="Release flavor.")
    parser.add_argument("--output", default=".external/eshkol", help="Extraction directory.")
    args = parser.parse_args()

    release = fetch_release(args.tag)
    asset = choose_asset(release, args.flavor)
    output = Path(args.output).resolve()
    downloads = output.parent / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    archive = downloads / asset["name"]
    sums = downloads / "SHA256SUMS.txt"
    download(asset["browser_download_url"], archive)
    sums_asset = next((item for item in release["assets"] if item["name"] == "SHA256SUMS.txt"), None)
    if sums_asset:
        download(sums_asset["browser_download_url"], sums)
        verify_from_sums(archive, sums)
    elif asset.get("digest", "").startswith("sha256:"):
        verify_digest(archive, asset["digest"].split(":", 1)[1])
    else:
        raise SystemExit("Release did not provide SHA256SUMS.txt or an asset digest.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp, filter="data")
        roots = [path for path in tmp.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise SystemExit(f"Expected one extracted directory, found {len(roots)}.")
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(roots[0]), output)

    repl = output / "bin" / "eshkol-repl"
    print(f"Installed {asset['name']} to {output}")
    print(f"eshkol-repl: {repl}")
    return 0


def fetch_release(tag: str) -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    if tag != "latest":
        url = f"https://api.github.com/repos/{REPO}/releases/tags/{tag}"
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def choose_asset(release: dict, flavor: str) -> dict:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        os_part = "macos"
    elif system == "linux":
        os_part = "linux"
    else:
        raise SystemExit(f"Unsupported platform: {platform.system()}")

    if machine in {"arm64", "aarch64"}:
        arch_part = "arm64"
    elif machine in {"x86_64", "amd64"}:
        arch_part = "x64"
    else:
        raise SystemExit(f"Unsupported architecture: {platform.machine()}")

    suffix = ".tar.gz"
    needle = f"-{os_part}-{arch_part}-{flavor}{suffix}"
    matches = [asset for asset in release["assets"] if asset["name"].endswith(needle)]
    if not matches:
        names = "\n".join(asset["name"] for asset in release["assets"])
        raise SystemExit(f"No release asset matched {needle}. Available assets:\n{names}")
    return matches[0]


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def verify_from_sums(archive: Path, sums: Path) -> None:
    expected = None
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == archive.name:
            expected = parts[0]
            break
    if not expected:
        raise SystemExit(f"No checksum found for {archive.name}.")
    verify_digest(archive, expected)


def verify_digest(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Checksum mismatch for {path.name}: expected {expected}, got {actual}")


if __name__ == "__main__":
    raise SystemExit(main())
