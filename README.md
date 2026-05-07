# Eshkol Jupyter Kernel

A Jupyter kernel for Eshkol. It lets JupyterLab, classic Notebook, VS Code
notebooks, and other Jupyter clients execute Eshkol code cells through a
long-lived `eshkol-repl` process.

This is separate from the standalone `eshkol-notebook` web app. That app owns
its own notebook UI and browser VM integration. This package plugs Eshkol into
the standard Jupyter `.ipynb` ecosystem.

## Status

Alpha, but usable:

- Stateful code execution through `eshkol-repl`
- Multiline cell handling
- Multiple top-level forms in one cell
- Text output and error reporting
- Kernel completion for common Scheme/Eshkol forms
- Kernel installation via `eshkol-kernel-install`

The kernel expects `eshkol-repl` to be installed and available on `PATH`, or
configured with `ESHKOL_REPL`.

## Install

Clone this repo and create a Python environment:

```bash
git clone https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel.git
cd eshkol-jupyter-kernel
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Then install the Jupyter kernelspec. If `eshkol-repl` is already on `PATH`:

```bash
eshkol-kernel-install --user
```

Then open JupyterLab, classic Notebook, or VS Code and select the `Eshkol`
kernel.

To pin the kernelspec to a specific Eshkol release binary:

```bash
eshkol-kernel-install --user --eshkol-repl /path/to/eshkol-repl
```

To fetch the latest compatible Eshkol release binary from GitHub into this repo:

```bash
python scripts/fetch_eshkol_release.py
eshkol-kernel-install --user --eshkol-repl "$PWD/.external/eshkol/bin/eshkol-repl"
```

To use the included example notebook with JupyterLab:

```bash
pip install jupyterlab
jupyter lab examples/hello_eshkol.ipynb
```

## Configure

Environment variables:

- `ESHKOL_REPL`: path to `eshkol-repl` (default: `eshkol-repl`)
- `ESHKOL_KERNEL_LOAD_STDLIB`: load stdlib on startup (`1` by default)
- `ESHKOL_KERNEL_REPL_ARGS`: extra arguments passed to `eshkol-repl`
- `ESHKOL_KERNEL_TIMEOUT`: per-cell execution timeout in seconds (default: `30`)
- `ESHKOL_KERNEL_START_TIMEOUT`: REPL startup timeout in seconds (default: `10`)

Example:

```bash
ESHKOL_REPL=/path/to/eshkol-repl eshkol-kernel-install --user
```

If Jupyter launches from an environment that does not inherit your shell
variables, set the variable before starting Jupyter itself.
Alternatively, use `eshkol-kernel-install --eshkol-repl /path/to/eshkol-repl`
to write that path directly into the kernelspec.

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
pip install -e '.[test]'
pytest
```

The tests use a fake REPL so they can run even when Eshkol itself is not
installed.

## Known Limits

- This package currently targets Unix-like systems where `pexpect` can allocate
  a pseudo-terminal. macOS and Linux are the intended platforms.
- Rich display output is not implemented yet. Text output works; plots/images
  should be added once Eshkol exposes a stable notebook display convention.
- Interrupt behavior depends on the native REPL's signal handling and the
  frontend. Restarting the kernel is the reliable reset path.
