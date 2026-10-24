"""Run unittest integration tests in a new disposable PostgreSQL database.

Required: TEST_PGUSER (CREATEDB role). Optional TEST_PGHOST, TEST_PGPORT,
TEST_PGPASSWORD, TEST_PGMAINTENANCE_DB, TEST_PGSSLMODE. PGDATABASE is ignored.
The default JSON evidence file is test-results.json at the project root.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        self._started = time.monotonic()
        super().startTest(test)

    def record(self, test, status, detail=None):
        item = {"test": test.id(), "status": status,
                "seconds": round(time.monotonic() - self._started, 4)}
        if detail:
            item["detail"] = detail
        self.records.append(item)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "ERROR", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "SKIP", reason)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match", default="", help="Run only test IDs containing this substring")
    parser.add_argument("--report", type=Path, default=ROOT / "test-results.json")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
              "python_version": platform.python_version(), "platform": platform.platform()}
    sandbox = result = None
    try:
        import support
        report["driver_version"] = support.psycopg2.__version__
        with support.disposable_database("TEST") as sandbox:
            support.configure(sandbox)
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_release.py")
            suite = unittest.TestSuite(t for t in flatten(suite) if args.match in t.id())
            if not suite.countTestCases():
                raise ValueError("No tests matched; refusing to report an empty run as successful.")
            suite_started = time.perf_counter()
            result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
            report["suite_seconds"] = round(time.perf_counter() - suite_started, 4)
    except Exception as exc:
        report["runner_error"] = f"{type(exc).__name__}: {exc}"
        print(report["runner_error"], file=sys.stderr)
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["total_seconds"] = round(time.perf_counter() - started, 4)
        if sandbox:
            report.update(database=sandbox.database, database_created=sandbox.created,
                          database_removed=sandbox.removed, server_version=sandbox.server_version)
        if result:
            report.update(tests_run=result.testsRun, failures=len(result.failures),
                          errors=len(result.errors), skipped=len(result.skipped), results=result.records,
                          passed=result.wasSuccessful() and sandbox.removed and "runner_error" not in report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Evidence written to {args.report}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
