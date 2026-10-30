# CI fixes and current Eshkol recheck

The kernel fixes are commit `51cc1eb2958b8c2cd66666a5dbd66eaaccf0ea40`, based on
PR #2's earlier head `7b0cc05db32ddbf4f688b83d54781c9e68d73398`. Work was isolated
in `/home/gabe/.codex/worktrees/4cc3/eshkol-jupyter-kernel-current`. The original
primary checkout's uncommitted files were preserved.

## Kernel CI failures fixed

- The fake-runtime doctor workflow now invokes `fake_machine_repl.py`, which speaks
  the default EREPL v1 protocol. Previously it invoked the interactive PTY fake and
  timed out waiting for a machine handshake.
- POSIX cleanup tolerates process-group `EPERM` only after the owned child exits,
  preserving the original startup/EOF error on macOS. If the child is still alive,
  cleanup falls back to signaling that owned process directly. A denied direct
  signal remains an explicit error. The final descendant group sweep remains.
- Five regression tests cover stale-group startup and request failures, live-child
  termination, denied direct signals, and descendants surviving their group leader.

Local default suite: **134 passed, 35 explicitly skipped** (33 opt-in real-runtime
compatibility cases and 2 opt-in smoke cases), recorded in `final-default-junit.xml`.
Ruff and the exact corrected fake-runtime doctor command passed.

The [GitHub CI run](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41079165076)
for exact kernel commit `51cc1eb` completed successfully: Ubuntu and macOS with
Python 3.11 and 3.12, plus the real-runtime smoke/doctor job. `ci-results.json`
retains the remote job conclusions; this is new remote evidence, separate from
the previous local-only checks.

## Current runtime contract

Current upstream master was resolved, built and rechecked at
`402126e596a6fe16044f9e181c4a7b36566f54ef`. It reports EREPL v1 and runtime version
`1.3.6-evolve`. The upstream changes since the previous source pin `341ac812` are
documentation-only; no compiler source was changed for this work.

Direct upstream reference-client probes still reproduce all three assertions:

| Request | Expected | Actual |
| --- | --- | --- |
| `is_complete` with `"unterminated` | `incomplete` | `complete` |
| `is_complete` with `'` | `incomplete` | `complete` |
| `eval` definition | empty value with `value_type=unspecified` | `value=0`, `value_type=integer` |

The following read of the defined variable returns the correct value, and imports
and stdlib calls succeed. Upstream's own reference self-test passes 34 checks; it
thus does not cover these contract defects. `contract-probes.json` retains exact
requests, expected/actual data and control probes, without Jupyter in the path.
`runtime-provenance.json` records the clean compiler tree, binary/stdlib hashes,
LLVM22 CPU-only build commands, wrapper library roots and runtime handshake.
The runtime build began at kernel base `7b0cc05`; direct probes and the complete
kernel suite used `51cc1eb`, as recorded independently in their evidence.

No xfail, expected-result adjustment, silent fallback, compiler patch, or test
suppression was added. The CI source matrix now pins `402126e5`, while retaining
v1.3.5 and v1.3.6 official release cases and all three contract assertions.

The complete local Jupyter/nbclient suite against current source finished with
**30 passed, 3 failed, 0 skipped** in 60.89 seconds. The three failures are exactly
the assertions above. State across cells, output fidelity, structured errors and
recovery, imports, interrupts, timeout/exit cleanup, rich output and notebook
save/reload all passed. Full commands and per-test outcomes are retained in
`current-runtime/provenance.json`, `current-runtime/pytest.log` and
`current-runtime/junit.xml`. These tests used a clean kernel source tree at
`51cc1eb` before the evidence-only documentation commit. No compiler fix is claimed.
