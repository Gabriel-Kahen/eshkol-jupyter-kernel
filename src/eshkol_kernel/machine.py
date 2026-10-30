"""Small, strict EREPL v1 pipe transport; no compiler or Jupyter dependencies."""

from __future__ import annotations

import itertools
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import suppress
from typing import Any

from .errors import EshkolSessionError


class MachineClient:
    def __init__(self, command: list[str], *, encoding: str, start_timeout: float) -> None:
        self.ready_info: dict[str, Any] = {}
        self._frames: queue.Queue = queue.Queue()
        self._outgoing: queue.Queue = queue.Queue()
        self._startup_tail: deque[str] = deque(maxlen=64)
        self._diagnostics: list[str] = []
        self._diagnostic_lock = threading.Lock()
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._threads: list[threading.Thread] = []
        self._proc: subprocess.Popen | None = None
        self._encoding = encoding
        options: dict[str, Any] = {}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True
        try:
            # Unbuffered handles make closing independent of a blocked reader/writer's Python lock.
            self._proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                **options,
            )
            for worker in (self._drain_stdout, self._read_stderr, self._write_stdin):
                thread = threading.Thread(target=worker, daemon=True)
                self._threads.append(thread)
                thread.start()
            ready = self._receive(start_timeout)
            if (
                ready.get("type") != "ready"
                or type(ready.get("protocol_version")) is not int
                or ready["protocol_version"] != 1
            ):
                raise EshkolSessionError("Runtime does not speak supported EREPL protocol version 1.")
            if (
                type(ready.get("pid")) is not int
                or ready["pid"] <= 0
                or not isinstance(ready.get("eshkol_version"), str)
            ):
                raise EshkolSessionError("Invalid EREPL ready metadata.")
            self.ready_info = ready
        except BaseException as exc:
            self.close()
            if isinstance(exc, (OSError, EshkolSessionError)):
                raise EshkolSessionError(
                    f"EREPL v1 startup failed: {exc} Upgrade the runtime or explicitly set "
                    "ESHKOL_KERNEL_PROTOCOL=legacy for the older PTY bridge."
                ) from exc
            raise

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _drain_stdout(self) -> None:
        # Eval frames own stdout; raw stdout is a duplicate with no cross-pipe ordering guarantee.
        assert self._proc is not None and self._proc.stdout is not None
        pipe = self._proc.stdout
        try:
            while pipe.read(65536):
                pass
        except OSError:
            pass  # Closed during bounded process cleanup.

    def _write_stdin(self) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        pipe = self._proc.stdin
        while True:
            item = self._outgoing.get()
            if item is None:
                return
            payload, sent = item
            try:
                pending = memoryview(payload)
                while pending:
                    written = pipe.write(pending)
                    if not written:
                        raise OSError("stdin write made no progress")
                    pending = pending[written:]
                sent.put(None)
            except (OSError, ValueError) as exc:
                sent.put(EshkolSessionError(f"Eshkol REPL pipe failed: {exc}"))
                return

    def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        pipe = self._proc.stderr
        pending = b""
        try:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    if pending:
                        self._stderr_line(pending)
                    break
                lines = (pending + chunk).split(b"\n")
                pending = lines.pop()
                for line in lines:
                    self._stderr_line(line)
        except (OSError, EshkolSessionError) as exc:
            self._frames.put(EshkolSessionError(str(exc)))
        finally:
            self._frames.put(EshkolSessionError("Eshkol REPL closed its protocol pipe."))

    def _stderr_line(self, raw: bytes) -> None:
        line = raw.decode(self._encoding, errors="replace").rstrip("\r")
        if line.startswith("EREPL/"):
            if not line.startswith("EREPL/1 "):
                raise EshkolSessionError("Unsupported EREPL frame version.")
            try:
                frame = json.loads(line[8:])
            except ValueError as exc:
                raise EshkolSessionError("Malformed EREPL JSON frame.") from exc
            if not isinstance(frame, dict):
                raise EshkolSessionError("EREPL frame must be an object.")
            self._frames.put(frame)
        elif line not in {"EREPL READY", "EREPL DONE", "EREPL FAIL"}:
            with self._diagnostic_lock:
                if self.ready_info:
                    self._diagnostics.append(line + "\n")
                else:
                    self._startup_tail.append(line[-4096:] + "\n")

    def _receive(self, timeout: float) -> dict[str, Any]:
        try:
            frame = self._frames.get(timeout=max(0, timeout))
        except queue.Empty as exc:
            raise EshkolSessionError(f"EREPL response timed out after {timeout:g} seconds.") from exc
        if isinstance(frame, EshkolSessionError):
            with self._diagnostic_lock:
                diagnostics = "".join([*self._startup_tail, *self._diagnostics]).strip()
            raise EshkolSessionError(str(frame) + " " + diagnostics)
        return frame

    def request(self, op: str, *, timeout: float, **fields: str) -> dict[str, Any]:
        with self._lock:
            if not self.is_running:
                raise EshkolSessionError("Eshkol REPL exited; start a new session before continuing.")
            req_id = str(next(self._ids))
            try:
                deadline = time.monotonic() + timeout
                payload = json.dumps({"id": req_id, "op": op, **fields}, ensure_ascii=True) + "\n"
                sent: queue.Queue = queue.Queue(maxsize=1)
                self._outgoing.put((payload.encode(self._encoding), sent))
                try:
                    send_error = sent.get(timeout=max(0, deadline - time.monotonic()))
                except queue.Empty as exc:
                    raise EshkolSessionError(f"EREPL request write timed out after {timeout:g} seconds.") from exc
                if send_error is not None:
                    raise send_error
                try:
                    frame = self._receive(deadline - time.monotonic())
                except KeyboardInterrupt:
                    # Signal-mode Jupyter interrupts arrive in Python; forward to the isolated child.
                    self.interrupt()
                    frame = self._receive(timeout)
                expected = {"eval": "result", "complete": "completion"}.get(op, op)
                if frame.get("id") != req_id or frame.get("type") != expected:
                    raise EshkolSessionError(f"Unexpected EREPL response to {op!r}: {frame!r}")
                return frame
            except BaseException:
                self.close()
                raise

    def interrupt(self) -> None:
        if self.is_running and self.ready_info:
            with suppress(ProcessLookupError):
                os.kill(self.ready_info["pid"], signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGINT)

    def diagnostics(self) -> str:
        with self._diagnostic_lock:
            text = "".join(self._diagnostics)
            self._diagnostics.clear()
        return text

    def _signal_owned_processes(self, sig: int) -> None:
        assert self._proc is not None
        try:
            if sys.platform == "win32":
                if self.is_running:
                    self._proc.send_signal(sig)
            else:
                os.killpg(self._proc.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin may report EPERM for an already-dead process group. Keep
            # signaling groups with surviving descendants, but never mask the
            # original protocol error after the owned child has exited.
            if self.is_running:
                try:
                    self._proc.send_signal(sig)
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    raise EshkolSessionError("Cannot signal the owned Eshkol REPL process.") from exc

    def close(self, *, graceful: bool = False) -> None:
        proc = self._proc
        if proc is None:
            return
        if graceful and self.is_running:
            try:
                frame = self.request("shutdown", timeout=2)
                if frame.get("ok") is not True:
                    raise EshkolSessionError("EREPL shutdown failed.")
                proc.wait(timeout=2)
            except (EshkolSessionError, subprocess.TimeoutExpired):
                pass
        # request() may already have closed on failure.
        if self._proc is None:
            return
        self._signal_owned_processes(signal.SIGTERM)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        if sys.platform != "win32":
            self._signal_owned_processes(signal.SIGKILL)  # Descendants may still own inherited pipe handles.
        self._outgoing.put(None)
        for thread in self._threads:
            thread.join(timeout=0.5)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()
        self._proc = None
