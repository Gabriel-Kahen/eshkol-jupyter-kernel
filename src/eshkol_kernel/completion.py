from __future__ import annotations

import re


COMMON_SYMBOLS = sorted(
    {
        "*",
        "+",
        "-",
        "/",
        "<",
        "<=",
        "=",
        ">",
        ">=",
        "abs",
        "and",
        "append",
        "apply",
        "begin",
        "boolean?",
        "call/cc",
        "car",
        "cdr",
        "cond",
        "cons",
        "cos",
        "curl",
        "define",
        "derivative",
        "display",
        "divergence",
        "dynamic-wind",
        "else",
        "exp",
        "filter",
        "fold",
        "for-each",
        "gradient",
        "guard",
        "if",
        "lambda",
        "laplacian",
        "length",
        "let",
        "let*",
        "letrec",
        "list",
        "list?",
        "log",
        "map",
        "max",
        "min",
        "newline",
        "not",
        "null?",
        "number?",
        "or",
        "print",
        "quote",
        "raise",
        "require",
        "sin",
        "sqrt",
        "string?",
        "symbol?",
        "tensor",
        "vector",
        "write",
    }
)

TOKEN_RE = re.compile(r"[A-Za-z0-9_+\-*/<>=!?$%&.:^~]+$")


def token_at_cursor(code: str, cursor_pos: int) -> tuple[str, int, int]:
    cursor_pos = max(0, min(cursor_pos, len(code)))
    prefix = code[:cursor_pos]
    match = TOKEN_RE.search(prefix)
    if not match:
        return "", cursor_pos, cursor_pos
    return match.group(0), match.start(), cursor_pos


def complete(code: str, cursor_pos: int) -> dict[str, object]:
    token, start, end = token_at_cursor(code, cursor_pos)
    matches = [symbol for symbol in COMMON_SYMBOLS if symbol.startswith(token)] if token else COMMON_SYMBOLS
    return {
        "matches": matches,
        "cursor_start": start,
        "cursor_end": end,
        "metadata": {},
        "status": "ok",
    }


def inspect_symbol(symbol: str) -> str | None:
    docs = {
        "define": "(define name value) or (define (name args...) body...)",
        "lambda": "(lambda (args...) body...)",
        "derivative": "(derivative f x) computes a scalar derivative.",
        "gradient": "(gradient f x y ...) computes a gradient vector.",
        "display": "(display value) writes value to output.",
        "map": "(map f list) applies f to each item.",
        "filter": "(filter predicate list) keeps items matching predicate.",
        "fold": "(fold f init list) reduces a list.",
    }
    return docs.get(symbol)
