"""Run real-runtime tests and retain revision, handshake and outcome evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(*args, cwd=ROOT, **kwargs):
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=60, **kwargs)
        return {"argv": list(args), "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"argv": list(args), "timeout": 60}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repl", required=True, type=Path)
    parser.add_argument("--transport", choices=["machine", "legacy"], default="machine")
    parser.add_argument("--runtime-ref", required=True, help="Exact compiler commit or release tag")
    parser.add_argument("--runtime-source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.runtime_ref in {"latest", "master", "main", "HEAD"}:
        parser.error("--runtime-ref must identify a fixed revision")
    repl = args.repl.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    probe = command(str(repl), "--machine", input='{"id":"probe","op":"shutdown"}\n')
    ready = []
    for line in probe.get("stderr", "").splitlines():
        if line.startswith("EREPL/1 "):
            try:
                frame = json.loads(line[8:])
                if isinstance(frame, dict) and frame.get("type") == "ready":
                    ready.append(frame)
            except ValueError:
                pass
    report = {
        "schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
        "kernel_head": command("git", "rev-parse", "HEAD"),
        "kernel_status": command("git", "status", "--short"),
        "runtime_ref": args.runtime_ref, "repl": str(repl),
        "repl_sha256": hashlib.sha256(repl.read_bytes()).hexdigest(),
        "transport": args.transport, "handshake": ready, "probe": probe,
        "dependencies": {name: importlib.metadata.version(name) for name in
                         ["eshkol-kernel", "ipykernel", "jupyter-client", "nbclient", "pytest"]},
    }
    if args.runtime_source:
        report["compiler_head"] = command("git", "rev-parse", "HEAD", cwd=args.runtime_source)
        report["compiler_status"] = command("git", "status", "--short", cwd=args.runtime_source)
    env = os.environ.copy()
    env.update(ESHKOL_REAL_REPL=str(repl), ESHKOL_COMPAT_TRANSPORT=args.transport)
    argv = [sys.executable, "-m", "pytest", "-ra", "tests/test_runtime_compatibility.py",
            "tests/test_runtime_reader_compatibility.py",
            f"--junitxml={output / 'junit.xml'}"]
    report["test_command"] = argv
    valid = args.transport != "machine" or (len(ready) == 1 and ready[0].get("protocol_version") == 1)
    if not valid:
        report["outcome"] = "blocked: required EREPL v1 handshake unavailable"
        code = 2
    else:
        with (output / "pytest.log").open("w") as log:
            result = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        code = result.returncode
        report["pytest_exit_code"] = code
        report["outcome"] = "passed" if code == 0 else "failed"
        print((output / "pytest.log").read_text())
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['outcome']}: {output}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
