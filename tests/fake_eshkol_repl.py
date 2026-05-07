#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time


def main() -> int:
    definitions: dict[str, str] = {}
    print("Fake Eshkol REPL")
    write_prompt()
    buffer: list[str] = []

    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if line in {":quit", ":q", "quit", "exit", "(exit)"}:
            print("Goodbye!")
            return 0

        buffer.append(line)
        source = "\n".join(buffer)
        if paren_depth(source) > 0:
            write_continuation_prompt(len(buffer), paren_depth(source))
            continue
        if paren_depth(source) < 0:
            print("Error: Unmatched closing parenthesis")
            buffer.clear()
            write_prompt()
            continue

        evaluate(source.strip(), definitions)
        buffer.clear()
        write_prompt()

    return 0


def evaluate(source: str, definitions: dict[str, str]) -> None:
    if not source:
        return
    begin_display_match = re.fullmatch(
        r'\(begin\s+\(display\s+"(.*)"\)\s+\(display\s+"(.*)"\)\)',
        source,
        flags=re.S,
    )
    if begin_display_match:
        sys.stdout.write(begin_display_match.group(1) + begin_display_match.group(2))
        sys.stdout.flush()
        return
    display_match = re.fullmatch(r'\(display\s+"(.*)"\)', source, flags=re.S)
    if display_match:
        sys.stdout.write(display_match.group(1))
        sys.stdout.flush()
        return
    define_match = re.fullmatch(r"\(define\s+([^\s()]+)\s+(.+)\)", source, flags=re.S)
    if define_match:
        definitions[define_match.group(1)] = define_match.group(2)
        return
    add_match = re.fullmatch(r"\(\+\s+(.+)\)", source, flags=re.S)
    if add_match:
        values = [resolve_number(part, definitions) for part in add_match.group(1).split()]
        if all(value is not None for value in values):
            print(sum(value for value in values if value is not None))
            return
    if source == "(rich-html)":
        print(
            json.dumps(
                {
                    "type": "display_data",
                    "data": {"text/plain": "hello", "text/html": "<strong>hello</strong>"},
                    "metadata": {},
                }
            )
        )
        return
    if source == "(mixed-rich)":
        print("before")
        print(
            json.dumps(
                {
                    "type": "display_data",
                    "data": {"text/plain": "middle", "text/html": "<em>middle</em>"},
                    "metadata": {},
                }
            )
        )
        print("after")
        return
    if source == "(display-prompt-text)":
        print("value: eshkol> still user text")
        print("coords: [1,2]> still user text")
        return
    if source == "(relative-error)":
        print("relative error is 0.01")
        return
    if source == "(hang)":
        time.sleep(60)
        return
    if source == "(cause-error)":
        print("Error: synthetic failure")
        return
    if source == "(syntax-problem)":
        print("syntax-error: unexpected closing delimiter")
        return
    if source == "(runtime-problem)":
        print("runtime-error: undefined variable")
        return
    if source in definitions:
        print(definitions[source])
        return
    print(f"ok: {source}")


def resolve_number(token: str, definitions: dict[str, str]) -> int | None:
    value = definitions.get(token, token)
    try:
        return int(value)
    except ValueError:
        return None


def paren_depth(source: str) -> int:
    depth = 0
    in_string = False
    escaped = False
    in_comment = False
    for char in source:
        if in_comment:
            if char == "\n":
                in_comment = False
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
            in_comment = True
            continue
        if char == '"':
            in_string = True
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return depth


def write_prompt() -> None:
    sys.stdout.write("eshkol> ")
    sys.stdout.flush()


def write_continuation_prompt(line_count: int, depth: int) -> None:
    sys.stdout.write(f"  [{line_count},{depth}]> ")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
