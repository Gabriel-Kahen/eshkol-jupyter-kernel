# Merge-readiness validation

This supersedes the earlier blocked [maintenance checkpoint](MAINTENANCE.md).

The final freshness guard subsequently caught upstream advancing to
`4c2ac2b10996bb6a06c93efb1d55f880da4b4e68` and prevented merging the old pin.
The compiler source diff is documentation/site content plus comments in
`lib/core/ad/rigorous_interval.esk`; removing full-line comments leaves that file
byte-identical. The supported matrix was re-pinned to `4c2ac2b1` and the runtime
rebuilt. Final fresh local and remote results are recorded in the PR body and
its linked CI provenance artifacts; a merge still requires all final-head gates
and an unchanged upstream pin. The local tables below retain their exact earlier
`402126e5` provenance rather than relabeling those historical runs.
The original 33 behavior assertions are unchanged. Their three failures are now
fixed at the kernel boundary, with explicit corrections rather than xfail,
relaxed expected values, or a compiler patch.

## Reviewed implementation

Implementation `a91cd46`, followed by lexical review fix `9df58b545eba128bb042082880f9511ca3ae0588`:

- Native completeness is still requested and its schema validated. The reader
  corrects statuses for unfinished strings/prefixes, characters, escaped identifiers
  and interpolation, respecting actual Eshkol lexical boundaries.
- Successful integer-zero placeholders from `define`, `define-syntax`, and
  `begin` ending in a definition become unspecified values. Explicit final zero,
  arithmetic zero, quoted definitions, output, errors and state remain intact.
- Pure character literals use a safe `begin` wrapper to avoid native top-level
  preprocessing truncating delimiter-valued characters.
- Cell splitting preserves adjacent datums, string interpolation, escaped
  identifiers, character literals and source spans. Unsupported Scheme block/datum
  comments are not silently consumed as comments. The documented reader nesting
  limit is 256 recursive levels.

An independent Codex reviewer found and verified fixes for interpolation containing
quoted parentheses and ordinary identifiers containing `|`. Final review at
`9df58b5` found no remaining actionable finding: 147 focused tests and Ruff passed,
with direct latest-runtime controls for interpolation, pipe-containing identifiers,
definitions and genuine zero results. All review was performed in Codex; no human
GitHub approval is claimed and no Copilot review was used.

## Local validation at the reviewed source

| Runtime / check | Outcome |
| --- | --- |
| Latest source `402126e596a6fe16044f9e181c4a7b36566f54ef` | **36 passed, 0 failed, 0 skipped** |
| v1.3.5 source `74dc40d68a2cdb39c3392067ac766ccd87d5ad79` | **36 passed, 0 failed, 0 skipped** |
| Default suite | **238 passed, 38 explicit opt-in skips** |
| Ruff, sdist/wheel build, twine metadata check | Passed |

The 36 native tests are the unchanged original 33 plus three batches of native
controls for reader completeness, adjacent datums/characters/interpolation, and
definitions versus meaningful final values. The default skips are those 36 opt-in
native cases and two native smoke tests; the configured native runs execute all
36 cases. Cross-cell state, structured errors/recovery, interrupts, timeout/exit
cleanup, imports, rich output and notebook save/reload all pass in these runs.

Full commands, per-test outcomes, dependency/platform versions and exact kernel
and compiler revisions are retained under `merge-ready/latest` and
`merge-ready/source135`. Both runtime source trees were clean. Latest upstream
master was reconfirmed at `402126e5` after the tests. These are LLVM22 CPU-only
source builds; native CI separately validates the supported v1.3.6 release binary
and LLVM21 source builds.

```sh
.venv/bin/python scripts/run_compatibility.py \
  --repl .external/source-repl \
  --runtime-ref 402126e596a6fe16044f9e181c4a7b36566f54ef \
  --runtime-source .external/eshkol-source \
  --output .external/merge-ready-latest

.venv/bin/python scripts/run_compatibility.py \
  --repl .external/source135-repl \
  --runtime-ref 74dc40d68a2cdb39c3392067ac766ccd87d5ad79 \
  --runtime-source .external/source135 \
  --output .external/merge-ready-source135
```

## Artifact support and remaining upstream work

The supported gate matrix is official v1.3.6 Linux x64 lite, latest pinned source,
and exact v1.3.5 source built with a generic x86-64 stdlib. The original distributed
v1.3.5 binary remains unsupported on affected tested CPUs because it can SIGILL
before READY. Its negative evidence is retained in
`maintenance/release135-blocked.json`; its source result does not certify that
binary. This is an explicit supported-artifact change, not a passing result for
the crashing asset. The same 36 behavioral tests run for each supported gate.

Raw upstream EREPL still has the original metadata/reader defects, retained in
`contract-probes.json` and prior reports. The kernel corrections make notebook
behavior conform; they do not claim those native defects are fixed upstream.
Windows native behavior, every language construct, arbitrary hardware, and
package publication are not established by this finite compatibility suite.

## Pre-merge remote gate

The reviewed source's [default CI](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41085384649)
and [native matrix](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41085384519)
were dispatched. Final PR-head runs are linked from
[PR #2 checks](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/pull/2/checks).
Every supported matrix job must pass and upstream master must still match the
validated pin before merging. Pending checks are not counted as passes. The PR
body records the final observed CI and merge outcome; this evidence-only commit
does not alter the reviewed implementation.
