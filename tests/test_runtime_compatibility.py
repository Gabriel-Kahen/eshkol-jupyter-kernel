"""Opt-in behavioral compatibility checks through real Jupyter channels.

Run with ESHKOL_REAL_REPL=/absolute/path/to/eshkol-repl. A missing setting
skips; a configured but unusable executable is a test failure.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from shutil import which
from threading import Timer
from typing import Any

import nbformat
import pytest
from compatibility_helpers import KernelHarness, running_kernel

from eshkol_kernel.session import EshkolReplSession, EshkolSessionError


@pytest.fixture
def runtime_kernel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    configured = os.environ.get("ESHKOL_REAL_REPL")
    if not configured:
        pytest.skip("Set ESHKOL_REAL_REPL to run actual runtime compatibility tests")
    executable = which(configured)
    if executable is None:
        pytest.fail(f"Configured ESHKOL_REAL_REPL is missing or not executable: {configured}")
    transport = os.environ.get("ESHKOL_COMPAT_TRANSPORT", "machine")
    if transport not in {"machine", "legacy"}:
        pytest.fail(f"Unsupported ESHKOL_COMPAT_TRANSPORT: {transport}")
    # Starting outside either source tree catches accidental cwd-based stdlib discovery.
    monkeypatch.chdir(tmp_path)
    env = {
        "ESHKOL_KERNEL_PROTOCOL": transport,
        "ESHKOL_KERNEL_LOAD_STDLIB": "1",
        "ESHKOL_KERNEL_START_TIMEOUT": "60",
        "ESHKOL_KERNEL_TIMEOUT": "10",
    }
    with running_kernel(tmp_path, executable, env=env, timeout=75) as kernel:
        yield kernel


@pytest.fixture
def machine_kernel(runtime_kernel: KernelHarness) -> KernelHarness:
    if os.environ.get("ESHKOL_COMPAT_TRANSPORT", "machine") != "machine":
        pytest.skip("Structured results and runtime operations require EREPL v1 machine transport")
    return runtime_kernel


@pytest.fixture
def machine_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    configured = os.environ.get("ESHKOL_REAL_REPL")
    if not configured:
        pytest.skip("Set ESHKOL_REAL_REPL to run actual runtime compatibility tests")
    executable = which(configured)
    if executable is None:
        pytest.fail(f"Configured ESHKOL_REAL_REPL is missing or not executable: {configured}")
    if os.environ.get("ESHKOL_COMPAT_TRANSPORT", "machine") != "machine":
        pytest.skip("Direct machine session lifecycle requires EREPL v1")
    monkeypatch.chdir(tmp_path)
    for key, value in {
        "ESHKOL_REPL": executable,
        "ESHKOL_KERNEL_PROTOCOL": "machine",
        "ESHKOL_KERNEL_REPL_ARGS": "",
        "ESHKOL_KERNEL_LOAD_STDLIB": "1",
        "ESHKOL_KERNEL_START_TIMEOUT": "60",
        "ESHKOL_KERNEL_TIMEOUT": "10",
    }.items():
        monkeypatch.setenv(key, value)
    session = EshkolReplSession.from_env()
    try:
        yield session
    finally:
        session.close()
        assert not session.is_running


def assert_process_exited(pid: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail(f"Runtime process {pid} remained alive after session cleanup")


def content(exchange: dict[str, Any]) -> dict[str, Any]:
    return exchange["reply"]["content"]


def messages(exchange: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [message["content"] for message in exchange["messages"] if message["msg_type"] == kind]


def stdout(exchange: dict[str, Any]) -> str:
    return "".join(item["text"] for item in messages(exchange, "stream") if item["name"] == "stdout")


def values(exchange: dict[str, Any]) -> list[str]:
    return [item["data"]["text/plain"] for item in messages(exchange, "execute_result")]


def assert_ok(exchange: dict[str, Any]) -> None:
    assert content(exchange)["status"] == "ok", content(exchange)
    assert not messages(exchange, "error")


def display_literal(text: str) -> str:
    return f"(display {json.dumps(text, ensure_ascii=False)})"


def test_state_multiline_and_multiple_forms(runtime_kernel: KernelHarness) -> None:
    first = runtime_kernel.execute(
        "; a notebook cell can contain several forms\n"
        "(define compat-state 40)\n"
        "(set! compat-state\n  (+ compat-state 1))\n"
        "(+ compat-state 1) ; final value is not the stored state\n"
    )
    assert_ok(first)
    second = runtime_kernel.execute("compat-state")
    assert_ok(second)
    if os.environ.get("ESHKOL_COMPAT_TRANSPORT", "machine") == "machine":
        assert values(first)[-1] == "42"
        assert values(second) == ["41"]
    else:
        assert stdout(first).strip() == "42"
        assert stdout(second).strip() == "41"


@pytest.mark.parametrize("text", [
    "Error: user-authored data\nsyntax-error: also ordinary output\n",
    "eshkol> user prompt text\n[1,2]> coordinates\n",
    "EREPL READY\nEREPL DONE\nEREPL FAIL\n",
    "  leading and trailing spaces  \n\n",
    "no trailing newline",
    "λ → café 日本語 🐚\n",
])
def test_stdout_is_byte_exact_and_does_not_become_an_error(machine_kernel: KernelHarness, text: str) -> None:
    result = machine_kernel.execute(display_literal(text))
    assert_ok(result)
    assert stdout(result) == text
    assert values(result) == []


def test_stdout_and_return_value_are_separate(machine_kernel: KernelHarness) -> None:
    result = machine_kernel.execute('(begin (display "answer=") (+ 40 2))')
    assert_ok(result)
    assert stdout(result) == "answer="
    assert values(result) == ["42"]
    relevant = [item["msg_type"] for item in result["messages"] if item["msg_type"] in {"stream", "execute_result"}]
    assert relevant == ["stream", "execute_result"]


@pytest.mark.parametrize(("code", "expected"), [
    ('"hello Eshkol"', '"hello Eshkol"'),
    ("#t", "#t"),
    ("#f", "#f"),
    ("(list 1 2 3)", "(1 2 3)"),
    ("(quote ())", "()"),
])
def test_return_values_use_unambiguous_write_format(machine_kernel: KernelHarness, code: str, expected: str) -> None:
    result = machine_kernel.execute(code)
    assert_ok(result)
    assert stdout(result) == ""
    assert values(result) == [expected]


def test_language_error_stops_cell_and_preserves_prior_state(machine_kernel: KernelHarness) -> None:
    assert_ok(machine_kernel.execute("(define compat-before-error 7)"))
    failed = machine_kernel.execute("(set! compat-before-error 8)\n(car (quote ()))\n(set! compat-before-error 99)")
    assert content(failed)["status"] == "error"
    assert content(failed)["ename"] == "EshkolTypeError"
    errors = messages(failed, "error")
    assert len(errors) == 1
    assert errors[0]["ename"] == content(failed)["ename"]
    recovered = machine_kernel.execute("(+ compat-before-error 1)")
    assert_ok(recovered)
    assert values(recovered) == ["9"]


def test_stdout_before_error_in_same_form_is_retained(machine_kernel: KernelHarness) -> None:
    failed = machine_kernel.execute('(begin (display "before failure\\n") (car (quote ())))')
    assert content(failed)["status"] == "error"
    assert stdout(failed) == "before failure\n"
    assert values(failed) == []
    kinds = [item["msg_type"] for item in failed["messages"]]
    assert kinds.index("stream") < kinds.index("error")


def test_completion_uses_real_bindings_without_comment_ghosts(machine_kernel: KernelHarness) -> None:
    assert_ok(machine_kernel.execute("; (define compat-ghost 99)\n(define compat-real-binding 42)"))
    reply = machine_kernel.request("complete", "(+ compat-", len("(+ compat-"))["content"]
    assert reply["status"] == "ok"
    assert "compat-real-binding" in reply["matches"]
    assert "compat-ghost" not in reply["matches"]
    assert reply["cursor_start"] == 3
    assert reply["cursor_end"] == len("(+ compat-")


@pytest.mark.parametrize(("code", "status"), [
    ("(+ 1\n 2)", "complete"),
    ('(display "parenthesis ) in string") ; ( in comment', "complete"),
    ("(define unfinished", "incomplete"),
    ('"unterminated', "incomplete"),
    ("'", "incomplete"),
    (")", "invalid"),
])
def test_runtime_completeness(machine_kernel: KernelHarness, code: str, status: str) -> None:
    reply = machine_kernel.request("is_complete", code)["content"]
    assert reply["status"] == status, reply


def test_stdlib_is_discovered_from_unrelated_working_directory(machine_kernel: KernelHarness) -> None:
    result = machine_kernel.execute("(length (map (lambda (x) (* x x)) (list 1 2 3)))")
    assert_ok(result)
    assert values(result) == ["3"]


def test_explicit_scheme_base_import_and_evaluation(machine_kernel: KernelHarness) -> None:
    imported = machine_kernel.execute("(import (scheme base))")
    assert_ok(imported)
    computed = machine_kernel.execute("(length (map (lambda (x) (+ x 1)) (list 1 2 3)))")
    assert_ok(computed)
    assert stdout(computed) == ""
    assert values(computed) == ["3"]


def test_timeout_stops_runtime_and_next_execution_starts_cleanly(machine_session: EshkolReplSession) -> None:
    machine_session.start()
    original_pid = machine_session.ready_info["pid"]
    machine_session.timeout = 0.2
    started = time.monotonic()
    with pytest.raises(EshkolSessionError, match="timed out"):
        machine_session.execute("(let loop () (loop))")
    assert time.monotonic() - started < 5
    assert not machine_session.is_running
    assert_process_exited(original_pid)
    machine_session.timeout = 10
    recovered = machine_session.execute("(+ 40 2)")
    assert recovered.ok, recovered.stderr
    assert recovered.stdout == ""
    assert recovered.value == "42"
    replacement_pid = machine_session.ready_info["pid"]
    machine_session.close()
    assert not machine_session.is_running
    assert_process_exited(replacement_pid)


def test_process_exit_reports_error_and_next_execution_restarts(machine_session: EshkolReplSession) -> None:
    machine_session.start()
    original_pid = machine_session.ready_info["pid"]
    started = time.monotonic()
    with pytest.raises(EshkolSessionError, match="closed|exited|EOF"):
        machine_session.execute("(exit 0)")
    assert time.monotonic() - started < 5
    assert not machine_session.is_running
    assert_process_exited(original_pid)
    recovered = machine_session.execute("(+ 40 2)")
    assert recovered.ok, recovered.stderr
    assert recovered.stdout == ""
    assert recovered.value == "42"
    replacement_pid = machine_session.ready_info["pid"]
    machine_session.close()
    assert not machine_session.is_running
    assert_process_exited(replacement_pid)


def test_rich_output_order_metadata_and_final_value(machine_kernel: KernelHarness) -> None:
    payload = json.dumps({
        "type": "display_data",
        "data": {"text/plain": "middle", "text/html": "<strong>middle</strong>"},
        "metadata": {"text/html": {"isolated": True}},
        "transient": {"display_id": "compat-display"},
    })
    forms = [display_literal("before\n"), display_literal(payload + "\n"), display_literal("after\n"), "42"]
    result = machine_kernel.execute("(begin " + " ".join(forms) + ")")
    assert_ok(result)
    output = [item for item in result["messages"] if item["msg_type"] in {"stream", "display_data", "execute_result"}]
    assert [item["msg_type"] for item in output] == ["stream", "display_data", "stream", "execute_result"]
    assert output[0]["content"]["text"] == "before\n"
    assert output[1]["content"]["data"] == {"text/plain": "middle", "text/html": "<strong>middle</strong>"}
    assert output[1]["content"]["metadata"] == {"text/html": {"isolated": True}}
    assert output[1]["content"]["transient"] == {"display_id": "compat-display"}
    assert output[2]["content"]["text"] == "after\n"
    assert output[3]["content"]["data"]["text/plain"] == "42"


def test_silent_execution_suppresses_output_and_history(machine_kernel: KernelHarness) -> None:
    first = machine_kernel.execute("(define compat-silent-state 1)")
    assert_ok(first)
    silent = machine_kernel.execute('(begin (set! compat-silent-state 2) (display "hidden") 99)', silent=True)
    assert_ok(silent)
    assert {item["msg_type"] for item in silent["messages"]} <= {"status"}
    last = machine_kernel.execute("compat-silent-state")
    assert_ok(last)
    assert values(last) == ["2"]
    assert content(last)["execution_count"] == content(first)["execution_count"] + 1


def test_interrupt_is_bounded_and_preserves_state(machine_kernel: KernelHarness) -> None:
    assert_ok(machine_kernel.execute("(define compat-interrupt-state 41)"))
    timer = Timer(1.5, machine_kernel.interrupt)
    started = time.monotonic()
    timer.start()
    try:
        interrupted = machine_kernel.execute("(let loop () (loop))")
    finally:
        timer.cancel()
        timer.join(timeout=2)
    assert time.monotonic() - started < 15
    assert content(interrupted)["status"] == "error"
    assert content(interrupted)["ename"] in {"KeyboardInterrupt", "EshkolInterrupted", "EshkolInterruptedError"}
    recovered = machine_kernel.execute("(+ compat-interrupt-state 1)")
    assert_ok(recovered)
    assert values(recovered) == ["42"]


def test_nbclient_notebook_error_recovery_and_saved_outputs(machine_kernel: KernelHarness, tmp_path: Path) -> None:
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell("(define compat-notebook-state 41)"),
        nbformat.v4.new_code_cell("(+ compat-notebook-state 1)"),
        nbformat.v4.new_code_cell("(car (quote ()))"),
        nbformat.v4.new_code_cell("compat-notebook-state"),
    ])
    executed = machine_kernel.execute_notebook(notebook, allow_errors=True)
    target = tmp_path / "compatibility-executed.ipynb"
    nbformat.write(executed, target)
    saved = nbformat.read(target, as_version=4)
    nbformat.validate(saved)
    assert saved.cells[1].outputs[0].output_type == "execute_result"
    assert saved.cells[1].outputs[0].data["text/plain"] == "42"
    errors = [output for output in saved.cells[2].outputs if output.output_type == "error"]
    assert len(errors) == 1
    assert errors[0].ename == "EshkolTypeError"
    assert saved.cells[3].outputs[0].data["text/plain"] == "41"
    counts = [cell.execution_count for cell in saved.cells]
    assert counts == sorted(set(counts))


def test_kernel_info_exposes_runtime_version(machine_kernel: KernelHarness) -> None:
    reply = machine_kernel.request("kernel_info")["content"]
    assert reply["status"] == "ok"
    assert reply["language_info"]["name"] == "eshkol"
    assert reply["language_info"]["version"] not in {"", "unknown"}
    assert reply["protocol_version"].startswith("5.")


def test_execute_reply_and_iopub_use_same_parent_and_order(machine_kernel: KernelHarness) -> None:
    exchange = machine_kernel.execute("(+ 1 2)")
    assert_ok(exchange)
    parent = exchange["reply"]["parent_header"]["msg_id"]
    assert all(m["parent_header"]["msg_id"] == parent for m in exchange["messages"])
    states = [m["execution_state"] for m in messages(exchange, "status")]
    assert states == ["busy", "idle"]
    assert exchange["messages"][-1]["msg_type"] == "status"
    assert values(exchange) == ["3"]


def test_definition_has_unspecified_result(machine_kernel: KernelHarness) -> None:
    result = machine_kernel.execute("(define compat-definition-result 41)")
    assert_ok(result)
    assert stdout(result) == ""
    assert values(result) == []
