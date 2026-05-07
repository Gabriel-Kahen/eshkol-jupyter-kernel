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


def test_extract_archive_rejects_symlinks(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("root/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../outside"
        tar.addfile(member)

    with pytest.raises(SystemExit, match="archive link"):
        fetch_runtime.extract_archive(archive, tmp_path / "out")


def test_extract_archive_rejects_hardlinks(tmp_path: Path) -> None:
    archive = tmp_path / "archive.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("root/link")
        member.type = tarfile.LNKTYPE
        member.linkname = "root/target"
        tar.addfile(member)

    with pytest.raises(SystemExit, match="archive link"):
        fetch_runtime.extract_archive(archive, tmp_path / "out")


def test_download_uses_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(url: str, *, timeout: float):
        seen["url"] = url
        seen["timeout"] = timeout
        return Response(b"payload")

    monkeypatch.setattr(fetch_runtime.urllib.request, "urlopen", fake_urlopen)

    destination = tmp_path / "download.bin"
    fetch_runtime.download("https://example.test/file", destination, timeout=12.5)

    assert seen == {"url": "https://example.test/file", "timeout": 12.5}
    assert destination.read_bytes() == b"payload"
