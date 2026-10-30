"""Run all local release gates and save a reproducible verification report."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import unittest

from portfolio_shared.data import ROOT, ensure_database, read_only


def main():
    started=time.perf_counter()
    artifact=ROOT/"artifacts"
    artifact.mkdir(exist_ok=True)
    database=ensure_database()
    suite=unittest.TestSuite()
    loader=unittest.defaultTestLoader
    for module in ("tests.test_shared","projects.ai_analytics.test_engine","projects.data_platform.tests.test_pipeline","projects.analytics_dashboard.test_metrics","tests.test_integration"):
        suite.addTests(loader.loadTestsFromName(module))
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (artifact/"tests.txt").write_text(stream.getvalue())
    print(stream.getvalue())
    frontend={"status":"not_run","reason":"Node.js unavailable"}
    if shutil.which("node"):
        process=subprocess.run(["node","projects/analytics_dashboard/test_frontend.js"],cwd=ROOT,text=True,capture_output=True)
        frontend={"status":"passed" if process.returncode==0 else "failed","output":process.stdout+process.stderr}
        print(frontend["output"])
    with read_only(database) as db:
        reference=json.loads(db.execute("SELECT value FROM metadata WHERE key='reference_metrics'").fetchone()[0])
    success=result.wasSuccessful() and frontend["status"]=="passed"
    report={"status":"passed" if success else "failed","completed_at":datetime.now(timezone.utc).isoformat(),"environment":f"Python {platform.python_version()} / {platform.system()} {platform.machine()}","tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"frontend":frontend,"elapsed_seconds":round(time.perf_counter()-started,3),"dataset":reference,"scope":"Local deterministic demonstration and statistical baseline; not a live LLM or cloud deployment","deferred":["Live LLM integration and provider evaluation","Airbyte/Airflow/dbt/Superset runtime integrations","AWS Athena/QuickSight deployment"]}
    (artifact/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Verification: {report['status']} ({result.testsRun} Python tests; frontend {frontend['status']})")
    return 0 if success else 1


if __name__=="__main__":
    raise SystemExit(main())
