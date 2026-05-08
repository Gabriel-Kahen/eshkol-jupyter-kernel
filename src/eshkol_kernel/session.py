from __future__ import annotations

import json
import os
import re
import shlex
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from shutil import which
from typing import Any

from .display import parse_display_payload
from .forms import FormError, split_top_level_forms

try:
    import pexpect
except ImportError:  # pragma: no cover - exercised on unsupported platforms.
    pexpect = None  # type: ignore[assignment]


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PROMPT_RE = re.compile(r"(?m)^\s*(?:eshkol|\[\d+,\d+\])>\s*")
TRAILING_PROMPT_RE = re.compile(r"(?:eshkol|\[\d+,\d+\])>\s*$")
ERROR_RE = re.compile(
    r"(?im)(^|\n)\s*(?:error|exception|syntax[- ]?error|runtime[- ]?error|type[- ]?error)\s*:.*"
)
CLASSIFIED_ERROR_PATTERNS = [
    (re.compile(r"(?im)(^|\n)\s*syntax[- ]?error\s*:?\s*.*"), "EshkolSyntaxError"),
    (re.compile(r"(?im)(^|\n)\s*runtime[- ]?error\s*:?\s*.*"), "EshkolRuntimeError"),
    (re.compile(r"(?im)(^|\n)\s*type[- ]?error\s*:?\s*.*"), "EshkolTypeError"),
    (re.compile(r"(?im)(^|\n)\s*(?:divide[- ]?by[- ]?zero|division by zero)\b.*"), "EshkolZeroDivisionError"),
    (re.compile(r"(?im)(^|\n)\s*exception\s*:?\s*.*"), "EshkolException"),
    (ERROR_RE, "EshkolError"),
]


class EshkolSessionError(RuntimeError):
    """Raised when the Eshkol REPL session cannot be used."""


@dataclass
class DisplayData:
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    transient: dict[str, Any] | None = None


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    ok: bool = True
    error_name: str = "EshkolError"
    display_data: list[DisplayData] = field(default_factory=list)
    output_events: list[OutputEvent] = field(default_factory=list)


@dataclass
class OutputEvent:
    kind: str
    text: str = ""
    display_data: DisplayData | None = None


class EshkolReplSession:
    """Stateful PTY-backed wrapper around `eshkol-repl`."""

    PRIMARY_PROMPT_PATTERN = r"eshkol(?:\x1b\[[0-9;?]*[ -/]*[@-~])*>\s*"

    def __init__(
        self,
        executable: str = "eshkol-repl",
        argv: Sequence[str] | None = None,
        *,
        load_stdlib: bool = True,
        timeout: float = 30.0,
        start_timeout: float = 10.0,
        encoding: str = "utf-8",
    ) -> None:
        self.executable = executable
        self.argv = list(argv or [])
        self.load_stdlib = load_stdlib
        self.timeout = timeout
        self.start_timeout = start_timeout
        self.encoding = encoding
        self._child = None

    @classmethod
    def from_env(cls) -> EshkolReplSession:
        executable = os.environ.get("ESHKOL_REPL", "eshkol-repl")
        argv = shlex.split(os.environ.get("ESHKOL_KERNEL_REPL_ARGS", ""))
        load_stdlib = os.environ.get("ESHKOL_KERNEL_LOAD_STDLIB", "1").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        timeout = float(os.environ.get("ESHKOL_KERNEL_TIMEOUT", "30"))
        start_timeout = float(os.environ.get("ESHKOL_KERNEL_START_TIMEOUT", "10"))
        return cls(
            executable=executable,
            argv=argv,
            load_stdlib=load_stdlib,
            timeout=timeout,
            start_timeout=start_timeout,
        )

    @property
    def is_running(self) -> bool:
        return self._child is not None and self._child.isalive()

    def start(self) -> None:
        if self.is_running:
            return
        if pexpect is None:
            raise EshkolSessionError("pexpect is required to run eshkol-repl through a pseudo-terminal.")
        if sys.platform.startswith("win"):
            raise EshkolSessionError("The PTY-backed Eshkol kernel currently supports macOS and Linux.")

        command = self._resolve_executable()
        args = list(self.argv)
        if self.load_stdlib and "--stdlib" not in args and "-s" not in args:
            args.append("--stdlib")

        try:
            child = pexpect.spawn(
                command,
                args=args,
                encoding=self.encoding,
                timeout=self.timeout,
                echo=False,
            )
            child.setecho(False)
            child.expect(self.PRIMARY_PROMPT_PATTERN, timeout=self.start_timeout)
        except Exception as exc:  # noqa: BLE001 - normalize pexpect startup failures.
            raise EshkolSessionError(f"Failed to start Eshkol REPL: {exc}") from exc

        self._child = child

    def execute(self, code: str) -> ExecutionResult:
        try:
            forms = split_top_level_forms(code)
        except FormError as exc:
            return ExecutionResult(stderr=str(exc), ok=False, error_name=exc.__class__.__name__)

        if not forms:
            return ExecutionResult()

        self.start()
        output_parts: list[str] = []
        for form in forms:
            output_parts.append(self._execute_form(form))

        stdout = "\n".join(part for part in output_parts if part).strip()
        text, display_data, output_events = extract_display_data(stdout)
        error_name = classify_error(text)
        if error_name:
            return ExecutionResult(
                stderr=f"{text}\n" if text else "",
                ok=False,
                error_name=error_name,
                display_data=display_data,
                output_events=output_events,
            )
        return ExecutionResult(
            stdout=f"{text}\n" if text else "",
            display_data=display_data,
            output_events=output_events,
        )

    def interrupt(self) -> None:
        if self.is_running:
            self._child.sendcontrol("c")

    def reset(self) -> None:
        self.close()
        self.start()

    def close(self) -> None:
        child = self._child
        self._child = None
        if child is None:
            return
        if child.isalive():
            child.sendline(":quit")
            try:
                child.expect(pexpect.EOF, timeout=2)
            except Exception:
                child.terminate(force=True)

    def _execute_form(self, form: str) -> str:
        child = self._require_child()
        sentinel = f"__ESHKOL_JUPYTER_DONE_{uuid.uuid4().hex}__"
        sentinel_expr = sentinel_expression(sentinel)
        payload = f"{form.rstrip()}\n{sentinel_expr}\n"

        try:
            child.send(payload)
            child.expect(re.escape(sentinel), timeout=self.timeout)
            raw_output = child.before
            child.expect(self.PRIMARY_PROMPT_PATTERN, timeout=self.timeout)
        except pexpect.TIMEOUT as exc:
            self.close()
            raise EshkolSessionError(f"Eshkol execution timed out after {self.timeout:g} seconds.") from exc
        except pexpect.EOF as exc:
            raise EshkolSessionError("Eshkol REPL exited unexpectedly.") from exc

        return remove_echoed_input(clean_repl_output(raw_output), [form, sentinel_expr])

    def _require_child(self):
        if self._child is None:
            raise EshkolSessionError("Eshkol REPL session is not started.")
        return self._child

    def _resolve_executable(self) -> str:
        if os.path.sep in self.executable:
            if not os.path.exists(self.executable):
                raise EshkolSessionError(f"Eshkol REPL not found: {self.executable}")
            return self.executable
        resolved = which(self.executable)
        if not resolved:
            raise EshkolSessionError(
                f"Could not find {self.executable!r}. Install Eshkol or set ESHKOL_REPL=/path/to/eshkol-repl."
            )
        return resolved


def clean_repl_output(raw: str) -> str:
    text = ANSI_RE.sub("", raw).replace("\r", "")
    text = PROMPT_RE.sub("", text)
    text = TRAILING_PROMPT_RE.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def sentinel_expression(sentinel: str) -> str:
    midpoint = max(1, len(sentinel) // 2)
    first = sentinel[:midpoint]
    second = sentinel[midpoint:]
    return f'(begin (display "{first}") (display "{second}"))'


def remove_echoed_input(output: str, sent_forms: Sequence[str]) -> str:
    lines = output.splitlines()
    echoes: list[str] = []
    for form in sent_forms:
        echoes.extend(line.strip() for line in form.splitlines() if line.strip())

    for echo in echoes:
        for index, line in enumerate(lines):
            if line.strip() == echo:
                del lines[index]
                break

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def classify_error(text: str) -> str | None:
    for pattern, error_name in CLASSIFIED_ERROR_PATTERNS:
        if pattern.search(text):
            return error_name
    return None


def extract_display_data(output: str) -> tuple[str, list[DisplayData], list[OutputEvent]]:
    text_lines: list[str] = []
    display_data: list[DisplayData] = []
    output_events: list[OutputEvent] = []
    pending_text: list[str] = []

    for line in output.splitlines():
        parsed = parse_display_data(line)
        if parsed is None:
            text_lines.append(line)
            pending_text.append(line)
        else:
            if pending_text:
                output_events.append(OutputEvent(kind="stdout", text="\n".join(pending_text).strip() + "\n"))
                pending_text = []
            display_data.append(parsed)
            output_events.append(OutputEvent(kind="display_data", display_data=parsed))

    if pending_text:
        output_events.append(OutputEvent(kind="stdout", text="\n".join(pending_text).strip() + "\n"))

    return "\n".join(text_lines).strip(), display_data, output_events


def parse_display_data(line: str) -> DisplayData | None:
    stripped = line.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    parsed = parse_display_payload(payload)
    if parsed is None:
        return None
    data, metadata, transient = parsed
    return DisplayData(data=data, metadata=metadata, transient=transient)
