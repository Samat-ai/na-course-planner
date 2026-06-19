"""PostToolUse hook: run the test suite after edits to Python files under src/ or tests/.

Informational only — always exits 0, so it never blocks an edit (a failing test during the
TDD "red" phase is expected). Reads the hook payload (JSON) from stdin.
"""
import json
import pathlib
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    norm = file_path.replace("\\", "/")
    if not norm.endswith(".py") or ("/src/" not in norm and "/tests/" not in norm):
        return 0

    root = pathlib.Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["py", "-3", "-m", "pytest", "-q"],
            cwd=root, capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[run_tests hook] could not run pytest: {e}")
        return 0

    out = (result.stdout or "")[-3000:]
    err = (result.stderr or "")[-1000:]
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
