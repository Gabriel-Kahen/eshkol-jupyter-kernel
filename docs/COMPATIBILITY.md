# Runtime compatibility tests

`tests/test_runtime_compatibility.py` exercises a real kernel subprocess over
Jupyter channels and nbclient. It covers cross-cell state, multiline and multiple
forms, exact stdout versus returned values, errors and recovery, runtime completion
and completeness, stdlib discovery from an unrelated cwd, rich output order and
metadata, silent execution/history, interrupts, and saved notebook outputs.
Cross-cell state is in-process state; this suite does not establish durable
save/restore after a kernel restart.

Install test dependencies and run a pinned runtime:

```sh
python -m pip install -e '.[test]'
python scripts/run_compatibility.py \
  --repl /absolute/path/to/eshkol-repl \
  --runtime-ref v1.3.6-evolve \
  --output .external/evidence-1.3.6
```

For a source build, use the full compiler commit as `--runtime-ref` and add
`--runtime-source /path/to/compiler`. Output contains `provenance.json`,
`pytest.log`, and `junit.xml`. Provenance records the kernel revision and dirty
status, compiler revision when supplied, executable hash, platform, Python/dependency
versions, handshake/runtime version, exact test command, and outcome. If the
executable is a wrapper, its hash identifies the wrapper; retain the underlying
binary and downloaded asset hashes separately. A failed handshake is a blocked
run (exit 2), not a passing test or a skip. Do not equate compiler release labels
with protocol compatibility.

Without `ESHKOL_REAL_REPL`, the real suite explicitly skips. A configured missing
executable fails. For direct pytest runs:

```sh
ESHKOL_REAL_REPL=/path/to/eshkol-repl ESHKOL_COMPAT_TRANSPORT=machine \
  python -m pytest -ra tests/test_runtime_compatibility.py
```

`--transport legacy` runs only the legacy-compatible state test and explicitly
skips structured-output cases. It does not certify the known lossy PTY output
semantics. The runner defaults to machine transport and requires EREPL v1.

`compatibility/runtimes.json` is the fixed supported-artifact matrix used by
`.github/workflows/compatibility.yml`:

- Official v1.3.6 Linux x64 lite binary.
- Current source `4c2ac2b10996bb6a06c93efb1d55f880da4b4e68` (re-pinned after the final upstream freshness check).
- v1.3.5 source `74dc40d68a2cdb39c3392067ac766ccd87d5ad79`, built with
  a generic x86-64 standard library. This is a source-build compatibility gate.

The official v1.3.5 binary is **not supported on the affected tested CPUs**: it
can exit with SIGILL before READY, including on an Ubuntu CI runner. Its negative
evidence remains retained; a passing source build does not certify that binary.
The previous failing asset gate is replaced by the exact release's source build,
not an xfail or a skipped test. All original 33 behavioral assertions stay enabled;
three added native tests cover lexical and zero-value controls. The earlier
source pin `341ac812` equals the v1.3.6 tag and remains in historical evidence.
The real smoke job stays pinned to v1.3.6. Update pins only with fresh evidence;
`latest` is not a compatibility contract. CI uploads evidence on failure too.

## EREPL v1 compatibility corrections

The upstream reference client still exposes the earlier runtime defects. The
kernel now corrects the notebook-facing behavior without changing the tests:

- Native completeness is still requested and validated. The lexical reader
  corrects unfinished strings/reader prefixes and statuses distorted by character
  literals, escaped identifiers or string interpolation. Ordinary native results
  stay authoritative otherwise.
- Only a successful integer-zero placeholder from `define`, `define-syntax`, or
  `begin` ending in one of those definitions is normalized to an unspecified value.
  Arithmetic zero, quoted definition data and an explicit final zero remain values.
  Stdout, displays, state and errors are retained.
- A standalone character literal is evaluated inside `begin` to avoid native
  top-level token preprocessing truncating delimiter-valued characters. It is a
  pure literal and retains the same value.
- Cell splitting respects strings, interpolation, escaped identifiers, characters,
  vectors, nested prefixes and adjacent datums. Only semicolon line comments are
  consumed as trivia; unsupported Scheme block/datum comments are not silently
  discarded. Recursive list/prefix nesting is bounded to 256 levels and fails
  explicitly beyond that bound rather than exhausting Python's call stack.

These are explicit client corrections to the EREPL v1 boundary, not compiler
fixes or silent protocol downgrade. Raw upstream evidence remains available for
upstream remediation. Corrected future `unspecified` results are left untouched.

## Initial baseline

Kernel `1a172348bfdd13e34efe9388e115b8f8a4eb0307`, Linux x86_64, Python 3.14.7:

- Original suite: 87 passed, 2 explicitly skipped real smoke tests.
- Original real smoke tests with official v1.3.6: 2 passed.
- Expanded suite before migration: 101 passed, 29 explicitly skipped real tests.
- Legacy state test with v1.3.6: 1 passed, 26 machine-only cases skipped.

These results do not establish machine migration compatibility. The migration
must be incorporated at an exact commit and the full suite executed against it.

## Independent migration validation

See [the retained findings and evidence](compatibility/2026-10-28/FINDINGS.md) for
validation of exact migration commit `3be79e3c44e3f2e7ae9c010183891711723a387a`,
including the historical runtime contract failures. The original 33 assertions
remain unchanged; the kernel corrections and three added native control batches
are covered by the later merge-readiness evidence.

## October 30 CI fixes and recheck

[Updated evidence](compatibility/2026-10-30/FINDINGS.md) records the fixed macOS
cleanup and fake-runtime doctor failures, passing Ubuntu/macOS CI, and the same
three still-failing contract assertions against current Eshkol `402126e5`.

## Merge-readiness corrections

[Reviewed implementation and passing local native results](compatibility/2026-10-30/MERGE_READINESS.md)
supersede the earlier blocked checkpoint. Raw upstream failures and the excluded
v1.3.5 binary's negative evidence remain preserved separately.
