from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eshkol_kernel.session import EshkolReplSession, EshkolSessionError, classify_error, clean_repl_output

FAKE_REPL = Path(__file__).with_name("fake_eshkol_repl.py")


def make_session() -> EshkolReplSession:
    return EshkolReplSession(
        executable=sys.executable,
        argv=[str(FAKE_REPL)],
        load_stdlib=False,
        timeout=5,
        start_timeout=5,
    )


def test_execute_single_form() -> None:
    session = make_session()
    try:
        result = session.execute("(+ 1 2 3)")
    finally:
        session.close()
    assert result.ok
    assert result.stdout == "6\n"


def test_execute_multiple_forms_preserves_state() -> None:
    session = make_session()
    try:
        result = session.execute("(define x 41)\nx")
    finally:
        session.close()
    assert result.ok
    assert result.stdout == "41\n"


def test_execute_multiline_form() -> None:
    session = make_session()
    try:
        result = session.execute("(display \"hello\")")
    finally:
        session.close()
    assert result.ok
    assert result.stdout == "hello\n"


def test_execute_reports_error_text() -> None:
    session = make_session()
    try:
        result = session.execute("(cause-error)")
    finally:
        session.close()
    assert not result.ok
    assert "synthetic failure" in result.stderr


def test_execute_classifies_syntax_errors() -> None:
    session = make_session()
    try:
        result = session.execute("(syntax-problem)")
    finally:
        session.close()
    assert not result.ok
    assert result.error_name == "EshkolSyntaxError"
    assert "unexpected closing delimiter" in result.stderr


def test_execute_extracts_rich_display_data() -> None:
    session = make_session()
    try:
        result = session.execute("(rich-html)")
    finally:
        session.close()
    assert result.ok
    assert result.stdout == ""
    assert len(result.display_data) == 1
    assert result.display_data[0].data["text/html"] == "<strong>hello</strong>"


def test_classify_error_variants() -> None:
    assert classify_error("runtime-error: undefined variable") == "EshkolRuntimeError"
    assert classify_error("division by zero") == "EshkolZeroDivisionError"
    assert classify_error("ordinary output") is None


def test_missing_executable_error() -> None:
    session = EshkolReplSession(executable="definitely-not-eshkol-repl", load_stdlib=False)
    with pytest.raises(EshkolSessionError):
        session.start()


def test_clean_repl_output_strips_prompts_and_ansi() -> None:
    raw = "\x1b[35meshkol\x1b[0m\x1b[35m> \x1b[0m42\r\n  [1,2]> more"
    assert clean_repl_output(raw) == "42\nmore"
