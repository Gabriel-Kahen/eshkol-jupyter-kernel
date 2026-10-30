# PR #2 maintenance outcome

The maintenance rerun tested kernel commit `893bf0b9772aaca8c6c2403468e57e93eb75a3b3`
against current Eshkol master `402126e596a6fe16044f9e181c4a7b36566f54ef`.
The compiler checkout was clean and upstream master was resolved again before the
run. Its handshake reports EREPL **1**, Eshkol **1.3.6-evolve**. Runtime binary
SHA256: `5afee975320f41aa3ba2ea25b332708359fefb2de00afa7f8b033c86a07b851e`.
The LLVM22 CPU-only build and standard-library custody remain recorded in
[runtime provenance](runtime-provenance.json).

## Reproduction and results

```sh
.venv/bin/python scripts/run_compatibility.py \
  --repl .external/source-repl \
  --runtime-ref 402126e596a6fe16044f9e181c4a7b36566f54ef \
  --runtime-source .external/eshkol-source \
  --output .external/maintenance-recheck-893bf0b
```

**30 passed, 3 failed, 0 skipped** in 62.49 seconds. The three failures still need
upstream work or an explicit upstream contract clarification:

| Case | Expected | Actual |
| --- | --- | --- |
| Unterminated string completeness | `incomplete` | `complete` |
| Bare quote completeness | `incomplete` | `complete` |
| Definition result | unspecified | integer `0` |

The same responses are reproduced without Jupyter through the upstream reference
client; see [direct probes](contract-probes.json). This kernel forwards them.
All 33 assertions remain enabled. Commands, dependencies, platform, kernel/compiler
commits and per-test results are retained in [rerun provenance](maintenance/runtime/provenance.json),
[JUnit](maintenance/runtime/junit.xml) and [pytest log](maintenance/runtime/pytest.log).

## Latest completed remote evidence

At PR head `893bf0b`:

- [Default CI](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41079665099)
  passed Ubuntu/macOS Python 3.11/3.12 and the real-runtime smoke/doctor job.
- [Pinned compatibility](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41079664871)
  failed. Official v1.3.6 and source `402126e5` each returned **30 passed / 3 failed**.
  Official v1.3.5 did not reach READY on its Ubuntu runner: probe return code
  **-4 (SIGILL)**, no tests executed. This differs from a prior successful startup
  on another runner and requires runtime binary/CPU portability investigation.

Remote job snapshots are retained in `maintenance/ci-893bf0b.json` and
`maintenance/compatibility-893bf0b.json`. The failing asset's exact binary hash,
platform and startup stderr are in `maintenance/release135-blocked.json`.
GitHub's PR jobs use a synthetic merge checkout; this artifact records checkout
`17171ce8`, while the workflow's head SHA is `893bf0b`. These are different Git
identities, not different claimed test runs.

## Codex review and addressed feedback

An independent Codex agent reviewed the full PR diff against `main`, including
transport, cleanup, Jupyter behavior, the evidence runner and CI. It found one
P2 issue: a valid JSON value such as `EREPL/1 []` caused the evidence runner to
raise `AttributeError` before retaining provenance. The fix checks the decoded
frame is an object before reading its fields. Six functional regressions cover
arrays, null, numbers, booleans, strings and malformed JSON.

Fix commit: `07f040ffc9426f4c26b3198663c7fb70ba0a7efd`. Follow-up Codex review
confirmed the issue resolved and all 11 runner tests passing. Focused cleanup,
transport and runner checks: **38 passed**. Full default suite at that commit:
**140 passed, 35 explicitly skipped**. Ruff passed. The skips are the 33 opt-in
compatibility cases and two opt-in real smoke cases; the real rerun above ran all
33 compatibility cases. This fix does not modify the kernel or compiler runtime
implementation, so the earlier real-runtime results remain applicable.

Follow-up remote runs for the review fix:
[default CI](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41080838460),
[compatibility CI](https://github.com/Gabriel-Kahen/eshkol-jupyter-kernel/actions/runs/41080838610).
Their status must be read from GitHub; no pending run is counted as passed here.
Reviews are performed in Codex. There is no claimed human GitHub approval.

## Merge decision and exact blockers

**Do not merge this maintenance checkpoint while the compatibility contract is
red.** The kernel changes are ready for review; all actionable Codex review
feedback has been addressed. Merge is deliberately deferred for these reasons:

1. The three current-runtime contract assertions above remain unresolved upstream.
   A fix, or an explicit upstream contract decision followed by reviewed test
   changes, is needed before claiming this compatibility contract passes.
2. The official v1.3.5 binary can SIGILL before READY on a supported CI host.
   Its startup/CPU portability must be resolved, or the supported-runtime policy
   must be explicitly narrowed with evidence. A working source build does not
   validate that distributed binary.

GitHub reports no merge conflict. The repository has only the author as a
collaborator, `main` has no branch protection, and no branch rulesets are active.
These are quality blockers, not a claim that GitHub technically forbids merging.
The author has admin merge permission; no bypass or merge was performed.
Documenting these blockers is the selected weekly maintenance outcome. No package
release or report outside this repository was changed.
