# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Improved execution errors to stop at the failing top-level form and report its cell line, column, and source excerpt.

## 0.1.0a3 - 2026-05-08

- Added an `eshkol` Pygments lexer for `.esk` files and rendered notebook output.
- Added helper payloads for pretty printing, markdown/HTML/SVG/JSON/LaTeX/PNG display, tables, and trees.
- Updated the kernel language metadata to advertise the Eshkol lexer instead of Scheme.

## 0.1.0a2 - 2026-05-08

- Added `eshkol-kernel-setup` to find or download Eshkol, install the kernelspec, run diagnostics, and print next steps.
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
