from __future__ import annotations

from dataclasses import dataclass


class FormError(ValueError):
    """Base class for Eshkol form parsing errors."""


class IncompleteInput(FormError):
    """Raised when a cell has unmatched opening delimiters."""


class UnmatchedDelimiter(FormError):
    """Raised when a cell has an unmatched closing delimiter."""


@dataclass(frozen=True)
class Completeness:
    status: str
    indent: str = ""


def split_top_level_forms(code: str) -> list[str]:
    """Split a notebook cell into top-level Eshkol forms.

    The native REPL parses one form per evaluation. Notebook users naturally
    put several definitions and one final expression in a single cell, so the
    wrapper sends them one at a time while preserving REPL state.
    """

    forms: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    in_comment = False
    escaped = False
    atom_mode = False

    for index, char in enumerate(code):
        if start is None and in_comment:
            if char == "\n":
                in_comment = False
            continue

        if start is None:
            if char.isspace():
                continue
            if char == ";":
                in_comment = True
                continue
            if char in ")]":
                raise UnmatchedDelimiter("Unmatched closing delimiter.")
            start = index
            atom_mode = char not in "(["

        if in_comment:
            if char == "\n":
                in_comment = False
                if atom_mode and start is not None:
                    _append_form(forms, code[start:index])
                    start = None
                    atom_mode = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == ";":
            if atom_mode and start is not None:
                _append_form(forms, code[start:index])
                start = None
                atom_mode = False
            in_comment = True
            continue

        if char == '"':
            in_string = True
            continue

        if atom_mode:
            if char.isspace():
                _append_form(forms, code[start:index])
                start = None
                atom_mode = False
            continue

        if char in "([":
            depth += 1
            continue

        if char in ")]":
            depth -= 1
            if depth < 0:
                raise UnmatchedDelimiter("Unmatched closing delimiter.")
            if depth == 0 and start is not None:
                _append_form(forms, code[start : index + 1])
                start = None
            continue

    if in_string:
        raise IncompleteInput("Unterminated string literal.")
    if depth > 0:
        raise IncompleteInput("Input has unmatched opening delimiters.")
    if depth < 0:
        raise UnmatchedDelimiter("Unmatched closing delimiter.")
    if start is not None:
        _append_form(forms, code[start:])

    return forms


def check_completeness(code: str) -> Completeness:
    try:
        split_top_level_forms(code)
    except IncompleteInput:
        return Completeness(status="incomplete", indent="  ")
    except UnmatchedDelimiter:
        return Completeness(status="invalid")
    return Completeness(status="complete")


def _append_form(forms: list[str], raw: str) -> None:
    form = raw.strip()
    if form:
        forms.append(form)
