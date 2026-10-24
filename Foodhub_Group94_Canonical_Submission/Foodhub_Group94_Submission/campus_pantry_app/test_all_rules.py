"""Compatibility entry point for the isolated integration suite.

Requires explicit TEST_PG* configuration; never uses the application's database.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests" / "run_tests.py"),
                  run_name="__main__")
