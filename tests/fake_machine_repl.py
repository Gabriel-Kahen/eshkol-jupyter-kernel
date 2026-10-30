#!/usr/bin/env python3
"""Deterministic EREPL v1 peer, not an Eshkol interpreter."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from contextlib import redirect_stdout

from fake_eshkol_repl import evaluate, paren_depth


def emit(frame: dict) -> None:
    print("EREPL/1 " + json.dumps(frame), file=sys.stderr, flush=True)


def error(kind: str, message: str) -> dict:
    return {
        "kind": kind,
        "message": message,
        "printed": message,
        "line": None,
        "column": None,
        "filename": None,
        "irritants": [],
    }


def main() -> None:
    assert "--machine" in sys.argv
    mode = next((x[7:] for x in sys.argv if x.startswith("--mode=")), "")
    if mode == "legacy-only":
        print("EREPL READY", file=sys.stderr, flush=True)
        time.sleep(60)
    if mode == "eof":
        print("native dependency missing", file=sys.stderr, flush=True)
        return
    if mode == "malformed-ready":
        print("EREPL/1 {broken", file=sys.stderr, flush=True)
        return
    emit(
        {
            "type": "ready",
            "protocol_version": 2 if mode == "version2" else 1,
            "pid": os.getpid(),
            "eshkol_version": "test-runtime",
        }
    )
    if mode == "stalled-input":
        time.sleep(60)
    if mode == "descendant":
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    definitions: dict[str, str] = {}
    for line in sys.stdin:
        request = json.loads(line)
        op, req_id = request["op"], request["id"]
        if op == "shutdown":
            emit({"type": op, "id": req_id, "ok": True})
            return
        if op == "complete":
            matches = sorted(x for x in {"define", "display", *definitions} if x.startswith(request["prefix"]))
            emit({"type": "completion", "id": req_id, "matches": matches})
            continue
        if op == "is_complete":
            depth = paren_depth(request["code"])
            emit(
                {
                    "type": op,
                    "id": req_id,
                    "status": "incomplete" if depth > 0 else "invalid" if depth < 0 else "complete",
                }
            )
            continue
        assert op == "eval"
        code = request["code"]
        frame = {"type": "result", "id": req_id, "ok": True, "stdout": "", "value": "", "value_type": "unspecified"}
        if code == "(hang)":
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                frame["ok"] = False
                frame["error"] = error("interrupted", "evaluation interrupted")
        elif code == "(eof)":
            return
        elif code == "(malformed)":
            print("EREPL/1 {broken", file=sys.stderr, flush=True)
            continue
        elif code == "(wrong-id)":
            frame["id"] = "wrong"
        elif code == "(bad-schema)":
            frame["stdout"] = None
        elif code in {"(cause-error)", "(syntax-problem)", "(runtime-problem)", "(new-error)", "(location-error)"}:
            kind = {"(syntax-problem)": "syntax-error", "(new-error)": "future-kind"}.get(code, "error")
            frame["ok"] = False
            frame["error"] = error(kind, "synthetic failure")
            frame["stdout"] = "before failure"
            if code == "(location-error)":
                frame["error"].update(line=1, column=3)
        elif mode == "zero-result":
            # A wire-level peer deliberately exposing a result independent of
            # source syntax, for correction and no-correction controls.
            frame.update(stdout="kept\n", value="0", value_type="integer")
        elif code == "(pipe-pressure)":
            frame["stdout"] = "x" * 1048576
        elif code == "(print-error-text)":
            frame["stdout"] = "error: successful user text\neshkol> \x1b[31m untouched  "
        elif code == "(value-and-output)":
            frame.update(stdout="hello", value="42", value_type="integer")
        elif code == "(diagnostic)":
            print("compiler warning", file=sys.stderr, flush=True)
        elif code == "(many-diagnostics)":
            for index in range(100):
                print(f"diagnostic {index}", file=sys.stderr, flush=True)
        elif code == "(external-error)":
            frame["ok"] = False
            frame["error"] = error("file-error", "external failure")
            frame["error"].update(filename="external.esk", line=7)
        elif code.startswith('"'):
            frame.update(value=code, value_type="string")
        elif code in definitions or re.fullmatch(r"\(\+\s+.+\)", code, re.S):
            output = io.StringIO()
            with redirect_stdout(output):
                evaluate(code, definitions)
            frame.update(value=output.getvalue().rstrip("\n"), value_type="integer")
        else:
            output = io.StringIO()
            with redirect_stdout(output):
                evaluate(code, definitions)
            frame["stdout"] = output.getvalue()
        # Duplicate raw bytes precede the frame to expose undrained-pipe deadlocks.
        sys.stdout.write(frame["stdout"] or "")
        sys.stdout.flush()
        print("EREPL DONE" if frame["ok"] else "EREPL FAIL", file=sys.stderr, flush=True)
        emit(frame)


if __name__ == "__main__":
    main()
