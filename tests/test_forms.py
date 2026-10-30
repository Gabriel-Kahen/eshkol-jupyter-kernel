from __future__ import annotations

import pytest

from eshkol_kernel.forms import (
    IncompleteInput,
    UnmatchedDelimiter,
    check_completeness,
    form_head_symbol,
    has_character_literal,
    has_escaped_identifier,
    has_incomplete_reader_token,
    has_interpolation,
    is_definition_form,
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


@pytest.mark.parametrize(("code", "expected"), [
    ('"a""b"', ['"a"', '"b"']),
    ("42(+ 1 2)", ["42", "(+ 1 2)"]),
    ("'x'(a)", ["'x", "'(a)"]),
    ("''x", ["''x"]),
    ("`(a ,x ,@items)", ["`(a ,x ,@items)"]),
    ("#(1 [2 3])4", ["#(1 [2 3])", "4"]),
    ('|a;b||a)b||a"b|', ["|a;b|", "|a)b|", '|a"b|']),
    (r"|a\|b|", [r"|a\|b|"]),
    (r'"escaped \\\" quote"', [r'"escaped \\\" quote"']),
])
def test_reader_datums_and_adjacent_boundaries(code: str, expected: list[str]) -> None:
    assert split_top_level_forms(code) == expected
    assert check_completeness(code).status == "complete"


@pytest.mark.parametrize("literal", [r"#\;", r'#\"', r"#\(", r"#\)", r"#\'", r"#\\", r"#\space", r"#\|"])
def test_character_literals_do_not_become_structural_tokens(literal: str) -> None:
    code = f"(list {literal})"
    assert split_top_level_forms(code) == [code]
    assert check_completeness(code).status == "complete"
    assert has_character_literal(code)
    assert not has_incomplete_reader_token(code)


def test_character_semicolon_and_following_real_comment() -> None:
    code = "#\\;; actual line comment\n42"
    assert split_top_level_forms(code) == ["#\\;", "42"]


@pytest.mark.parametrize("code", [
    '"unterminated', '"escaped trailing\\', "'", "''", "`", ",", ",@",
    "' ; waiting for datum", "(list '", '(list "unfinished', "|unfinished", "(quote |unfinished",
])
def test_reader_token_incompleteness_is_independent_of_list_depth(code: str) -> None:
    with pytest.raises(IncompleteInput):
        split_top_level_forms(code)
    assert has_incomplete_reader_token(code)
    assert check_completeness(code).status == "incomplete"


@pytest.mark.parametrize("code", ["(", "(list 1", "#(1", "[1 2", "#\\"])
def test_ordinary_unfinished_compounds_are_not_reader_token_overrides(code: str) -> None:
    assert check_completeness(code).status == "incomplete"
    assert not has_incomplete_reader_token(code)


@pytest.mark.parametrize("code", ["([)]", "[)", "'(a ')" , ")", "(+ 1 2)]"])
def test_mismatched_or_unmatched_delimiters_are_invalid(code: str) -> None:
    with pytest.raises(UnmatchedDelimiter):
        split_top_level_forms(code)
    assert check_completeness(code).status == "invalid"
    assert not has_incomplete_reader_token(code)


@pytest.mark.parametrize("code", [r'"#\\;"', "; #\\(\n42", "(quote |#\\;|)"])
def test_character_detection_ignores_strings_comments_and_escaped_identifiers(code: str) -> None:
    assert not has_character_literal(code)


@pytest.mark.parametrize("code", ['(quote |a"b|)', "(quote |a;b|)", "(quote |a)b|)"])
def test_native_escaped_identifier_controls(code: str) -> None:
    assert split_top_level_forms(code) == [code]
    assert has_escaped_identifier(code)
    assert check_completeness(code).status == "complete"


@pytest.mark.parametrize("code", ['"|not an identifier|"', "; |comment\n42", r"#\|"])
def test_escaped_identifier_detection_ignores_strings_comments_and_characters(code: str) -> None:
    assert not has_escaped_identifier(code)


@pytest.mark.parametrize("code", ["(define x 0)", "(define (f x) x)", "; heading\n( ; head comment\n define x 0)"])
def test_exact_definition_head_after_trivia(code: str) -> None:
    assert is_definition_form(code)
    assert form_head_symbol(code) == "define"


@pytest.mark.parametrize("code", [
    "'(define x 0)", "(quote (define x 0))", "(begin (define x 0) 0)",
    "(define-like x 0)", '(display "(define x 0)")', "(define x 0)\nx", "(define", "()",
])
def test_definition_detection_does_not_classify_quoted_data_or_other_forms(code: str) -> None:
    assert not is_definition_form(code)


def test_generic_head_supports_explicit_adapter_policy() -> None:
    assert form_head_symbol("(define-syntax name rules)") == "define-syntax"
    assert not is_definition_form("(define-syntax name rules)")
    assert form_head_symbol("(begin 0)") == "begin"


def test_unsupported_comment_syntax_is_not_silently_discarded() -> None:
    assert split_top_level_forms("#; (define x 1)") == ["#;", "(define x 1)"]
    assert split_top_level_forms("#| unsupported-token") == ["#|", "unsupported-token"]
    with pytest.raises(IncompleteInput):
        split_top_level_forms("#| not a native comment |# (define x 1)")
    assert not is_definition_form("#; (define x 1)")


def test_reader_spans_preserve_original_prefix_comments_and_adjacency() -> None:
    code = '; heading\n  \' ; reader comment\n (#\\; |a)b|)"next" 42(define x 0)'
    forms = split_top_level_form_sources(code)
    assert [form.text for form in forms] == ["' ; reader comment\n (#\\; |a)b|)", '"next"', "42", "(define x 0)"]
    for form in forms:
        assert code[form.start:form.end] == form.text
    assert forms[0].start == code.index("'")
    assert forms[-1].end == len(code)


def test_excessive_nesting_fails_with_form_error_instead_of_recursion_error() -> None:
    assert check_completeness("(" * 300 + "0" + ")" * 300).status == "invalid"


@pytest.mark.parametrize("code", [
    '(display "greeting ~{(string-append "(" "x")}")',
    r'(display "greeting ~{(string-append \"(\" \"x\")}")',
    '(display "brace ~{(string-append "}" "x")}")',
    '"sum ~{(+ 1 2)}; next ~{(+ 3 4)}"',
    r'(display "characters ~{(list #\( #\))}")',
    '(display "identifier ~{(quote |a)b|)}")',
])
def test_interpolated_strings_preserve_nested_expression_source(code: str) -> None:
    assert split_top_level_forms(code) == [code]
    assert check_completeness(code).status == "complete"
    assert has_interpolation(code)
    assert not has_incomplete_reader_token(code)


def test_interpolation_and_adjacent_string_keep_exact_source_spans() -> None:
    code = '  "~{(string-append "(" "x")}""after"42'
    forms = split_top_level_form_sources(code)
    assert [form.text for form in forms] == ['"~{(string-append "(" "x")}"', '"after"', "42"]
    assert all(code[form.start:form.end] == form.text for form in forms)


@pytest.mark.parametrize("code", [
    '"literal ~~{nothing}"', '"literal ~~{ no closer needed"',
    '(quote |~{identifier}|)', '; ~{comment\n42', r'"escaped \~{not active}"',
])
def test_interpolation_markers_in_literal_or_escaped_text_are_not_active(code: str) -> None:
    assert check_completeness(code).status == "complete"
    assert not has_interpolation(code)


@pytest.mark.parametrize("code", ['"~{(+ 1 2)', '(display "~{(string-append "(" "x")', '"~{name'])
def test_unterminated_interpolation_is_an_incomplete_reader_token(code: str) -> None:
    assert has_interpolation(code)
    assert has_incomplete_reader_token(code)
    assert check_completeness(code).status == "incomplete"


def test_pipe_inside_ordinary_symbol_is_not_an_escaped_identifier():
    assert split_top_level_forms("(quote foo|bar) foo|bar |a||b|") == [
        "(quote foo|bar)", "foo|bar", "|a|", "|b|",
    ]
    assert form_head_symbol("(define|suffix x)") == "define|suffix"
    assert not is_definition_form("(define|suffix x)")
