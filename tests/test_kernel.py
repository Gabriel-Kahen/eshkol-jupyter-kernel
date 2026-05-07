from __future__ import annotations

from dataclasses import dataclass

from eshkol_kernel.kernel import EshkolKernel
from eshkol_kernel.session import ExecutionResult


@dataclass
class DummySession:
    result: ExecutionResult
    closed: bool = False
    interrupted: bool = False

    def execute(self, code: str) -> ExecutionResult:
        self.code = code
        return self.result

    def close(self) -> None:
        self.closed = True

    def interrupt(self) -> None:
        self.interrupted = True


def test_do_execute_ok_silent() -> None:
    session = DummySession(ExecutionResult(stdout="6\n"))
    kernel = EshkolKernel(session_factory=lambda: session)  # type: ignore[arg-type]
    reply = kernel.do_execute("(+ 1 2 3)", silent=True)
    assert reply["status"] == "ok"
    assert session.code == "(+ 1 2 3)"


def test_do_execute_error_silent() -> None:
    session = DummySession(ExecutionResult(stderr="Error: bad\n", ok=False))
    kernel = EshkolKernel(session_factory=lambda: session)  # type: ignore[arg-type]
    reply = kernel.do_execute("(bad)", silent=True)
    assert reply["status"] == "error"
    assert reply["ename"] == "EshkolError"


def test_completion() -> None:
    kernel = EshkolKernel(session_factory=lambda: DummySession(ExecutionResult()))  # type: ignore[arg-type]
    reply = kernel.do_complete("(def", 4)
    assert "define" in reply["matches"]


def test_is_complete() -> None:
    kernel = EshkolKernel(session_factory=lambda: DummySession(ExecutionResult()))  # type: ignore[arg-type]
    assert kernel.do_is_complete("(define x 1)")["status"] == "complete"
    assert kernel.do_is_complete("(define x")["status"] == "incomplete"


def test_shutdown_closes_session() -> None:
    session = DummySession(ExecutionResult())
    kernel = EshkolKernel(session_factory=lambda: session)  # type: ignore[arg-type]
    _ = kernel.eshkol_session
    reply = kernel.do_shutdown(False)
    assert reply == {"restart": False}
    assert session.closed
