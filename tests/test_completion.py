from __future__ import annotations

from eshkol_kernel.completion import complete, extract_defined_symbols


def test_extract_defined_symbols_from_value_and_function_definitions() -> None:
    code = """
    (define x 41)
    (define (square n) (* n n))
    """
    assert extract_defined_symbols(code) == {"x", "square"}


def test_complete_merges_extra_symbols() -> None:
    reply = complete("squ", 3, extra_symbols={"square"})
    assert "square" in reply["matches"]
