from __future__ import annotations

from pathlib import Path

import nbformat
from jupyter_helpers import execute_and_collect, started_kernel

EXAMPLE = Path(__file__).parents[1] / "examples" / "hello_eshkol.ipynb"


def test_example_notebook_code_cells_execute_with_fake_repl(tmp_path: Path) -> None:
    notebook = nbformat.read(EXAMPLE, as_version=4)
    stdout: list[str] = []

    with started_kernel(tmp_path, kernel_name="eshkol-ipynb-test") as client:
        for cell in notebook.cells:
            if cell.cell_type != "code" or not "".join(cell.source).strip():
                continue

            reply, outputs = execute_and_collect(client, "".join(cell.source))

            assert reply["status"] == "ok"
            stdout.extend(text for name, text in outputs if name == "stdout")

    assert stdout == ["6\n", "41\n", "42\n"]
