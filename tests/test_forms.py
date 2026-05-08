from __future__ import annotations

import pytest

from eshkol_kernel.forms import (
    IncompleteInput,
    UnmatchedDelimiter,
    check_completeness,
    split_top_level_form_sources,
    split_top_level_forms,
)


def test_split_multiple_top_level_forms() -> None:
    assert split_top_level_forms("(define x 1)\n(+ x 2)") == ["(define x 1)", "(+ x 2)"]


def test_split_keeps_multiline_form_together() -> None:
    code = """
(define (square x)
  (* x x))

(square 4)
"""
    assert split_top_level_forms(code) == ["(define (square x)\n  (* x x))", "(square 4)"]


def test_split_reports_form_source_spans() -> None:
    code = "; heading\n(define x 1)\n\n(+ x 2)"

    forms = split_top_level_form_sources(code)

    assert [form.text for form in forms] == ["(define x 1)", "(+ x 2)"]
    assert code[forms[0].start : forms[0].end] == "(define x 1)"
    assert code[forms[1].start : forms[1].end] == "(+ x 2)"


def test_split_ignores_top_level_comments() -> None:
    assert split_top_level_forms("; hello\n(define x 1) ; trailing\nx") == ["(define x 1)", "x"]


def test_split_respects_strings() -> None:
    assert split_top_level_forms('(display "not ) a delimiter")\n(+ 1 2)') == [
        '(display "not ) a delimiter")',
        "(+ 1 2)",
    ]


def test_split_keeps_quoted_compound_datum_together() -> None:
    assert split_top_level_forms("'(1 2)\n`(3 4)\n,@(items)\n#(5 6)") == [
        "'(1 2)",
        "`(3 4)",
        ",@(items)",
        "#(5 6)",
    ]


def test_split_quoted_atom() -> None:
    assert split_top_level_forms("'x 'y") == ["'x", "'y"]


def test_split_quoted_datum_after_comment() -> None:
    assert split_top_level_forms("' ; comment\n(1 2)") == ["' ; comment\n(1 2)"]


def test_incomplete_input() -> None:
    with pytest.raises(IncompleteInput):
        split_top_level_forms("(define x")
    completeness = check_completeness("(define x")
    assert completeness.status == "incomplete"
    assert completeness.indent == "  "


def test_incomplete_datum_prefix() -> None:
    with pytest.raises(IncompleteInput):
        split_top_level_forms("'")
    assert check_completeness("'").status == "incomplete"


def test_unmatched_delimiter() -> None:
    with pytest.raises(UnmatchedDelimiter):
        split_top_level_forms("(+ 1 2))")
    assert check_completeness("(+ 1 2))").status == "invalid"
