from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from eshkol_kernel.kernel import EshkolKernel
from eshkol_kernel.session import EshkolReplSession, EshkolSessionError, LegacyReplSession

FAKE = Path(__file__).with_name("fake_machine_repl.py")


def make_session(*args: str, timeout: float = 3, start_timeout: float = 3) -> EshkolReplSession:
    return EshkolReplSession(sys.executable, [str(FAKE), *args], timeout=timeout, start_timeout=start_timeout)


@pytest.fixture
def session():
    instance = make_session()
    try:
        yield instance
    finally:
        instance.close()


def test_values_state_multiline_and_exact_stdout(session):
    result = session.execute("(define x 41)\n(+ x\n\n 1)\n(value-and-output)")
    assert result.ok
    assert result.stdout == "hello"
    assert result.value == "42"
    assert [e.kind for e in result.output_events] == ["execute_result", "stdout", "execute_result"]
    assert [e.text for e in result.output_events] == ["42", "hello", "42"]
    assert session.execute("x").value == "41"
    assert session.ready_info["eshkol_version"] == "test-runtime"


def test_stdout_is_exact_and_never_classified_as_an_error(session):
    result = session.execute("(print-error-text)")
    assert result.ok
    assert result.stdout == "error: successful user text\neshkol> \x1b[31m untouched  "
    assert result.output_events[0].text == result.stdout
    assert session.execute('"hello"').value == '"hello"'


def test_rich_display_order_and_metadata(session):
    result = session.execute("(mixed-rich)\n(rich-with-metadata)")
    assert result.stdout == "before\nafter\n"
    assert [e.kind for e in result.output_events] == ["stdout", "display_data", "stdout", "display_data"]
    assert result.display_data[-1].transient == {"display_id": "eshkol-demo"}
    assert result.display_data[-1].metadata == {"text/html": {"isolated": True}}


def test_structured_errors_preserve_stdout_and_source_and_stop_remaining_forms(session):
    result = session.execute("(define x 41)\n  (syntax-problem)\n(define skipped 1)")
    assert not result.ok
    assert result.error_name == "EshkolSyntaxError"
    assert result.error["kind"] == "syntax-error"
    assert result.stdout == "before failure"
    assert (result.error_form_index, result.error_form_count) == (2, 3)
    assert (result.error_line, result.error_column) == (2, 3)
    assert "2 |   (syntax-problem)" in result.stderr
    assert session.complete("skipped") == []
    assert session.execute("x").value == "41"
    assert session.execute("(new-error)").error_name == "EshkolError"
    located = session.execute("(define y 1)\n  (location-error)")
    assert (located.error_line, located.error_column) == (2, 5)


def test_pipe_pressure_does_not_block_or_duplicate_stdout(session):
    result = session.execute("(pipe-pressure)")
    assert result.stdout == "x" * 1048576
    assert len(result.output_events) == 1
    assert session.execute("(+ 1 2)").value == "3"


def test_runtime_editor_operations_and_full_reset(session):
    session.execute("(define notebook-name 12)")
    assert session.complete("notebook") == ["notebook-name"]
    assert session.is_complete("(display 1") == "incomplete"
    assert session.is_complete(")") == "invalid"
    pid = session.ready_info["pid"]
    session.reset()
    assert session.ready_info["pid"] != pid
    assert session.complete("notebook") == []


def test_interrupt_preserves_session(session):
    session.start()
    timer = threading.Timer(0.3, session.interrupt)
    timer.start()
    try:
        result = session.execute("(hang)")
    finally:
        timer.cancel()
        timer.join()
    assert result.error_name == "KeyboardInterrupt"
    assert result.error["kind"] == "interrupted"
    assert session.execute("(+ 1 2)").value == "3"


@pytest.mark.parametrize(
    "mode,match",
    [
        ("version2", "version 1"),
        ("legacy-only", "timed out"),
        ("eof", "native dependency missing"),
        ("malformed-ready", "Malformed"),
    ],
)
def test_bad_handshake_cleans_up(mode, match):
    session = make_session("--mode=" + mode, start_timeout=0.2)
    with pytest.raises(EshkolSessionError, match=match):
        session.start()
    assert not session.is_running
    session.close()


@pytest.mark.parametrize(
    "code,match",
    [
        ("(hang)", "timed out"),
        ("(eof)", "protocol pipe"),
        ("(malformed)", "Malformed"),
        ("(wrong-id)", "Unexpected"),
        ("(bad-schema)", "Invalid"),
    ],
)
def test_faults_close_session_and_allow_fresh_start(code, match):
    session = make_session(timeout=0.2)
    try:
        with pytest.raises(EshkolSessionError, match=match):
            session.execute(code)
        assert not session.is_running
        assert session.execute("(+ 1 2)").value == "3"
    finally:
        session.close()


def test_protocol_selection_is_explicit(monkeypatch):
    monkeypatch.delenv("ESHKOL_KERNEL_PROTOCOL", raising=False)
    assert isinstance(EshkolReplSession.from_env(), EshkolReplSession)
    monkeypatch.setenv("ESHKOL_KERNEL_PROTOCOL", "legacy")
    assert isinstance(EshkolReplSession.from_env(), LegacyReplSession)
    monkeypatch.setenv("ESHKOL_KERNEL_PROTOCOL", "auto")
    with pytest.raises(EshkolSessionError, match="machine.*legacy"):
        EshkolReplSession.from_env()


def test_kernel_uses_runtime_metadata_editor_and_ordered_values(session):
    kernel = EshkolKernel(session_factory=lambda: session)
    sent = []
    kernel.send_response = lambda _socket, kind, content: sent.append((kind, content))
    assert kernel.kernel_info["language_info"]["version"] == "test-runtime"
    assert kernel.do_complete("(dis", 4)["matches"] == ["display"]
    assert kernel.do_complete("(dis", 4)["cursor_start"] == 1
    assert kernel.do_is_complete("(") == {"status": "incomplete", "indent": "  "}
    assert kernel.do_execute("(value-and-output)", silent=False)["status"] == "ok"
    assert [kind for kind, _ in sent] == ["stream", "execute_result"]
    assert sent[-1][1]["data"] == {"text/plain": "42"}
    assert sent[-1][1]["metadata"]["eshkol"]["value_type"] == "integer"
    sent.clear()
    kernel.do_execute("(value-and-output)", silent=True)
    assert sent == []


def test_preserves_all_error_port_lines(session):
    result = session.execute("(many-diagnostics)")
    assert result.ok
    assert result.stderr == "".join(f"diagnostic {i}\n" for i in range(100))
    assert result.output_events[0].kind == "stderr"


def test_external_error_does_not_invent_a_column(session):
    result = session.execute("  (external-error)")
    assert result.error_filename == "external.esk"
    assert result.error_line == 7
    assert result.error_column is None
    assert "Runtime location: external.esk:7\n" in result.stderr
    assert result.stderr.rstrip().endswith("external failure")


def test_request_deadline_includes_blocked_stdin_write():
    session = make_session("--mode=stalled-input", timeout=0.1)
    started = time.monotonic()
    try:
        with pytest.raises(EshkolSessionError, match="write timed out"):
            session.execute('"' + "x" * 1048576 + '"')
        assert not session.is_running
        assert time.monotonic() - started < 3
    finally:
        session.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group cleanup")
def test_shutdown_cleans_up_descendants_holding_pipes():
    session = make_session("--mode=descendant")
    session.start()
    client = session._client
    assert session.execute("(+ 1 2)").ok  # Child has spawned its descendant.
    started = time.monotonic()
    session.close()
    assert time.monotonic() - started < 3
    assert not any(thread.is_alive() for thread in client._threads)


@pytest.mark.parametrize("code,unspecified", [
    ("(define x 0)", True),
    ("(define (f x) x)", True),
    ("(define-syntax ident (syntax-rules () ((_ x) x)))", True),
    ("( ; header comment\n define x 1)", True),
    ("(begin (define x 1))", True),
    ("(begin (display 1) (begin (define x 1)))", True),
    ("0", False),
    ("(begin (define x 1) 0)", False),
    ("'(define x 1)", False),
    ('"(define x 1)"', False),
    ("(define-like 1)", False),
])
def test_definition_placeholder_correction_preserves_real_zero_and_output(code, unspecified):
    session = make_session("--mode=zero-result")
    try:
        result = session.execute(code)
    finally:
        session.close()
    assert result.ok
    assert result.stdout == "kept\n"
    assert result.value == ("" if unspecified else "0")
    assert result.value_type == ("unspecified" if unspecified else "integer")
    expected = ["stdout"] if unspecified else ["stdout", "execute_result"]
    assert [event.kind for event in result.output_events] == expected


@pytest.mark.parametrize("code,status", [
    ('"unterminated', "incomplete"),
    ("''", "incomplete"),
    ("' ; unfinished datum", "incomplete"),
    (r"(list #\; #\" #\( #\))", "complete"),
    ('(quote |a)b|)', "complete"),
    ('(quote |a"b|)', "complete"),
    ('(quote |a;b|)', "complete"),
])
def test_native_completeness_is_corrected_for_reader_tokens(session, code, status):
    assert session.is_complete(code) == status
