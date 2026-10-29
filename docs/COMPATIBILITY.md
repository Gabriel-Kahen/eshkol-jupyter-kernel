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

`compatibility/runtimes.json` is the reviewable fixed matrix used by
`.github/workflows/compatibility.yml`: official v1.3.5 and v1.3.6 Linux x64 lite
assets and source commit `341ac812ed600fd9d27c28e9509d66ab71363947`.
That source commit currently equals the v1.3.6 tag: testing both distinguishes
packaging/toolchain effects, not a newer language version. The existing real smoke
job is also pinned to v1.3.6. Update pins intentionally after retaining new evidence;
`latest` is not a compatibility contract. CI uploads evidence even on failure.

## Initial baseline

Kernel `1a172348bfdd13e34efe9388e115b8f8a4eb0307`, Linux x86_64, Python 3.14.7:

- Original suite: 87 passed, 2 explicitly skipped real smoke tests.
- Original real smoke tests with official v1.3.6: 2 passed.
- Expanded suite before migration: 101 passed, 29 explicitly skipped real tests.
- Legacy state test with v1.3.6: 1 passed, 26 machine-only cases skipped.

These results do not establish machine migration compatibility. The migration
must be incorporated at an exact commit and the full suite executed against it.
