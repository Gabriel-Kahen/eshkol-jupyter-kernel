from __future__ import annotations

from pygments.lexer import RegexLexer, words
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Text

from .completion import COMMON_SYMBOLS

SPECIAL_FORMS = {
    "and",
    "begin",
    "case",
    "cond",
    "define",
    "define-macro",
    "define-syntax",
    "delay",
    "do",
    "dynamic-wind",
    "else",
    "guard",
    "if",
    "lambda",
    "let",
    "let*",
    "letrec",
    "or",
    "quasiquote",
    "quote",
    "require",
    "set!",
    "syntax-rules",
    "unquote",
    "unquote-splicing",
}

BUILTINS = sorted(set(COMMON_SYMBOLS) - SPECIAL_FORMS)
SYMBOL = r"[A-Za-z0-9_+\-*/<>=!?$%&.:^~]+"


class EshkolLexer(RegexLexer):
    """Pygments lexer for Eshkol's Scheme-like syntax."""

    name = "Eshkol"
    aliases = ["eshkol"]
    filenames = ["*.esk"]
    mimetypes = ["text/x-eshkol"]

    tokens = {
        "root": [
            (r"\s+", Text.Whitespace),
            (r";.*?$", Comment.Single),
            (r'"(?:\\.|[^"\\])*"', String.Double),
            (r"#(?:t|f)\b", Keyword.Constant),
            (r"#[A-Za-z0-9_+\-*/<>=!?$%&.:^~]+", Name.Constant),
            (r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", Number.Float),
            (r"[-+]?\d+(?:[eE][-+]?\d+)", Number.Float),
            (r"[-+]?\d+", Number.Integer),
            (r"[(){}\[\]]", Punctuation),
            (r",@", Operator),
            (r"['`,]", Operator),
            (
                words(tuple(sorted(SPECIAL_FORMS)), prefix=r"(?<![^\s(){}\[\]'`,])", suffix=r"(?![^\s(){}\[\]'`,])"),
                Keyword,
            ),
            (
                words(tuple(BUILTINS), prefix=r"(?<![^\s(){}\[\]'`,])", suffix=r"(?![^\s(){}\[\]'`,])"),
                Name.Builtin,
            ),
            (SYMBOL, Name),
        ]
    }
