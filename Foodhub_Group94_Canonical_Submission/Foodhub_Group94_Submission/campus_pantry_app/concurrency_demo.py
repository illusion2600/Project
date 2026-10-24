"""Run coordinated two-connection scenarios in an owned disposable database.

Database triggers remain enabled. Only TEST_PG* configuration is accepted.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from run_tests import main

if __name__ == "__main__":
    raise SystemExit(main(["--match", "concurrency", *sys.argv[1:]]))
