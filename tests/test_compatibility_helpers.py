from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from queue import Empty
from typing import Any

import compatibility_helpers as helpers
import pytest


def message(kind: str, parent: str = "wanted", **content: Any) -> dict[str, Any]:
    return {"msg_type": kind, "parent_header": {"msg_id": parent}, "content": content}


class QueuedClient:
    def __init__(self, shell: list[Any], iopub: list[Any]) -> None:
        self.shell = deque(shell)
        self.iopub = deque(iopub)

    def get_shell_msg(self, timeout: float) -> Any:
        assert 0 < timeout <= 0.05
        if not self.shell:
            raise Empty
        item = self.shell.popleft()
        if item is None:
            raise Empty
        return item

    def get_iopub_msg(self, timeout: float) -> Any:
        assert 0 < timeout <= 0.05
        if not self.iopub:
            raise Empty
        return self.iopub.popleft()


@pytest.fixture
def bounded_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter(index * 0.01 for index in range(1000))
    monkeypatch.setattr(helpers.time, "monotonic", lambda: next(ticks))


def test_collect_exchange_preserves_full_order_and_matches_both_channels(bounded_clock: None) -> None:
    wanted_reply = message("execute_reply", status="ok")
    output = [
        message("status", execution_state="busy"),
        message("execute_input", code="(+ 1 2)", execution_count=1),
        message("stream", name="stdout", text="before"),
        message("display_data", data={"text/plain": "rich"}, metadata={"isolated": True}),
        message("execute_result", data={"text/plain": "3"}, execution_count=1),
        message("error", ename="ExampleError", evalue="example", traceback=[]),
        message("status", execution_state="idle"),
    ]
    client = QueuedClient(
        [message("execute_reply", parent="unrelated"), None, wanted_reply],
        [message("status", parent="unrelated", execution_state="idle"), *output],
    )
    assert helpers.collect_exchange(client, "wanted", timeout=1) == {"reply": wanted_reply, "messages": output}


@pytest.mark.parametrize(
    ("shell", "iopub", "missing"),
    [
        ([], [message("status", execution_state="idle")], "shell reply"),
        ([message("execute_reply", status="ok")], [], "IOPub idle"),
        ([], [], "shell reply and IOPub idle"),
        ([message("execute_reply", parent="other")],
         [message("status", parent="other", execution_state="idle")], "shell reply and IOPub idle"),
    ],
)
def test_collect_exchange_times_out_for_missing_components(
    bounded_clock: None, shell: list[Any], iopub: list[Any], missing: str,
) -> None:
    with pytest.raises(TimeoutError, match=f"waiting for {missing}"):
        helpers.collect_exchange(QueuedClient(shell, iopub), "wanted", timeout=0.2)


def test_shell_request_discards_unrelated_reply(bounded_clock: None) -> None:
    wanted = message("complete_reply", matches=["define"])
    client = QueuedClient([message("complete_reply", parent="other"), None, wanted], [])
    assert helpers.collect_shell_reply(client, "wanted", timeout=1) is wanted


def test_shell_request_timeout_is_bounded(bounded_clock: None) -> None:
    with pytest.raises(TimeoutError, match="shell reply"):
        helpers.collect_shell_reply(QueuedClient([], []), "wanted", timeout=0.2)


def test_environment_requires_explicit_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ESHKOL_REAL_REPL", raising=False)
    with pytest.raises(ValueError, match="Provide a runtime executable"):
        helpers.runtime_environment(None)


def test_environment_rejects_missing_runtime() -> None:
    with pytest.raises(FileNotFoundError, match="not executable"):
        helpers.runtime_environment("definitely-no-such-eshkol-runtime")


def test_environment_clears_ambient_kernel_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ESHKOL_KERNEL_REPL_ARGS", "ambient-fake.py")
    monkeypatch.setenv("ESHKOL_KERNEL_TRANSPORT", "ambient")
    monkeypatch.setenv("ESHKOL_KERNEL_TIMEOUT", "0.01")
    env = helpers.runtime_environment(sys.executable, {"ESHKOL_KERNEL_TRANSPORT": "machine"})
    assert env["ESHKOL_KERNEL_REPL_ARGS"] == ""
    assert env["ESHKOL_KERNEL_TRANSPORT"] == "machine"
    assert "ESHKOL_KERNEL_TIMEOUT" not in env
    assert env["ESHKOL_REPL"]


def test_harness_interrupt_calls_manager() -> None:
    class Manager:
        calls = 0

        def interrupt_kernel(self) -> None:
            self.calls += 1

    manager = Manager()
    helpers.KernelHarness(manager, None, {}, "test", 1).interrupt()
    assert manager.calls == 1


@pytest.mark.parametrize("stage", ["start", "ready", "body"])
def test_kernel_cleanup_on_startup_or_test_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str,
) -> None:
    class Client:
        stopped = False

        def start_channels(self) -> None:
            pass

        def stop_channels(self) -> None:
            self.stopped = True

        def wait_for_ready(self, timeout: float) -> None:
            if stage == "ready":
                raise RuntimeError("ready failed")

    class Manager:
        has_kernel = False
        shutdown = False

        def start_kernel(self, **kwargs: Any) -> None:
            self.has_kernel = True
            if stage == "start":
                raise RuntimeError("start failed")

        def client(self) -> Client:
            return client

        def shutdown_kernel(self, now: bool) -> None:
            assert now
            self.shutdown = True
            self.has_kernel = False

    client = Client()
    manager = Manager()
    monkeypatch.setattr(helpers, "KernelManager", lambda **kwargs: manager)
    monkeypatch.setattr(helpers, "install_kernel_spec", lambda **kwargs: str(tmp_path / "kernels" / "compat"))
    with pytest.raises(RuntimeError, match=f"{stage} failed"), helpers.running_kernel(tmp_path, sys.executable):
        raise RuntimeError("body failed")
    assert manager.shutdown
    assert client.stopped == (stage != "start")
