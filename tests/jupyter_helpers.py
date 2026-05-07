from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

from eshkol_kernel.install import install_kernel_spec

FAKE_REPL = Path(__file__).with_name("fake_eshkol_repl.py")


@contextmanager
def started_kernel(
    tmp_path: Path,
    *,
    kernel_name: str = "eshkol-test",
    eshkol_repl: str | None = None,
    repl_args: str | None = None,
    load_stdlib: bool = False,
) -> Iterator[Any]:
    destination = install_kernel_spec(
        prefix=str(tmp_path),
        name=kernel_name,
        display_name="Eshkol Test",
    )
    spec_manager = KernelSpecManager(kernel_dirs=[str(Path(destination).parent)])
    manager = KernelManager(kernel_name=kernel_name, kernel_spec_manager=spec_manager)
    env = os.environ.copy()
    env["ESHKOL_REPL"] = eshkol_repl or sys.executable
    env["ESHKOL_KERNEL_REPL_ARGS"] = repl_args if repl_args is not None else str(FAKE_REPL)
    env["ESHKOL_KERNEL_LOAD_STDLIB"] = "1" if load_stdlib else "0"

    manager.start_kernel(env=env)
    client = manager.client()
    try:
        client.start_channels()
        client.wait_for_ready(timeout=10)
        yield client
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)


def execute_and_collect(client: Any, code: str) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    msg_id = client.execute(code)
    outputs = collect_outputs(client, msg_id)
    reply = client.get_shell_msg(timeout=10)
    return reply["content"], outputs


def collect_outputs(client: Any, msg_id: str) -> list[tuple[str, Any]]:
    outputs: list[tuple[str, Any]] = []
    deadline = time.time() + 10
    while time.time() < deadline:
        message = client.get_iopub_msg(timeout=10)
        if message["parent_header"].get("msg_id") != msg_id:
            continue
        if message["msg_type"] == "stream":
            outputs.append((message["content"]["name"], message["content"]["text"]))
        elif message["msg_type"] == "display_data":
            outputs.append(("display_data", message["content"]["data"]))
        elif message["msg_type"] == "error":
            outputs.append(("error", message["content"]))
        if message["msg_type"] == "status" and message["content"]["execution_state"] == "idle":
            return outputs
    raise TimeoutError("Kernel did not become idle after execute_request.")
