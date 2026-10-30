# EREPL v1 bridge

The development kernel uses `eshkol-repl --machine` with EREPL protocol
version 1. This migration is not part of the published `0.1.0a5` PTY release.
The bridge stays in this repository and depends on the subprocess protocol,
not compiler internals or an embedding ABI.

## Compatibility policy

The runtime must emit an `EREPL/1 ` JSON `ready` frame with
`protocol_version: 1`. Its `eshkol_version` is reported as language metadata
and used for diagnostics; it does not select behavior. Unknown additional
fields are ignored. Missing or unsupported protocol versions fail startup
with a session error. Bare `EREPL READY` is insufficient, and the kernel
never silently falls back after a handshake failure.

Use `ESHKOL_KERNEL_PROTOCOL=legacy` explicitly for an older interactive
runtime. That mode retains the PTY, prompt/sentinel handling, text-based error
classification, and local completion/completeness behavior. Legacy mode is
intended for Unix-like systems with `pexpect`; it does not provide the
machine-mode guarantees below.

`ESHKOL_KERNEL_START_TIMEOUT` defaults to 120 seconds for startup and the
handshake. `ESHKOL_KERNEL_TIMEOUT` defaults to 30 seconds **per top-level
form**, not per cell. A transport failure or execution timeout invalidates
the process; the next execution starts a fresh session and loses earlier
definitions. Machine mode always loads the standard library, as required by
upstream. `ESHKOL_KERNEL_LOAD_STDLIB` applies only in legacy mode.

## Execution and output

Cells are split into top-level forms with their source offsets retained.
Each form becomes one JSON request with string `id`, `op: "eval"`, and
`code` fields. Embedded newlines travel as JSON escapes. Requests are
serialized, and responses must match the request ID and expected type.
No sentinel Scheme expression is injected in machine mode.

The runtime's `result.stdout` is the authoritative explicit output for that
form. The runtime also replays these bytes to its raw stdout pipe. The
kernel drains that pipe continuously without republishing the duplicate;
it separately drains stderr for protocol frames and diagnostics. This
avoids relying on ordering between two independent OS pipes.

Within captured stdout, valid rich-display JSON lines become `display_data`
events in their original position; ordinary text keeps its whitespace.
The form's `value` in Scheme `write` representation becomes a separate
Jupyter `execute_result` after its stdout/display events, unless
`value_type` is `unspecified`. A proven EREPL v1 integer-zero placeholder from a
definition (or `begin` ending in a definition) is normalized to unspecified;
meaningful zero expressions remain values. See the exact corrections and tested
artifact policy in [COMPATIBILITY.md](COMPATIBILITY.md). Multiple top-level forms can therefore publish
multiple return values in one cell. A quoted string value remains quoted;
it is not confused with an explicit `display` call.

Errors come from `result.ok` and `error.kind`, never from the wording of
user output. Output and displays produced before an error are retained, and
the rest of the cell is not evaluated. Structured error details retain the
runtime's source information. Form offsets supply cell context when the
runtime provides no location; locations in external files must not be
presented as notebook-cell positions. Unknown future error kinds remain
errors with a generic classification.

## Editor and lifecycle requests

Machine-mode completion asks the runtime for builtin and session-defined
identifiers matching a prefix. Jupyter token replacement positions remain
local because EREPL v1 returns matches without cursor offsets. Documentation
inspection also remains local.

Completeness starts with the runtime's `is_complete` response. The kernel's
lexical reader corrects proven EREPL v1 reader-token defects for unfinished
strings/prefixes, character literals, escaped identifiers and interpolation.
Local indentation is only a presentation suggestion. Upstream currently implements
completeness using a parenthesis/string/comment scan; `complete` does not
mean the source has passed full syntax validation. Completion bookkeeping
can also contain names whose definitions failed at runtime.

Interrupt is an out-of-band native signal, not a JSON request, because the
runtime cannot read stdin while evaluating. A successful interrupt returns a
structured `interrupted` error; the process may then be reused. Native
runtime and frontend behavior still require real-runtime testing.

A full session reset/restart shuts down the old process and starts another.
EREPL `reset` only clears tracked-definition bookkeeping and cannot unload
JIT definitions, so it is not used as a substitute for a clean reset.
Shutdown requests orderly native teardown, with bounded cleanup if the child
does not respond.

## Validation and remaining limits

Focused fake-runtime tests validate framing, request IDs, protocol rejection,
output/value separation, source context, editor replies, and cleanup at the
Python/Jupyter boundary. They do not prove native JIT execution, repeated
native interruption, platform portability, or package-release readiness.
A focused session/Jupyter smoke also passed against the separately built
upstream `341ac812ed600fd9d27c28e9509d66ab71363947` Linux runtime
(`tests/test_real_eshkol.py`, 2 tests). Broader real-runtime tests are a
separate effort; do not infer their results from these smoke tests.

The runtime captures stdout until each form finishes; this bridge does not
provide incremental output during a long-running form. Stderr diagnostics
are separate from structured language errors, and relative ordering between
stdout and stderr cannot be guaranteed. Rich display remains a JSON-line
convention. Stderr is a newline-framed shared protocol/diagnostic channel;
programs must not emit reserved EREPL framing on it. Windows native execution and interrupt behavior have not been
verified by this migration.

## Upstream contract and future scope

The implementation was checked against upstream commit
`341ac812ed600fd9d27c28e9509d66ab71363947`:

- [EREPL wire contract](https://github.com/tsotchke/eshkol/blob/341ac812ed600fd9d27c28e9509d66ab71363947/docs/reference/runtime/eshkol-repl.md)
- [Reference Python client](https://github.com/tsotchke/eshkol/blob/341ac812ed600fd9d27c28e9509d66ab71363947/tools/erepl_client.py)
- [Native REPL implementation](https://github.com/tsotchke/eshkol/blob/341ac812ed600fd9d27c28e9509d66ab71363947/exe/eshkol-repl.cpp)
- [Canonical roadmap](https://github.com/tsotchke/eshkol/blob/341ac812ed600fd9d27c28e9509d66ab71363947/ROADMAP.md)
- [Compiler roadmap companion](https://github.com/tsotchke/eshkol/blob/341ac812ed600fd9d27c28e9509d66ab71363947/docs/COMPILER_ROADMAP.md)

The canonical roadmap takes precedence over its companion. It places the
full embedding SDK at v1.4.1, resident sessions at v1.5.1, and the later
session protocol and AD-aware debugger/profiler at v1.9.1, on the path to
v2.0 Starlight. Those plans do not establish current capabilities. This
bridge implements EREPL v1 only; embedding, resident sessions, debugging,
profiling, and compiler-repository integration are outside this migration.
