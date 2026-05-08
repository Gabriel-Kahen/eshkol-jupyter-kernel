from __future__ import annotations

from pathlib import Path

from jupyter_helpers import execute_and_collect, started_kernel


def test_kernel_runs_through_jupyter_client(tmp_path: Path) -> None:
    with started_kernel(tmp_path, kernel_name="eshkol-integration") as client:
        reply, outputs = execute_and_collect(client, "(+ 1 2 3)")

    assert reply["status"] == "ok"
    assert outputs == [("stdout", "6\n")]


def test_kernel_sends_rich_display_data(tmp_path: Path) -> None:
    with started_kernel(tmp_path, kernel_name="eshkol-rich") as client:
        reply, outputs = execute_and_collect(client, "(rich-html)")

    assert reply["status"] == "ok"
    assert outputs == [("display_data", {"text/plain": "hello", "text/html": "<strong>hello</strong>"})]


def test_kernel_preserves_mixed_output_order(tmp_path: Path) -> None:
    with started_kernel(tmp_path, kernel_name="eshkol-mixed-rich") as client:
        reply, outputs = execute_and_collect(client, "(mixed-rich)")

    assert reply["status"] == "ok"
    assert outputs == [
        ("stdout", "before\n"),
        ("display_data", {"text/plain": "middle", "text/html": "<em>middle</em>"}),
        ("stdout", "after\n"),
    ]


def test_kernel_sends_display_helper_data(tmp_path: Path) -> None:
    with started_kernel(tmp_path, kernel_name="eshkol-helper-rich") as client:
        reply, outputs = execute_and_collect(client, "(rich-table)")

    assert reply["status"] == "ok"
    assert outputs[0][0] == "display_data"
    assert "text/html" in outputs[0][1]
    assert "n | square" in outputs[0][1]["text/plain"]
