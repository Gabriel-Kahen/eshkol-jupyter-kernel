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


def make_short_timeout_session() -> EshkolReplSession:
    return EshkolReplSession(
        executable=sys.executable,
        argv=[str(FAKE_REPL)],
        load_stdlib=False,
        timeout=0.2,
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


def test_execute_preserves_mixed_output_order_events() -> None:
    session = make_session()
    try:
        result = session.execute("(mixed-rich)")
    finally:
        session.close()

    assert result.ok
    assert result.stdout == "before\nafter\n"
    assert [event.kind for event in result.output_events] == ["stdout", "display_data", "stdout"]
    assert result.output_events[0].text == "before\n"
    assert result.output_events[1].display_data is not None
    assert result.output_events[1].display_data.data["text/plain"] == "middle"
    assert result.output_events[2].text == "after\n"


def test_execute_does_not_strip_prompt_text_from_stdout() -> None:
    session = make_session()
    try:
        result = session.execute("(display-prompt-text)")
    finally:
        session.close()

    assert result.ok
    assert "value: eshkol> still user text" in result.stdout
    assert "coords: [1,2]> still user text" in result.stdout


def test_execute_does_not_classify_plain_error_word_as_failure() -> None:
    session = make_session()
    try:
        result = session.execute("(relative-error)")
    finally:
        session.close()

    assert result.ok
    assert result.stdout == "relative error is 0.01\n"


def test_execute_recovers_after_timeout() -> None:
    session = make_short_timeout_session()
    try:
        with pytest.raises(EshkolSessionError, match="timed out"):
            session.execute("(hang)")
        result = session.execute("(+ 1 2 3)")
    finally:
        session.close()

    assert result.ok
    assert result.stdout == "6\n"


def test_classify_error_variants() -> None:
    assert classify_error("runtime-error: undefined variable") == "EshkolRuntimeError"
    assert classify_error("division by zero") == "EshkolZeroDivisionError"
    assert classify_error("relative error is 0.01") is None
    assert classify_error("ordinary output") is None


def test_missing_executable_error() -> None:
    session = EshkolReplSession(executable="definitely-not-eshkol-repl", load_stdlib=False)
    with pytest.raises(EshkolSessionError):
        session.start()


def test_clean_repl_output_strips_prompts_and_ansi() -> None:
    raw = "\x1b[35meshkol\x1b[0m\x1b[35m> \x1b[0m42\r\n  [1,2]> more"
    assert clean_repl_output(raw) == "42\nmore"
