# Releasing

This project publishes with PyPI Trusted Publishing. Do not add long-lived PyPI
API tokens to GitHub secrets.

## One-Time PyPI Setup

Create Trusted Publisher entries before the first upload.

For TestPyPI:

- owner: `Gabriel-Kahen`
- repository name: `eshkol-jupyter-kernel`
- workflow name: `testpypi.yml`
- environment name: `testpypi`

For PyPI:

- owner: `Gabriel-Kahen`
- repository name: `eshkol-jupyter-kernel`
- workflow name: `release.yml`
- environment name: `pypi`

In GitHub repository settings, create matching environments named `testpypi` and
`pypi`. Require manual approval for the `pypi` environment.

For this repository, the GitHub environments are already configured. The
remaining one-time setup is creating the Trusted Publisher entries in TestPyPI
and PyPI.

## Pre-Release Checklist

1. Confirm the package name is available or owned by this project:

   ```bash
   python - <<'PY'
   import urllib.error, urllib.request
   try:
       urllib.request.urlopen("https://pypi.org/pypi/eshkol-kernel/json", timeout=10)
       print("eshkol-kernel exists on PyPI")
   except urllib.error.HTTPError as exc:
       print(exc.code)
   PY
   ```

2. Decide the version in `pyproject.toml`. The initial publishing target is
   `0.1.0a1`, leaving `0.1.0` available for a later stable first release.

3. Update `CHANGELOG.md` and change `Unreleased` to the release date.

4. Run local validation:

   ```bash
   rm -rf dist
   python -m pip install -e '.[test,dev]'
   ruff check .
   python -m build
   twine check dist/*
   pytest
   eshkol-kernel-doctor --eshkol-repl "$PWD/.external/eshkol/bin/eshkol-repl" --skip-kernelspec
   ```

5. Push to `main` and wait for CI to pass.

## TestPyPI

Run the `Publish to TestPyPI` workflow manually from GitHub Actions. It builds
the package, runs `twine check`, and uploads to TestPyPI using the `testpypi`
Trusted Publisher. The workflow currently requires a pre-release version such
as `0.1.0a1`.

After it publishes, test installation in a fresh environment:

```bash
python3 -m venv /tmp/eshkol-kernel-testpypi
. /tmp/eshkol-kernel-testpypi/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  eshkol-kernel
eshkol-kernel-doctor --skip-smoke --skip-kernelspec
```

## PyPI

For a real release, commit the final version and changelog, then tag exactly the
same version with a leading `v`:

```bash
git tag v0.1.0a1
git push origin v0.1.0a1
```

The `Publish to PyPI` workflow validates that the tag version matches
`pyproject.toml`, builds the package, runs `twine check`, and publishes through
the protected `pypi` environment.

PyPI files and versions cannot be overwritten after upload. If a release is bad,
publish a new version.
