# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Fixed kernelspec installation to store absolute expanded `eshkol-repl` paths.
- Fixed setup diagnostics for kernelspec/runtime mismatches and local runtime hints.
- Hardened runtime downloads with network timeouts and safer tar extraction.
- Fixed top-level quoted datum parsing, prompt-like stdout handling, and broad error false positives.
- Fixed rich display output ordering when stdout and display data are mixed.
- Fixed timeout recovery so the next cell starts from a fresh REPL session.

## 0.1.0a1 - 2026-05-07

- Published the first alpha release to PyPI as `eshkol-kernel`.
- Added a PTY-backed Jupyter kernel for `eshkol-repl`.
- Added kernelspec installation through `eshkol-kernel-install`.
- Added Eshkol runtime download support through `eshkol-kernel-fetch-runtime`.
- Added setup diagnostics through `eshkol-kernel-doctor`.
- Added multiline and multi-form cell handling.
- Added text output, classified errors, and JSON-line `display_data` MIME bundles.
- Added static and notebook-session completion support.
- Added example notebook coverage, Jupyter protocol tests, packaging checks, and real Eshkol smoke tests.
