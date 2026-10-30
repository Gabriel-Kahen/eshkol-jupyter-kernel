"""Correlated Jupyter exchanges for compatibility tests against explicit runtimes."""
from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from queue import Empty
from shutil import which
from typing import Any

from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

from eshkol_kernel.install import install_kernel_spec


def collect_exchange(client: Any, msg_id: str, *, timeout: float = 30) -> dict[str, Any]:
    """Wait for both the matching execute reply and matching IOPub idle.

    Keep full messages, including execute_result, status, and display metadata.
    Poll both channels so a missing shell reply cannot hide useful output.
    """
    deadline = time.monotonic() + timeout
    reply = None
    messages: list[dict[str, Any]] = []
    idle = False
    while reply is None or not idle:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            missing = []
            if reply is None:
                missing.append("shell reply")
            if not idle:
                missing.append("IOPub idle")
            raise TimeoutError(f"Request {msg_id} timed out waiting for {' and '.join(missing)}")
        if reply is None:
            try:
                candidate = client.get_shell_msg(timeout=min(0.05, remaining))
            except Empty:
                pass
            else:
                if candidate.get("parent_header", {}).get("msg_id") == msg_id:
                    reply = candidate
        if not idle:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                continue
            try:
                message = client.get_iopub_msg(timeout=min(0.05, remaining))
            except Empty:
                continue
            if message.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            messages.append(message)
            idle = message.get("msg_type") == "status" and message["content"].get("execution_state") == "idle"
    return {"reply": reply, "messages": messages}


def collect_shell_reply(client: Any, msg_id: str, *, timeout: float = 30) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Request {msg_id} timed out waiting for shell reply")
        try:
            reply = client.get_shell_msg(timeout=min(0.05, remaining))
        except Empty:
            continue
        if reply.get("parent_header", {}).get("msg_id") == msg_id:
            return reply


class KernelHarness:
    def __init__(self, manager: Any, client: Any, env: dict[str, str], kernel_name: str, timeout: float) -> None:
        self.manager = manager
        self.client = client
        self.env = env
        self.kernel_name = kernel_name
        self.timeout = timeout

    def execute(self, code: str, **kwargs: Any) -> dict[str, Any]:
        return collect_exchange(self.client, self.client.execute(code, **kwargs), timeout=self.timeout)

    def request(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return collect_shell_reply(self.client, getattr(self.client, method)(*args, **kwargs), timeout=self.timeout)

    def interrupt(self) -> None:
        self.manager.interrupt_kernel()

    def execute_notebook(self, notebook: Any, **kwargs: Any) -> Any:
        from nbclient import NotebookClient

        options = {"timeout": int(self.timeout), "kernel_name": self.kernel_name, **kwargs}
        return NotebookClient(notebook, km=self.manager, **options).execute(env=self.env)


def runtime_environment(executable: str | Path | None, env: Mapping[str, str] | None = None) -> dict[str, str]:
    configured = str(executable or os.environ.get("ESHKOL_REAL_REPL", ""))
    if not configured:
        raise ValueError("Provide a runtime executable or set ESHKOL_REAL_REPL; no fake runtime is selected implicitly")
    resolved = which(configured)
    if resolved is None:
        raise FileNotFoundError(f"Runtime executable is missing or not executable: {configured}")
    isolated = {key: value for key, value in os.environ.items() if not key.startswith("ESHKOL_KERNEL_")}
    isolated.update({"ESHKOL_REPL": str(Path(resolved).resolve()), "ESHKOL_KERNEL_REPL_ARGS": ""})
    source = str(Path(__file__).resolve().parents[1] / "src")
    isolated["PYTHONPATH"] = os.pathsep.join(filter(None, [source, isolated.get("PYTHONPATH", "")]))
    isolated.update(env or {})
    return isolated


@contextmanager
def running_kernel(
    tmp_path: Path,
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    timeout: float = 30,
) -> Iterator[KernelHarness]:
    isolated_env = runtime_environment(executable, env)
    kernel_name = f"eshkol-compat-{uuid.uuid4().hex}"
    destination = install_kernel_spec(prefix=str(tmp_path), name=kernel_name, display_name="Eshkol Compatibility")
    spec_manager = KernelSpecManager(kernel_dirs=[str(Path(destination).parent)])
    manager = KernelManager(kernel_name=kernel_name, kernel_spec_manager=spec_manager)
    client = None
    try:
        manager.start_kernel(env=isolated_env)
        client = manager.client()
        client.start_channels()
        client.wait_for_ready(timeout=timeout)
        yield KernelHarness(manager, client, isolated_env, kernel_name, timeout)
    finally:
        if client is not None:
            client.stop_channels()
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
