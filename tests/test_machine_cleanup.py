"""POSIX cleanup regressions: Darwin stale-group EPERM and live-child ownership."""
from __future__ import annotations

import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from eshkol_kernel import machine
from eshkol_kernel.errors import EshkolSessionError
from eshkol_kernel.machine import MachineClient

FAKE = Path(__file__).with_name("fake_machine_repl.py")
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX owned process-group cleanup")


def client(*args: str) -> MachineClient:
    return MachineClient([sys.executable, str(FAKE), "--machine", *args], encoding="utf-8", start_timeout=3)


def test_exited_group_permission_error_preserves_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    processes: list[Any] = []
    popen = subprocess.Popen
    killpg = os.killpg

    def capture_process(*args: Any, **kwargs: Any) -> Any:
        proc = popen(*args, **kwargs)
        processes.append(proc)
        return proc

    def stale_group_permission(pid: int, sig: int) -> None:
        if processes and pid == processes[0].pid:
            processes[0].wait(timeout=3)
            raise PermissionError(errno.EPERM, "stale process group")
        killpg(pid, sig)

    monkeypatch.setattr(machine.subprocess, "Popen", capture_process)
    monkeypatch.setattr(machine.os, "killpg", stale_group_permission)
    started = time.monotonic()
    with pytest.raises(EshkolSessionError, match="startup failed.*protocol pipe.*native dependency missing"):
        client("--mode=eof")
    assert time.monotonic() - started < 3
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert all(pipe.closed for pipe in (processes[0].stdin, processes[0].stdout, processes[0].stderr))


def test_exited_group_permission_error_preserves_request_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = client()
    proc = instance._proc
    assert proc is not None
    killpg = os.killpg

    def stale_group_permission(pid: int, sig: int) -> None:
        if pid == proc.pid:
            proc.wait(timeout=3)
            raise PermissionError(errno.EPERM, "stale process group")
        killpg(pid, sig)

    with monkeypatch.context() as patched:
        patched.setattr(machine.os, "killpg", stale_group_permission)
        try:
            started = time.monotonic()
            with pytest.raises(EshkolSessionError, match="closed its protocol pipe"):
                instance.request("eval", timeout=3, code="(eof)")
            assert time.monotonic() - started < 3
            assert not instance.is_running
            assert not any(thread.is_alive() for thread in instance._threads)
        finally:
            instance.close()


def test_live_group_permission_error_still_terminates_owned_child(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = client()
    proc = instance._proc
    assert proc is not None
    killpg = os.killpg
    denied = []

    def deny_owned_group(pid: int, sig: int) -> None:
        if pid == proc.pid:
            denied.append((sig, proc.poll()))
            raise PermissionError(errno.EPERM, "owned group denied")
        killpg(pid, sig)

    try:
        with monkeypatch.context() as patched:
            patched.setattr(machine.os, "killpg", deny_owned_group)
            started = time.monotonic()
            instance.close()
        assert time.monotonic() - started < 3
        assert denied[0] == (signal.SIGTERM, None)
        assert proc.poll() is not None
        assert not instance.is_running
        assert not any(thread.is_alive() for thread in instance._threads)
        assert all(pipe.closed for pipe in (proc.stdin, proc.stdout, proc.stderr))
    finally:
        # Restore group signaling before emergency cleanup if the regression fails.
        instance.close()


def test_live_child_permission_failure_is_explicit_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = client()
    proc = instance._proc
    assert proc is not None
    killpg = os.killpg

    def deny_owned_group(pid: int, sig: int) -> None:
        if pid == proc.pid:
            raise PermissionError(errno.EPERM, "owned group denied")
        killpg(pid, sig)

    def deny_direct_signal(sig: int) -> None:
        raise PermissionError(errno.EPERM, "owned child denied")

    try:
        with monkeypatch.context() as patched:
            patched.setattr(machine.os, "killpg", deny_owned_group)
            patched.setattr(proc, "send_signal", deny_direct_signal)
            started = time.monotonic()
            with pytest.raises(EshkolSessionError, match="Cannot signal.*owned.*process"):
                instance.close()
            assert time.monotonic() - started < 3
            assert proc.poll() is None  # A denied signal must not falsely report cleanup.
    finally:
        instance.close()
    assert proc.poll() is not None


def test_cleanup_still_signals_descendants_after_leader_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = client("--mode=descendant")
    proc = instance._proc
    assert proc is not None
    # Reading a response proves the fake has spawned its pipe-inheriting child.
    assert instance.request("eval", timeout=3, code="(+ 1 2)")["ok"]
    killpg = os.killpg
    calls = []

    def record_owned_group(pid: int, sig: int) -> None:
        if pid == proc.pid:
            calls.append((sig, proc.poll()))
        killpg(pid, sig)

    try:
        with monkeypatch.context() as patched:
            patched.setattr(machine.os, "killpg", record_owned_group)
            started = time.monotonic()
            instance.close(graceful=True)
        assert time.monotonic() - started < 3
        assert calls[0][0] == signal.SIGTERM
        assert calls[0][1] is not None  # Graceful shutdown reaped the group leader first.
        assert calls[-1][0] == signal.SIGKILL
        assert proc.poll() is not None
        assert not any(thread.is_alive() for thread in instance._threads)
    finally:
        instance.close()
