"""
Runs every example's test suite, each in its own subprocess.

Why not just `pytest examples/` from the repo root: several examples have
same-named modules (e.g. both 03-fullstack-streaming/server.py and
04-load-handling/server.py) and different, sometimes-conflicting
dependencies (01 and 02 don't need fastapi at all). Running them in one
pytest process risks Python's module cache silently reusing the wrong
same-named module across examples — a real bug, not a hypothetical, that
running each in its own subprocess/interpreter avoids entirely. This
mirrors how each example's own README already says to test it: cd in,
then run pytest, in isolation.

Run:
    python run_all_tests.py
"""
import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / "examples"


def main() -> int:
    example_dirs = sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir())
    overall_ok = True

    for example_dir in example_dirs:
        test_files = list(example_dir.glob("test_*.py"))
        if not test_files:
            continue

        print(f"\n{'=' * 70}\n{example_dir.name}\n{'=' * 70}")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v"] + [f.name for f in test_files],
            cwd=str(example_dir),
        )
        if result.returncode != 0:
            overall_ok = False
            print(f"FAILED: {example_dir.name}")

    print(f"\n{'=' * 70}")
    print("ALL EXAMPLES PASSED" if overall_ok else "SOME EXAMPLES FAILED — see above")
    print("=" * 70)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
