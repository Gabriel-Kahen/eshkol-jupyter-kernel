from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ipykernel.kernelbase import Kernel

from . import __version__
from .completion import complete, extract_defined_symbols, inspect_symbol, token_at_cursor
from .forms import check_completeness
from .session import DisplayData, EshkolReplSession, EshkolSessionError, ExecutionResult

SessionFactory = Callable[[], EshkolReplSession]


class EshkolKernel(Kernel):
    implementation = "eshkol_kernel"
    implementation_version = __version__
    language = "eshkol"
    language_version = "unknown"
    language_info = {
        "name": "eshkol",
        "mimetype": "text/x-eshkol",
        "file_extension": ".esk",
        "codemirror_mode": "scheme",
        "pygments_lexer": "eshkol",
    }
    banner = "Eshkol kernel backed by eshkol-repl"
    help_links = [
        {
            "text": "Eshkol",
            "url": "https://github.com/tsotchke/eshkol",
        },
        {
            "text": "Jupyter kernels",
            "url": "https://jupyter-client.readthedocs.io/en/stable/kernels.html",
        },
    ]

    def __init__(self, *args: Any, session_factory: SessionFactory | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session_factory = session_factory or EshkolReplSession.from_env
        self._eshkol_session: EshkolReplSession | None = None
        self._user_symbols: set[str] = set()

    @property
    def eshkol_session(self) -> EshkolReplSession:
        if self._eshkol_session is None:
            self._eshkol_session = self._session_factory()
        return self._eshkol_session

    def do_execute(
        self,
        code: str,
        silent: bool,
        store_history: bool = True,
        user_expressions: dict[str, Any] | None = None,
        allow_stdin: bool = False,
    ) -> dict[str, Any]:
        del store_history, allow_stdin

        try:
            result = self.eshkol_session.execute(code)
        except EshkolSessionError as exc:
            result = ExecutionResult(stderr=f"{exc}\n", ok=False, error_name="EshkolSessionError")

        if not silent:
            self._publish_result(result)

        if result.ok:
            self._user_symbols.update(extract_defined_symbols(code))
            return {
                "status": "ok",
                "execution_count": self.execution_count,
                "payload": [],
                "user_expressions": user_expressions or {},
            }

        traceback = (result.stderr or result.stdout or "Eshkol execution failed.").splitlines()
        return {
            "status": "error",
            "execution_count": self.execution_count,
            "ename": result.error_name,
            "evalue": traceback[-1] if traceback else result.error_name,
            "traceback": traceback,
        }

    @property
    def kernel_info(self) -> dict[str, Any]:
        info = super().kernel_info
        session = self.eshkol_session
        if getattr(session, "supports_machine_protocol", False):
            try:
                ready = session.ready_info
                info["language_info"] = {**info["language_info"], "version": ready["eshkol_version"]}
                info["banner"] = f"Eshkol {ready['eshkol_version']} (EREPL v1)"
            except EshkolSessionError as exc:
                info["banner"] = f"Eshkol runtime unavailable: {exc}"
        return info

    def do_complete(self, code: str, cursor_pos: int) -> dict[str, Any]:
        session = self.eshkol_session
        if not getattr(session, "supports_machine_protocol", False):
            return complete(code, cursor_pos, extra_symbols=self._user_symbols)
        prefix, start, end = token_at_cursor(code, cursor_pos)
        try:
            matches = session.complete(prefix)
        except EshkolSessionError as exc:
            return {"status": "error", "ename": "EshkolSessionError", "evalue": str(exc), "traceback": []}
        return {"matches": matches, "cursor_start": start, "cursor_end": end, "metadata": {}, "status": "ok"}

    def do_inspect(self, code: str, cursor_pos: int, detail_level: int = 0) -> dict[str, Any]:
        del detail_level
        token, _, _ = token_at_cursor(code, cursor_pos)
        text = inspect_symbol(token)
        if not text:
            return {"status": "ok", "data": {}, "metadata": {}, "found": False}
        return {
            "status": "ok",
            "data": {"text/plain": text},
            "metadata": {},
            "found": True,
        }

    def do_is_complete(self, code: str) -> dict[str, str]:
        session = self.eshkol_session
        if getattr(session, "supports_machine_protocol", False):
            try:
                status = session.is_complete(code)
            except EshkolSessionError:
                return {"status": "unknown"}
            return {"status": status, **({"indent": "  "} if status == "incomplete" else {})}
        completeness = check_completeness(code)
        reply = {"status": completeness.status}
        if completeness.indent:
            reply["indent"] = completeness.indent
        return reply

    def do_shutdown(self, restart: bool) -> dict[str, bool]:
        if self._eshkol_session is not None:
            self._eshkol_session.close()
            self._eshkol_session = None
        self._user_symbols.clear()
        return {"restart": restart}

    def do_interrupt(self, interrupt: bool = True) -> dict[str, str]:
        if interrupt and self._eshkol_session is not None:
            self._eshkol_session.interrupt()
        return {"status": "ok"}

    def _publish_result(self, result: ExecutionResult) -> None:
        if result.output_events:
            for event in result.output_events:
                if event.kind == "display_data" and event.display_data is not None:
                    self._publish_display_data(event.display_data)
                elif event.kind in {"stdout", "stderr"} and event.text:
                    self._publish_stream(event.kind, event.text)
                elif event.kind == "execute_result":
                    self.send_response(
                        self.iopub_socket,
                        "execute_result",
                        {
                            "execution_count": self.execution_count,
                            "data": {"text/plain": event.text},
                            "metadata": {"eshkol": {"value_type": event.value_type}},
                        },
                    )
        elif result.stdout:
            self.send_response(
                self.iopub_socket,
                "stream",
                {"name": "stdout", "text": result.stdout},
            )
        if result.stderr and not any(event.kind == "stderr" for event in result.output_events):
            self.send_response(
                self.iopub_socket,
                "stream",
                {"name": "stderr", "text": result.stderr},
            )
        if not result.ok:
            text = result.stderr or result.stdout or "Eshkol execution failed."
            traceback = text.splitlines()
            self.send_response(
                self.iopub_socket,
                "error",
                {
                    "ename": result.error_name,
                    "evalue": traceback[-1] if traceback else text.strip(),
                    "traceback": traceback,
                },
            )

    def _publish_display_data(self, display: DisplayData) -> None:
        content: dict[str, Any] = {
            "data": display.data,
            "metadata": display.metadata,
        }
        if display.transient:
            content["transient"] = display.transient
        self.send_response(self.iopub_socket, "display_data", content)

    def _publish_stream(self, name: str, text: str) -> None:
        self.send_response(
            self.iopub_socket,
            "stream",
            {"name": name, "text": text},
        )
