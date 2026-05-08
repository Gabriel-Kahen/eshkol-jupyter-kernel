from __future__ import annotations

from eshkol_kernel.session import parse_display_data


def test_parse_markdown_helper() -> None:
    display = parse_display_data('{"type":"eshkol_display","format":"markdown","value":"**hello**"}')

    assert display is not None
    assert display.data == {"text/plain": "**hello**", "text/markdown": "**hello**"}


def test_parse_json_helper_pretty_prints_plain_fallback() -> None:
    display = parse_display_data('{"type":"eshkol_display","format":"json","value":{"b":2,"a":1}}')

    assert display is not None
    assert display.data["application/json"] == {"b": 2, "a": 1}
    assert display.data["text/plain"] == '{\n  "a": 1,\n  "b": 2\n}'


def test_parse_json_helper_preserves_explicit_plain_fallback() -> None:
    display = parse_display_data(
        '{"type":"eshkol_display","format":"json","value":{"answer":42},"text/plain":"answer = 42"}'
    )

    assert display is not None
    assert display.data["application/json"] == {"answer": 42}
    assert display.data["text/plain"] == "answer = 42"


def test_parse_pretty_helper_formats_lists_as_eshkol_like_text() -> None:
    display = parse_display_data('{"type":"eshkol_pretty","value":["define",["square","x"],["*","x","x"]]}')

    assert display is not None
    assert display.data["text/plain"] == "(define (square x) (* x x))"
    assert display.data["application/json"] == ["define", ["square", "x"], ["*", "x", "x"]]


def test_parse_table_helper_builds_text_and_html() -> None:
    display = parse_display_data('{"type":"eshkol_table","columns":["n","square"],"rows":[[1,1],[2,4]]}')

    assert display is not None
    assert "n | square" in display.data["text/plain"]
    assert "<table>" in display.data["text/html"]
    assert "<td>4</td>" in display.data["text/html"]


def test_parse_tree_helper_builds_text_and_html() -> None:
    display = parse_display_data('{"type":"eshkol_tree","value":["root",["left"],["right"]]}')

    assert display is not None
    assert "root" in display.data["text/plain"]
    assert "<ul>" in display.data["text/html"]


def test_parse_helper_preserves_metadata_and_transient() -> None:
    display = parse_display_data(
        '{"type":"eshkol_display","format":"html","value":"<b>x</b>",'
        '"metadata":{"text/html":{"isolated":true}},"transient":{"display_id":"demo"}}'
    )

    assert display is not None
    assert display.metadata == {"text/html": {"isolated": True}}
    assert display.transient == {"display_id": "demo"}


def test_unknown_helper_format_remains_plain_stdout() -> None:
    assert parse_display_data('{"type":"eshkol_display","format":"unknown","value":"x"}') is None
