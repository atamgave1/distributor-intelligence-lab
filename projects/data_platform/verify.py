"""Run regression tests + independent shared-data reconciliation; save evidence."""
import hashlib
import io
import json
from pathlib import Path
import platform
import sqlite3
import time
import unittest

from portfolio_shared.data import ensure_database
from projects.data_platform.pipeline import run, now


def main():
    root = Path(__file__).parent
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (evidence / "unit-tests.txt").write_text(stream.getvalue())
    if not result.wasSuccessful():
        raise SystemExit("Regression tests failed; see evidence/unit-tests.txt")
    source = ensure_database()
    warehouse = evidence / "warehouse.sqlite"
    started = time.perf_counter()
    first = run(str(source), str(warehouse), full_refresh=True)
    elapsed = time.perf_counter() - started
    second = run(str(source), str(warehouse))
    conn = sqlite3.connect(source)
    try:
        expected = conn.execute("SELECT COUNT(*),SUM(net_revenue_cents),SUM(cogs_cents),SUM(units) FROM v_sales").fetchone()
        per_year = conn.execute("SELECT SUBSTR(event_date,1,4),SUM(net_revenue_cents) FROM v_sales GROUP BY 1 ORDER BY 1").fetchall()
    finally:
        conn.close()
    conn = sqlite3.connect(warehouse)
    try:
        actual = conn.execute("SELECT COUNT(*),SUM(net_revenue_cents),SUM(cogs_cents),SUM(units) FROM published_sales").fetchone()
        daily = conn.execute("SELECT SUM(event_count),SUM(net_revenue_cents),SUM(cogs_cents),SUM(units) FROM daily_sales").fetchone()
        metadata = dict(conn.execute("SELECT name,watermark FROM pipeline_state"))
    finally:
        conn.close()
    assert expected == actual == daily, (expected, actual, daily)
    assert first["active_rows"] == second["active_rows"]
    assert first["net_revenue_cents"] == second["net_revenue_cents"]
    report = {
        "generated_at_utc": now(), "data_provenance": "100% synthetic; shared distributor fixture",
        "python": platform.python_version(), "os": platform.system(),
        "unit_tests": result.testsRun, "unit_tests_passed": result.wasSuccessful(),
        "shared_source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        "mode": first["mode"], "source_events": expected[0],
        "net_revenue_cents": expected[1], "cogs_cents": expected[2], "net_units": expected[3],
        "annual_net_revenue_cents": dict(per_year), "watermarks": metadata,
        "source_detail_daily_reconcile": expected == actual == daily,
        "rerun_reconciles": first["net_revenue_cents"] == second["net_revenue_cents"],
        "full_refresh_elapsed_seconds": round(elapsed, 4),
        "measurement_scope": "Local wall-clock observation; not a throughput or production SLA claim",
        "not_executed": ["Airbyte", "Airflow", "dbt", "Redshift", "Superset"],
    }
    (evidence / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
