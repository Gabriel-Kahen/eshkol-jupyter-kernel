from __future__ import annotations

from pygments.lexers import find_lexer_class_for_filename, get_lexer_by_name
from pygments.token import Comment, Keyword, Name, Number, Punctuation, String

from eshkol_kernel.lexer import EshkolLexer


def token_pairs(code: str) -> list[tuple[object, str]]:
    return [(token_type, value) for token_type, value in EshkolLexer().get_tokens(code) if value.strip()]


def test_lexer_registration_by_alias() -> None:
    assert isinstance(get_lexer_by_name("eshkol"), EshkolLexer)


def test_lexer_registration_by_filename() -> None:
    assert find_lexer_class_for_filename("example.esk") is EshkolLexer


def test_lexer_highlights_core_eshkol_syntax() -> None:
    tokens = token_pairs('(define (square x) (* x x)) ; comment\n(display "done")\n42')

    assert (Keyword, "define") in tokens
    assert (Name.Builtin, "display") in tokens
    assert (String.Double, '"done"') in tokens
    assert (Number.Integer, "42") in tokens
    assert (Punctuation, "(") in tokens
    assert any(token_type in Comment for token_type, value in tokens if "comment" in value)


def test_lexer_highlights_eshkol_math_builtins() -> None:
    tokens = token_pairs("(gradient f x y) (derivative f x) (tensor 2 2)")

    assert (Name.Builtin, "gradient") in tokens
    assert (Name.Builtin, "derivative") in tokens
    assert (Name.Builtin, "tensor") in tokens
