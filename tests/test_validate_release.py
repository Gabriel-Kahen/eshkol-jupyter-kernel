from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

VALIDATE_RELEASE = Path(__file__).parents[1] / "scripts" / "validate_release.py"
SPEC = importlib.util.spec_from_file_location("validate_release", VALIDATE_RELEASE)
assert SPEC and SPEC.loader
validate_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_release)


def test_normalize_tag_accepts_v_prefixed_versions() -> None:
    assert validate_release.normalize_tag("v0.1.0") == "0.1.0"
    assert validate_release.normalize_tag("refs/tags/v0.1.0a1") == "0.1.0a1"


def test_normalize_tag_rejects_non_version_tags() -> None:
    with pytest.raises(SystemExit, match="must look like"):
        validate_release.normalize_tag("release-latest")


def test_is_prerelease() -> None:
    assert validate_release.is_prerelease("0.1.0a1")
    assert validate_release.is_prerelease("0.1.0rc2")
    assert not validate_release.is_prerelease("0.1.0")
