# Eshkol Jupyter Kernel

A Jupyter kernel for Eshkol. It lets JupyterLab, classic Notebook, VS Code
notebooks, and other Jupyter clients execute Eshkol code cells through a
long-lived `eshkol-repl` process.

![Eshkol running in JupyterLab](docs/images/jupyterlab-eshkol.svg)

## Status

Alpha, but usable:

- Published on PyPI as `eshkol-kernel` version `0.1.0a2`
- Stateful code execution through `eshkol-repl`
- Multiline cell handling
- Multiple top-level forms in one cell
- Text streams, classified errors, and Jupyter `display_data` MIME bundles
- Completion for common Scheme/Eshkol forms plus symbols defined in successful cells
- One-command setup via `eshkol-kernel-setup`
- Kernel installation via `eshkol-kernel-install`
- Runtime download helper via `eshkol-kernel-fetch-runtime`
- Setup diagnostics via `eshkol-kernel-doctor`
- Unit, Jupyter protocol, notebook execution, packaging, and real-runtime smoke tests

This package does not vendor Eshkol itself. You can point it at an existing
`eshkol-repl`, or let `eshkol-kernel-setup` download the latest compatible
release into a user cache directory.

## Quick Start

Create a Python environment, install the kernel package and JupyterLab, then run
the setup command:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install eshkol-kernel==0.1.0a2 jupyterlab
eshkol-kernel-setup --user
python -m jupyter lab
```

Create or open a notebook and select the `Eshkol` kernel. Try:

```scheme
(+ 1 2 3)
```

The setup command uses an existing `eshkol-repl` on `PATH` when available. If it
cannot find one, it downloads the latest compatible Eshkol release into a user
cache directory, installs the Jupyter kernelspec, runs diagnostics, and prints
the next command to launch Jupyter.

To force a specific runtime:

```bash
eshkol-kernel-setup --user --eshkol-repl /absolute/path/to/eshkol-repl
```

## Runtime Options

Most users should configure the kernel with `eshkol-kernel-setup`. Useful setup
options:

```bash
eshkol-kernel-setup --user
eshkol-kernel-setup --user --eshkol-repl /absolute/path/to/eshkol-repl
eshkol-kernel-setup --user --runtime-dir ~/.cache/eshkol-kernel/eshkol
eshkol-kernel-setup --user --tag latest --flavor lite
eshkol-kernel-setup --sys-prefix
eshkol-kernel-setup --no-download
```

The kernel reads these environment variables when Jupyter starts it:

- `ESHKOL_REPL`: path to `eshkol-repl` (default: `eshkol-repl`)
- `ESHKOL_KERNEL_LOAD_STDLIB`: load stdlib on startup (`1` by default)
- `ESHKOL_KERNEL_REPL_ARGS`: extra arguments passed to `eshkol-repl`
- `ESHKOL_KERNEL_TIMEOUT`: per-cell execution timeout in seconds (default: `30`)
- `ESHKOL_KERNEL_START_TIMEOUT`: REPL startup timeout in seconds (default: `10`)

Lower-level commands remain available when you want manual control. If Jupyter
launches from an environment that does not inherit your shell variables, bake
the runtime path into the kernelspec:

```bash
eshkol-kernel-install --user --eshkol-repl /absolute/path/to/eshkol-repl
```

The fetch helper supports release tags and flavors:

```bash
eshkol-kernel-fetch-runtime --tag latest --flavor lite --output .external/eshkol
```

Use `.external/` as local development setup, not as source code. The setup
command downloads into a user cache by default; production or packaged setups
can point the kernelspec at any Eshkol installation.

Linux release binaries may require system BLAS/LAPACK and LLVM runtime
libraries. The CI workflow documents the Ubuntu packages currently needed for
the downloaded Eshkol release.

## Diagnose Setup

`eshkol-kernel-setup` runs the doctor checks automatically. Run the doctor
command directly when Jupyter cannot start the kernel or Eshkol cells fail
before evaluating code:

```bash
eshkol-kernel-doctor
```

It checks the package import, platform support, `eshkol-repl` resolution, shared
library dependencies, the `Eshkol` kernelspec, and a real `(+ 1 2 3)` execution.
Point it at a specific runtime when your kernelspec uses an absolute path:

```bash
eshkol-kernel-doctor --eshkol-repl /absolute/path/to/eshkol-repl
```

The command exits nonzero only for failures. Missing kernelspecs are warnings by
default so contributors can diagnose the runtime before installing Jupyter
metadata. Use `--require-kernelspec` when validating a fully installed setup.

## Manage The Kernelspec

List installed kernels:

```bash
jupyter kernelspec list
```

Update or reinstall the default `Eshkol` kernelspec through the setup command:

```bash
eshkol-kernel-setup --user --eshkol-repl /absolute/path/to/eshkol-repl
```

Install just the kernelspec without fetching or running diagnostics:

```bash
eshkol-kernel-install --user --eshkol-repl /absolute/path/to/eshkol-repl
```

Install a second kernelspec name for another runtime:

```bash
eshkol-kernel-install --user \
  --name eshkol-dev \
  --display-name "Eshkol Dev" \
  --eshkol-repl /absolute/path/to/dev/eshkol-repl
```

Uninstall the default kernelspec:

```bash
jupyter kernelspec uninstall eshkol
```

## Rich Display Output

The kernel treats any single output line matching this JSON shape as a Jupyter
MIME bundle and publishes it as `display_data` instead of plain stdout:

```json
{
  "type": "display_data",
  "data": {
    "text/plain": "hello",
    "text/html": "<strong>hello</strong>"
  },
  "metadata": {}
}
```

This is a small bridge until Eshkol has a native notebook display API. Normal
text output still goes to stdout.

## How It Works

The kernel subclasses `ipykernel.kernelbase.Kernel`, the standard wrapper-kernel
path described by the Jupyter Client documentation. It starts `eshkol-repl` in a
pseudo-terminal rather than a plain pipe because the native REPL is interactive,
stateful, and prints prompts only when attached to a terminal.

Each notebook cell is split into top-level Eshkol forms and sent to the REPL.
After each form, the kernel sends a private sentinel expression and reads until
that sentinel appears, which gives the wrapper a reliable end-of-execution
marker while keeping the same REPL state alive between cells.

## Development

```bash
git clone https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel.git
cd eshkol-jupyter-kernel
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test,dev]'
ruff check .
python -m build
pytest
```

The default tests use a fake REPL so they can run even when Eshkol itself is not
installed. To run the real-runtime smoke tests locally:

```bash
eshkol-kernel-fetch-runtime --output .external/eshkol
ESHKOL_REAL_REPL="$PWD/.external/eshkol/bin/eshkol-repl" pytest tests/test_real_eshkol.py
eshkol-kernel-doctor --eshkol-repl "$PWD/.external/eshkol/bin/eshkol-repl" --skip-kernelspec
```

CI runs linting, package builds, fake-REPL tests, notebook execution tests, and
a separate real Eshkol smoke test that downloads the release binary.

## Release

Release publishing uses PyPI Trusted Publishing through GitHub Actions:

- `Publish to TestPyPI` is a manual workflow for dry runs.
- `Publish to PyPI` runs only for tags like `v0.1.0a2` or `v0.1.0`.
- Both workflows build the package and run `twine check dist/*` before upload.

Version `0.1.0a2` is published on
[PyPI](https://pypi.org/project/eshkol-kernel/). See
[docs/RELEASING.md](docs/RELEASING.md) for the release checklist.

## Known Limits

- This package targets Unix-like systems where `pexpect` can allocate a
  pseudo-terminal. macOS and Linux are the intended platforms.
- Rich display output currently depends on the JSON line convention above.
- Interrupt behavior depends on the native REPL's signal handling and the
  frontend. Restarting the kernel is the reliable reset path.
