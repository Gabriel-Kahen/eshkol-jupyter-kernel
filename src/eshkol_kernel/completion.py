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
        "caar",
        "cadr",
        "cdar",
        "cddr",
        "ceiling",
        "cond",
        "cons",
        "cos",
        "curl",
        "define",
        "define-macro",
        "derivative",
        "display",
        "divergence",
        "dynamic-wind",
        "else",
        "eq?",
        "equal?",
        "exp",
        "filter",
        "floor",
        "fold",
        "for-each",
        "gradient",
        "guard",
        "if",
        "integer?",
        "lambda",
        "laplacian",
        "length",
        "let",
        "let*",
        "letrec",
        "list",
        "list?",
        "log",
        "magnitude",
        "map",
        "max",
        "member",
        "memq",
        "min",
        "modulo",
        "newline",
        "not",
        "null?",
        "number?",
        "or",
        "pair?",
        "print",
        "quotient",
        "quote",
        "raise",
        "remainder",
        "require",
        "reverse",
        "round",
        "sin",
        "sqrt",
        "string?",
        "symbol?",
        "tensor",
        "truncate",
        "vector",
        "vector-ref",
        "vector-set!",
        "zero?",
        "write",
    }
)

TOKEN_RE = re.compile(r"[A-Za-z0-9_+\-*/<>=!?$%&.:^~]+$")
DEFINE_VALUE_RE = re.compile(r"\(\s*define\s+([A-Za-z0-9_+\-*/<>=!?$%&.:^~]+)")
DEFINE_FUNCTION_RE = re.compile(r"\(\s*define\s+\(\s*([A-Za-z0-9_+\-*/<>=!?$%&.:^~]+)")


def token_at_cursor(code: str, cursor_pos: int) -> tuple[str, int, int]:
    cursor_pos = max(0, min(cursor_pos, len(code)))
    prefix = code[:cursor_pos]
    match = TOKEN_RE.search(prefix)
    if not match:
        return "", cursor_pos, cursor_pos
    return match.group(0), match.start(), cursor_pos


def complete(code: str, cursor_pos: int, extra_symbols: set[str] | None = None) -> dict[str, object]:
    token, start, end = token_at_cursor(code, cursor_pos)
    symbols = sorted(set(COMMON_SYMBOLS).union(extra_symbols or set()))
    matches = [symbol for symbol in symbols if symbol.startswith(token)] if token else symbols
    return {
        "matches": matches,
        "cursor_start": start,
        "cursor_end": end,
        "metadata": {},
        "status": "ok",
    }


def extract_defined_symbols(code: str) -> set[str]:
    symbols: set[str] = set()
    symbols.update(match.group(1) for match in DEFINE_VALUE_RE.finditer(code))
    symbols.update(match.group(1) for match in DEFINE_FUNCTION_RE.finditer(code))
    return symbols


def inspect_symbol(symbol: str) -> str | None:
    docs = {
        "+": "(+ a b ...) adds numbers.",
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
