"""Additional native controls for the EREPL v1 compatibility corrections."""
from __future__ import annotations

from test_runtime_compatibility import (
    assert_ok,
    stdout,
    values,
)
from test_runtime_compatibility import (
    machine_kernel as machine_kernel,
)
from test_runtime_compatibility import (
    runtime_kernel as runtime_kernel,
)


def test_native_reader_completeness_controls(machine_kernel):
    for code in [r'(list #\; #\" #\( #\))', '(quote |a)b|)', '(quote |a"b|)',
                 '(quote |a;b|)', '(quote foo|bar)', '(display "greeting ~{(string-append "(" "x")}")']:
        reply = machine_kernel.request("is_complete", code)["content"]
        assert reply["status"] == "complete", (code, reply)
    for code in ["''", "' ; comment", '"unfinished', '(quote |unfinished']:
        assert machine_kernel.request("is_complete", code)["content"]["status"] == "incomplete"


def test_native_adjacent_datums_characters_and_interpolation(machine_kernel):
    adjacent = machine_kernel.execute('"one""two" 0(+ 1 2)')
    assert_ok(adjacent)
    assert values(adjacent) == ['"one"', '"two"', "0", "3"]
    for code, expected in [(r'#\;', r'#\;'), (r'#\(', r'#\('), (r'#\)', r'#\)'),
                           (r'#\"', r'#\"'), ('(quote |a)b|)', '|a)b|'),
                           ('(quote |a"b|)', '|a"b|'), ('(quote |a;b|)', '|a;b|'), ('(quote foo|bar)', r'|foo\|bar|')]:
        result = machine_kernel.execute(code)
        assert_ok(result)
        assert values(result) == [expected], (code, result)
    for code, expected in [
        ('(display "greeting ~{(string-append "(" "x")}")', 'greeting (x'),
        ('(display "greeting ~~{literal}")', 'greeting ~{literal}'),
    ]:
        result = machine_kernel.execute(code)
        assert_ok(result)
        assert stdout(result) == expected
        assert values(result) == []


def test_native_definition_results_preserve_state_and_meaningful_zero(machine_kernel):
    for code in ["(define reader-state 1)", "(define (reader-f x) (+ x 1))",
                 "(begin (display \"kept\") (begin (define reader-other 2)))",
                 "(define-syntax reader-id (syntax-rules () ((_ x) x)))"]:
        result = machine_kernel.execute(code)
        assert_ok(result)
        assert values(result) == [], (code, result)
        if "kept" in code:
            assert stdout(result) == "kept"
    result = machine_kernel.execute("(reader-id (reader-f reader-state))")
    assert_ok(result)
    assert values(result) == ["2"]
    for code in ["0", "(- 1 1)", "(begin (define reader-zero 99) 0)"]:
        result = machine_kernel.execute(code)
        assert_ok(result)
        assert values(result) == ["0"], (code, result)
    quoted = machine_kernel.execute("'(define reader-unexecuted 1)")
    assert_ok(quoted)
    assert values(quoted) == ["(define reader-unexecuted 1)"]
