# Local pipeline runbook

## Prerequisites and boundaries

Run Python 3 from the repository root. No packages beyond the standard library are needed for the executed pipeline. Use only the generated dataset or a synthetic mutable fixture. Never connect this demo to client production databases. All three database paths must be distinct.

## Initial run and validation

```sh
python3 -m projects.data_platform.pipeline --warehouse output/data_platform/warehouse.sqlite
python3 -m projects.data_platform.verify
```

Success means the CLI returns `status: succeeded`, a committed watermark, active row count and net revenue. Verification must exit zero and show `source_detail_daily_reconcile: true`. Its evidence records the actual shared fixture revision hash. Do not report numbers copied from a previous evidence file after changing the generator.

## Inspect results without extra tools

Use Python's `sqlite3` module to query the warehouse. `pipeline_runs` records succeeded/failed attempts, timestamps, extracted row counts, active rows on successful runs, committed watermark and error text. `pipeline_state` holds the last committed watermark and publication time. `published_sales` contains active detail; `daily_sales` contains daily totals. The separate raw file's `sales_events` retains tombstones and source timestamps.

## Mutable source operations

Call `pipeline.run(source_db, warehouse_db, raw_db=..., overlap_seconds=86400)` from Python, or pass `--source PATH` to the CLI. The source must expose the documented `sales_events` table/view. To remove an event, update its timestamp and set `is_deleted=1`; do not physically remove it. Deliver corrections with a new timestamp. The run acquires a warehouse write lock, so a second writer waits up to 30 seconds and then fails cleanly if the lock remains held.

## Failure and recovery

- **Quality failure:** inspect the error in the CLI/run log, correct the synthetic source, and rerun. The last good raw/warehouse state and watermark remain unchanged.
- **Future source timestamp:** `updated_at` may be at most 300 seconds ahead of the run's recorded UTC start. A timestamp beyond this clock-skew allowance rejects the whole batch before raw merge. Correct the source clock/timestamp and retry; do not enlarge the watermark to match a bad future date.
- **Interrupted or failed transform:** rerun the same command. SQLite rolls back the incomplete transaction. Programmatic failure injection (`after_raw`, `before_publish`) is covered by regression tests; do not enable it for normal demonstrations.
- **Update older than the overlap / replaced static fixture:** run again with `--full-refresh`. This rebuilds raw from the current source snapshot and republishes only after validation.
- **Locked database:** ensure no other process is writing to these outputs. Do not delete database journals or copy a database while a write is active.
- **Failed initial setup:** inspect paths and permissions. A failure before metadata tables exist may not produce a persisted failure row; the raised exception remains the authoritative error.

## Operational constraints

Keep both raw and warehouse on the same local filesystem. The cross-file commit relies on SQLite rollback journals, not WAL; do not enable WAL or put either file on an unreliable network filesystem. Normal concurrency is one writer with read-only consumers. A process-level fault can roll back safely; this demonstration has not performed hardware power-loss testing. Run logs are local, not an alerting service. Freshness alerting and managed scheduling are not implemented.

## Public release checklist

Run the regression/verification commands, inspect the resulting source hash and totals, manually review screenshots, and scan source/configuration for secrets. Publish code, documentation and synthetic evidence only. Runtime SQLite files may be regenerated and should be excluded from Git. Optional cloud deployments require separate permissions, cost limits, integration tests and cleanup steps.
