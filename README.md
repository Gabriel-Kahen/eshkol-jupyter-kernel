# Eshkol Jupyter Kernel

A Jupyter kernel for Eshkol. It lets JupyterLab, classic Notebook, VS Code
notebooks, and other Jupyter clients execute Eshkol code cells through a
long-lived `eshkol-repl` process.

![Eshkol running in JupyterLab](docs/images/jupyterlab-eshkol.svg)

## Status

Alpha, but usable:

- Stateful code execution through `eshkol-repl`
- Multiline cell handling
- Multiple top-level forms in one cell
- Text streams, classified errors, and Jupyter `display_data` MIME bundles
- Completion for common Scheme/Eshkol forms plus symbols defined in successful cells
- Kernel installation via `eshkol-kernel-install`
- Runtime download helper via `eshkol-kernel-fetch-runtime`
- Unit, Jupyter protocol, notebook execution, packaging, and real-runtime smoke tests

This package does not vendor Eshkol itself. You can point it at an existing
`eshkol-repl`, or use the fetch command below to download a local development
runtime into `.external/`. The `.external/` directory is intentionally ignored
by git.

## Quick Start

Clone this repo and create a Python environment:

```bash
git clone https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel.git
cd eshkol-jupyter-kernel
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If `eshkol-repl` is already on `PATH`, install the kernelspec:

```bash
eshkol-kernel-install --user
```

If you want the repo to fetch the latest compatible Eshkol release binary:

```bash
eshkol-kernel-fetch-runtime --output .external/eshkol
eshkol-kernel-install --user --eshkol-repl "$PWD/.external/eshkol/bin/eshkol-repl"
```

Open the included example notebook:

```bash
python -m pip install jupyterlab
jupyter lab examples/hello_eshkol.ipynb
```

Then select the `Eshkol` kernel if Jupyter does not choose it automatically.

## Runtime Options

The kernel reads these environment variables when Jupyter starts it:

- `ESHKOL_REPL`: path to `eshkol-repl` (default: `eshkol-repl`)
- `ESHKOL_KERNEL_LOAD_STDLIB`: load stdlib on startup (`1` by default)
- `ESHKOL_KERNEL_REPL_ARGS`: extra arguments passed to `eshkol-repl`
- `ESHKOL_KERNEL_TIMEOUT`: per-cell execution timeout in seconds (default: `30`)
- `ESHKOL_KERNEL_START_TIMEOUT`: REPL startup timeout in seconds (default: `10`)

If Jupyter launches from an environment that does not inherit your shell
variables, bake the runtime path into the kernelspec:

```bash
eshkol-kernel-install --user --eshkol-repl /absolute/path/to/eshkol-repl
```

The fetch helper supports release tags and flavors:

```bash
eshkol-kernel-fetch-runtime --tag latest --flavor lite --output .external/eshkol
```

Use `.external/` as local setup, not as source code. Installation docs use it
because it gives new contributors a repeatable path, but production or packaged
setups can point the kernelspec at any Eshkol installation.

Linux release binaries may require system BLAS/LAPACK and LLVM runtime
libraries. The CI workflow documents the Ubuntu packages currently needed for
the downloaded Eshkol release.

## Manage The Kernelspec

List installed kernels:

```bash
jupyter kernelspec list
```

Update or reinstall the default `Eshkol` kernelspec:

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
```

CI runs linting, package builds, fake-REPL tests, notebook execution tests, and
a separate real Eshkol smoke test that downloads the release binary.

## Known Limits

- This package targets Unix-like systems where `pexpect` can allocate a
  pseudo-terminal. macOS and Linux are the intended platforms.
- Rich display output currently depends on the JSON line convention above.
- Interrupt behavior depends on the native REPL's signal handling and the
  frontend. Restarting the kernel is the reliable reset path.
