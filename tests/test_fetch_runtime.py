from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from eshkol_kernel import fetch_runtime


def test_choose_asset_for_current_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch_runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(fetch_runtime.platform, "machine", lambda: "x86_64")
    release = {
        "assets": [
            {"name": "eshkol-macos-arm64-lite.tar.gz"},
            {"name": "eshkol-linux-x64-lite.tar.gz"},
        ]
    }

    asset = fetch_runtime.choose_asset(release, "lite")

    assert asset["name"] == "eshkol-linux-x64-lite.tar.gz"


def test_verify_digest_rejects_mismatches(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar.gz"
    archive.write_text("not the expected archive", encoding="utf-8")

    with pytest.raises(SystemExit, match="Checksum mismatch"):
        fetch_runtime.verify_digest(archive, "0" * 64)


def test_extract_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        data = b"bad"
        member = tarfile.TarInfo("../outside.txt")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))

    with pytest.raises(SystemExit, match="outside output directory"):
        fetch_runtime.extract_archive(archive, tmp_path / "out")
