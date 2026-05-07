from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

from eshkol_kernel.install import install_kernel_spec


FAKE_REPL = Path(__file__).with_name("fake_eshkol_repl.py")


def test_kernel_runs_through_jupyter_client(tmp_path: Path) -> None:
    destination = install_kernel_spec(
        prefix=str(tmp_path),
        name="eshkol-integration",
        display_name="Eshkol Integration",
    )
    spec_manager = KernelSpecManager(kernel_dirs=[str(Path(destination).parent)])
    manager = KernelManager(kernel_name="eshkol-integration", kernel_spec_manager=spec_manager)
    env = os.environ.copy()
    env["ESHKOL_REPL"] = sys.executable
    env["ESHKOL_KERNEL_REPL_ARGS"] = str(FAKE_REPL)
    env["ESHKOL_KERNEL_LOAD_STDLIB"] = "0"

    manager.start_kernel(env=env)
    client = manager.client()
    try:
        client.start_channels()
        client.wait_for_ready(timeout=10)
        msg_id = client.execute("(+ 1 2 3)")
        outputs = collect_outputs(client, msg_id)
        reply = client.get_shell_msg(timeout=10)
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)

    assert reply["content"]["status"] == "ok"
    assert outputs == [("stdout", "6\n")]


def collect_outputs(client, msg_id: str) -> list[tuple[str, str]]:
    outputs: list[tuple[str, str]] = []
    deadline = time.time() + 10
    while time.time() < deadline:
        message = client.get_iopub_msg(timeout=10)
        if message["parent_header"].get("msg_id") != msg_id:
            continue
        if message["msg_type"] == "stream":
            outputs.append((message["content"]["name"], message["content"]["text"]))
        if message["msg_type"] == "status" and message["content"]["execution_state"] == "idle":
            return outputs
    raise TimeoutError("Kernel did not become idle after execute_request.")
