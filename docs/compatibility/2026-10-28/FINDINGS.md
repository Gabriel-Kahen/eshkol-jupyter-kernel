# Independent migration validation

The isolated kernel worktree is `/home/gabe/.codex/worktrees/4cc3/eshkol-jupyter-kernel`,
branch `codex/kernel-compatibility-tests`, original base
`1a172348bfdd13e34efe9388e115b8f8a4eb0307`.

Testing commits are `afad8b434b996e6ba5ef8062d2d0d7235b5bf71c` and
`01d0acc` (lifecycle/provenance additions). Exact migration commit
`3be79e3c44e3f2e7ae9c010183891711723a387a` was cherry-picked unchanged as
`e6e6fbfecc94ad2d6073aa7c85cc8275b2be23e0`. The final tested source revision is
`6ab3d18` (isolates the definition-result assertion so notebook roundtrip checks
can finish independently). No kernel implementation or compiler fixes were made
by this testing chat.

## Confirmed runtime contract defects

All three usable runtimes reproduce these directly through the pinned upstream
`tools/erepl_client.py`, with no kernel or Jupyter in the path:

| Request | Expected | Actual |
| --- | --- | --- |
| `is_complete` with code `"unterminated` | `incomplete` | `complete` |
| `is_complete` with code `'` | `incomplete` | `complete` |
| `eval` with code `(define compat-reference-value 41)` | unspecified value | `value="0", value_type="integer"` |

The following read of `compat-reference-value` correctly returns `41`; cross-cell
state is functioning. These are runtime responses faithfully forwarded by the
migration. The current protocol documentation explicitly describes definitions
as unspecified. The tests retain those intended behavior assertions as failures;
there are no xfail, continue-on-error, version-based suppressions, or weakened
expectations for these cases. The pinned CI matrix is consequently expected to
remain red until the owning runtime contract is resolved.

Raw reference probe results are in `completeness-reference-probes.json` and
`definition-reference-probes.json`. Reproduce through the upstream reference driver:

```python
# Run with tools/ on PYTHONPATH from the exact compiler source checkout.
from erepl_client import EReplClient
with EReplClient('/absolute/path/to/runtime-wrapper') as client:
    print(client.is_complete('"unterminated'))
    print(client.is_complete("'"))
    print(client.execute('(define compat-reference-value 41)'))
    print(client.execute('compat-reference-value'))
```

## Runtime provenance and scope

See `runtime-provenance.json` for asset/binary SHA256, resolved release commits,
LLVM flags, library dependency closure, platform, and commands. Both source trees
were clean. Local host: CachyOS x86_64, Python 3.14.7, LLVM/Clang 22.1.8.
The official assets require LLVM21/BLAS; dependencies were extracted into an
isolated directory without system installation changes.

- Official v1.3.6 asset and current source SHA
  `341ac812ed600fd9d27c28e9509d66ab71363947` each passed the upstream reference
  self-test (34 checks). This source SHA equals the v1.3.6 tag, so it is a separate
  source/toolchain build rather than a newer language release.
- v1.3.5 source `74dc40d68a2cdb39c3392067ac766ccd87d5ad79` passed its own reference
  self-test (22 checks). The newer deterministic compile-interruption test hook is
  unavailable there; this is not a promise of every current compiler test on older releases.
- The official v1.3.5 asset exits with SIGILL before READY on this host, despite
  resolved shared-library dependencies. The runner records it as blocked (exit 2),
  without claiming that its source-build result validates the official binary.

The suite covers in-process cross-cell state, multiple/multiline forms, exact
stdout and distinct typed values, structured language errors and recovery,
error-like user text, bounded interrupt/timeout/exit and recovery, stdlib/import
discovery from an unrelated cwd, completion/completeness, ordered rich output,
silent requests/history, parent correlation, and nbclient saved-notebook output.
Durable save/restore across restart, hardware matrices, macOS/Windows real runs,
and package publication remain outside this evidence. The Ubuntu/Python3.12/
LLVM21 CI workflow was parsed and its shell steps checked locally; it has not been
dispatched or observed passing. Source wrappers deliberately select matching
library roots; they do not prove an installed source build discovers everything
without configuration. The installation reminder is tracked separately in
[issue #1](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/issues/1).

## Final outcomes

All final suite runs used clean tested kernel source `6ab3d18` (the following
commit only retains documentation/evidence). Each real run exercised 33 cases:

| Runtime | Passed | Failed | Skipped | Evidence |
| --- | ---: | ---: | ---: | --- |
| Official v1.3.6 Linux x64 lite | 30 | 3 | 0 | [release136](release136/provenance.json) |
| Current source `341ac812`, LLVM22 | 30 | 3 | 0 | [source136](source136/provenance.json) |
| v1.3.5 source `74dc40d6`, LLVM22 | 30 | 3 | 0 | [source135](source135/provenance.json) |
| Official v1.3.5 Linux x64 lite | — | — | — | [blocked before READY](release135-blocked/provenance.json) |

Each configured real run exits 1 with exactly the three contract assertions above.
There were no unexpected skips. Cross-cell state, timeout/exit cleanup and recovery,
interrupt state survival, imports, rich-output ordering, and nbclient notebook
save/reload all passed on all three usable runtimes. Tests are retained failing
until the owning runtime behavior or contract is resolved. The blocked official
v1.3.5 probe was recorded at integration revision `e6e6fbf`; no tests ran in that case.

Default suite: **129 passed, 35 explicitly skipped** (33 opt-in compatibility cases
and two opt-in native smoke tests), recorded in `default-junit.xml`. Ruff, sdist
and wheel build, and `twine check` passed. The workflow YAML loaded and each shell
step passed `bash -n`. CI was not dispatched. Nothing was published or merged.

Re-run using the exact `test_command` and executable recorded in each provenance
file, or use `scripts/run_compatibility.py` as described in `docs/COMPATIBILITY.md`.
The scripts and CI configuration make reruns reproducible after changes without
relying on the cached local runtimes. Runtime binaries and compiler trees remain
under the ignored `.external/` directory; retained JSON/log/XML evidence is committed.
