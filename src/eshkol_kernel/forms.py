from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass


class FormError(ValueError):
    """Base class for Eshkol form parsing errors."""


class IncompleteInput(FormError):
    """Raised when a cell ends before its current datum is finished."""

    def __init__(self, message: str, *, reason: str = "list") -> None:
        super().__init__(message)
        self.reason = reason


class UnmatchedDelimiter(FormError):
    """Raised when a cell has an unmatched or mismatched closing delimiter."""


@dataclass(frozen=True)
class Completeness:
    status: str
    indent: str = ""


@dataclass(frozen=True)
class FormSource:
    text: str
    start: int
    end: int


class _Reader:
    """Find datum boundaries without interpreting or evaluating Eshkol syntax.

    Only semicolon line comments are trivia: native Eshkol currently rejects
    Scheme block/datum comments, so consuming those here would discard source.
    Compound/prefix nesting is bounded at 256 to avoid Python recursion failure.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        self.has_character = False
        self.has_escaped_identifier = False
        self.has_interpolation = False

    def trivia(self, index: int) -> int:
        while index < len(self.code):
            if self.code[index].isspace():
                index += 1
            elif self.code[index] == ";":
                newline = self.code.find("\n", index)
                index = len(self.code) if newline < 0 else newline + 1
            else:
                break
        return index

    def datum(self, index: int, depth: int = 0) -> int:
        if depth > 256:
            raise FormError("Input nesting exceeds the lexical reader limit.")
        index = self.trivia(index)
        if index == len(self.code):
            raise IncompleteInput("Missing datum after prefix.", reason="prefix")
        char = self.code[index]
        if char in ")]":
            raise UnmatchedDelimiter("Unmatched closing delimiter.")
        if char in "'`,":
            following = index + (2 if self.code.startswith(",@", index) else 1)
            return self.datum(following, depth + 1)
        if char in '\"|':
            self.has_escaped_identifier |= char == "|"
            cursor = index + 1
            while cursor < len(self.code):
                if self.code[cursor] == char:
                    return cursor + 1
                if char == '"' and self.code.startswith("~~{", cursor):
                    cursor += 3
                    continue
                if char == '"' and self.code.startswith("~{", cursor):
                    self.has_interpolation = True
                    cursor = self.interpolation_end(cursor + 2)
                    continue
                cursor += 2 if self.code[cursor] == "\\" else 1
            reason = "string" if char == '"' else "escaped-identifier"
            raise IncompleteInput(f"Unterminated {reason} literal.", reason=reason)
        if self.code.startswith("#\\", index):
            self.has_character = True
            cursor = index + 2
            if cursor == len(self.code):
                raise IncompleteInput("Incomplete character literal.", reason="character")
            # A delimiter is itself the character, never a structural token.
            if self.code[cursor].isspace() or self.code[cursor] in "()[];\"'`,|":
                return cursor + 1
            return self.atom_end(cursor)
        opening = index + 1 if self.code.startswith("#(", index) else index
        if self.code[opening] in "([":
            closing = ")" if self.code[opening] == "(" else "]"
            cursor = opening + 1
            while True:
                cursor = self.trivia(cursor)
                if cursor == len(self.code):
                    raise IncompleteInput("Input has unmatched opening delimiters.")
                if self.code[cursor] == closing:
                    return cursor + 1
                if self.code[cursor] in ")]":
                    raise UnmatchedDelimiter("Mismatched closing delimiter.")
                cursor = self.datum(cursor, depth + 1)
        if self.code.startswith("#;", index):
            # Preserve this unsupported native token instead of treating it as
            # a Scheme datum comment and silently dropping the following form.
            return index + 2
        return self.atom_end(index)

    def interpolation_end(self, cursor: int) -> int:
        """Mirror native readString's boundary scan and expression unescaping.

        Parentheses remain expression source, not outer-string structure. The
        native expression parser validates them after the interpolation closes.
        """
        in_string = escaped = False
        while cursor < len(self.code):
            char = self.code[cursor]
            if not in_string and char == "}":
                return cursor + 1
            cursor += 1
            if char == "\\" and cursor < len(self.code):
                char = {"n": "\n", "t": "\t", "r": "\r"}.get(self.code[cursor], self.code[cursor])
                cursor += 1
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
        raise IncompleteInput("Unterminated string interpolation.", reason="interpolation")

    def atom_end(self, index: int) -> int:
        while index < len(self.code) and not self.code[index].isspace() and self.code[index] not in "()[];\"'`,":
            index += 1
        return index

    def forms(self) -> list[FormSource]:
        result: list[FormSource] = []
        index = self.trivia(0)
        while index < len(self.code):
            end = self.datum(index)
            result.append(FormSource(self.code[index:end], index, end))
            index = self.trivia(end)
        return result


def split_top_level_forms(code: str) -> list[str]:
    return [form.text for form in split_top_level_form_sources(code)]


def split_top_level_form_sources(code: str) -> list[FormSource]:
    """Split cells into source-preserving datums for one-form native requests."""
    return _Reader(code).forms()


def check_completeness(code: str) -> Completeness:
    try:
        split_top_level_forms(code)
    except IncompleteInput:
        return Completeness(status="incomplete", indent="  ")
    except FormError:
        return Completeness(status="invalid")
    return Completeness(status="complete")


def has_incomplete_reader_token(code: str) -> bool:
    """Detect EOF inside strings, escaped identifiers or reader prefixes."""
    try:
        split_top_level_forms(code)
    except IncompleteInput as exc:
        return exc.reason in {"string", "escaped-identifier", "interpolation", "prefix"}
    except FormError:
        pass
    return False


def has_character_literal(code: str) -> bool:
    """Recognize actual character tokens, excluding text in strings/comments."""
    reader = _Reader(code)
    with suppress(FormError):
        reader.forms()
    return reader.has_character


def has_escaped_identifier(code: str) -> bool:
    """Recognize pipe-quoted identifiers, excluding strings and comments."""
    reader = _Reader(code)
    with suppress(FormError):
        reader.forms()
    return reader.has_escaped_identifier


def has_interpolation(code: str) -> bool:
    """Recognize active ~{ string interpolation, excluding escaped ~~{ text."""
    reader = _Reader(code)
    with suppress(FormError):
        reader.forms()
    return reader.has_interpolation


def form_head_symbol(code: str) -> str | None:
    """Return an exact unquoted list head; this does not validate special forms."""
    reader = _Reader(code)
    try:
        forms = reader.forms()
        if len(forms) != 1 or forms[0].text[0] not in "([":
            return None
        start = reader.trivia(forms[0].start + 1)
        if start >= forms[0].end - 1 or code[start] in "()[]\"'`,|" or code.startswith("#\\", start):
            return None
        end = reader.atom_end(start)
        return code[start:end] or None
    except FormError:
        return None


def is_definition_form(code: str) -> bool:
    """Identify exactly a top-level define, including function definitions."""
    return form_head_symbol(code) == "define"
