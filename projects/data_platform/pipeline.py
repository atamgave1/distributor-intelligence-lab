"""Retry-safe SQLite ELT. Run from portfolio-lab: python -m projects.data_platform.pipeline."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import uuid

FIELDS = ("event_id", "event_date", "order_id", "customer_id", "product_id",
          "net_revenue_cents", "cogs_cents", "units", "kind", "customer_name",
          "segment", "region", "product_name", "category")
INTEGERS = {"net_revenue_cents", "cogs_cents", "units"}
RAW_COLUMNS = ", ".join(f"{f} {'INTEGER' if f in INTEGERS else 'TEXT'} NOT NULL" for f in FIELDS)
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_CLOCK_SKEW_SECONDS = 300


def now() -> str:
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(f"""
    CREATE TABLE IF NOT EXISTS raw.sales_events (
      {RAW_COLUMNS}, updated_at TEXT NOT NULL, is_deleted INTEGER NOT NULL,
      PRIMARY KEY(event_id));
    CREATE TABLE IF NOT EXISTS pipeline_state (
      name TEXT PRIMARY KEY, watermark TEXT, published_at TEXT);
    CREATE TABLE IF NOT EXISTS pipeline_runs (
      run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
      status TEXT NOT NULL, source_rows INTEGER DEFAULT 0, active_rows INTEGER,
      watermark TEXT, error TEXT);
    CREATE TABLE IF NOT EXISTS published_sales ({RAW_COLUMNS}, PRIMARY KEY(event_id));
    CREATE TABLE IF NOT EXISTS daily_sales (
      event_date TEXT PRIMARY KEY, net_revenue_cents INTEGER NOT NULL,
      cogs_cents INTEGER NOT NULL, gross_margin_cents INTEGER NOT NULL,
      units INTEGER NOT NULL, event_count INTEGER NOT NULL);
    """)
    conn.commit()


def _validate(rows: list[dict], *, run_started_at: str) -> None:
    latest_allowed = datetime.strptime(run_started_at, TIMESTAMP_FORMAT) + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    seen = set()
    for row in rows:
        event = row["event_id"]
        if event in seen:
            raise ValueError(f"duplicate event_id in source batch: {event}")
        seen.add(event)
        for field in FIELDS:
            value = row[field]
            if field in INTEGERS:
                if not isinstance(value, int):
                    raise ValueError(f"{event}: {field} must be integer cents/units")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"{event}: {field} must be nonempty text")
        try:
            date = datetime.strptime(row["event_date"], "%Y-%m-%d")
            stamp = datetime.strptime(row["updated_at"], TIMESTAMP_FORMAT)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{event}: invalid date or UTC updated_at") from exc
        if date.strftime("%Y-%m-%d") != row["event_date"] or stamp.strftime(TIMESTAMP_FORMAT) != row["updated_at"]:
            raise ValueError(f"{event}: dates must use canonical ISO formatting")
        if stamp > latest_allowed:
            raise ValueError(f"{event}: updated_at exceeds run start plus {MAX_CLOCK_SKEW_SECONDS}-second clock-skew tolerance")
        if row["is_deleted"] not in (0, 1):
            raise ValueError(f"{event}: is_deleted must be 0 or 1")
        kind, revenue, cost, units = (row[k] for k in ("kind", "net_revenue_cents", "cogs_cents", "units"))
        if kind == "sale":
            valid = revenue >= 0 and cost >= 0 and units > 0
        elif kind == "return":
            valid = revenue <= 0 and cost <= 0 and units < 0
        else:
            valid = False
        if not valid:
            raise ValueError(f"{event}: invalid kind or signed sale/return values")


def run(source_db: str, warehouse_db: str, *, raw_db: str | None = None,
        overlap_seconds: int = 86400, full_refresh: bool = False,
        inject_failure: str | None = None) -> dict:
    """Read a stable source snapshot and atomically publish all validated active rows.

    Mutable sources expose sales_events with FIELDS, updated_at (UTC ISO text), and
    is_deleted (0/1). Shared v_sales is a static snapshot adapter: all source rows are
    scanned each run with a fixed timestamp; it does not model CDC/hard deletion.
    Failure injection is for tests: after_raw or before_publish.
    """
    if overlap_seconds < 0:
        raise ValueError("overlap_seconds cannot be negative")
    if inject_failure not in (None, "after_raw", "before_publish"):
        raise ValueError("unknown failure injection point")
    paths = [Path(source_db).resolve(), Path(warehouse_db).resolve(),
             Path(raw_db or (str(warehouse_db) + ".raw.sqlite")).resolve()]
    if len(set(paths)) != 3:
        raise ValueError("source, raw, and warehouse must be separate files")
    if not paths[0].is_file():
        raise FileNotFoundError(paths[0])
    for path in paths[1:]:
        path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(paths[0].as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    warehouse = sqlite3.connect(paths[1], timeout=30)
    warehouse.row_factory = sqlite3.Row
    run_id, started, rows = uuid.uuid4().hex, now(), []
    try:
        # Attached file + rollback journals support one SQLite cross-file commit.
        # WAL is deliberately disabled; do not change this to WAL for this demo.
        warehouse.execute("PRAGMA journal_mode=DELETE")
        warehouse.execute("ATTACH DATABASE ? AS raw", (str(paths[2]),))
        warehouse.execute("PRAGMA raw.journal_mode=DELETE")
        _initialize(warehouse)
        warehouse.execute("BEGIN IMMEDIATE")
        state = warehouse.execute("SELECT watermark FROM pipeline_state WHERE name='sales'").fetchone()
        previous = state[0] if state else None
        cutoff = None
        if previous and not full_refresh:
            cutoff = (datetime.strptime(previous, TIMESTAMP_FORMAT) - timedelta(seconds=overlap_seconds)).strftime(TIMESTAMP_FORMAT)
        source.execute("BEGIN")
        exists = source.execute("SELECT 1 FROM sqlite_master WHERE name='sales_events' AND type IN ('table','view')").fetchone()
        relation = "sales_events" if exists else "v_sales"
        columns = {r[1] for r in source.execute(f"PRAGMA table_info({relation})")}
        required = set(FIELDS) | ({"updated_at", "is_deleted"} if exists else set())
        if not required.issubset(columns):
            raise ValueError(f"{relation} missing required fields: {sorted(required-columns)}")
        projection = ",".join(FIELDS)
        if exists:
            query = f"SELECT {projection},updated_at,is_deleted FROM sales_events"
            args = ()
            if cutoff:
                query += " WHERE updated_at >= ?"
                args = (cutoff,)
        else:
            # Snapshot mode deliberately scans the whole immutable shared fixture.
            query = f"SELECT {projection},'2025-12-31T23:59:59Z' AS updated_at,0 AS is_deleted FROM v_sales"
            args = ()
        rows = [dict(r) for r in source.execute(query, args)]
        # Shared dimension keys are integers; normalize identifiers to text in
        # the warehouse without changing any monetary or quantity types.
        for row in rows:
            for key in ("event_id", "order_id", "customer_id", "product_id"):
                if isinstance(row[key], int):
                    row[key] = str(row[key])
        _validate(rows, run_started_at=started)
        watermark = max([r["updated_at"] for r in rows] + ([previous] if previous and not full_refresh else []), default=None)
        if full_refresh:
            warehouse.execute("DELETE FROM raw.sales_events")
        cols = FIELDS + ("updated_at", "is_deleted")
        upsert = (f"INSERT INTO raw.sales_events ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
                  f"ON CONFLICT(event_id) DO UPDATE SET {','.join(f'{c}=excluded.{c}' for c in cols if c != 'event_id')} "
                  "WHERE excluded.updated_at >= sales_events.updated_at")
        warehouse.executemany(upsert, ([r[c] for c in cols] for r in rows))
        if inject_failure == "after_raw":
            raise RuntimeError("injected failure after raw merge")
        # Publishing both detail and aggregate tables, watermark, and run log is
        # one transaction: readers see either the previous or the next dataset.
        warehouse.execute("DELETE FROM published_sales")
        warehouse.execute(f"INSERT INTO published_sales SELECT {','.join(FIELDS)} FROM raw.sales_events WHERE is_deleted=0")
        warehouse.execute("DELETE FROM daily_sales")
        warehouse.execute("""INSERT INTO daily_sales
          SELECT event_date,SUM(net_revenue_cents),SUM(cogs_cents),
                 SUM(net_revenue_cents-cogs_cents),SUM(units),COUNT(*)
          FROM published_sales GROUP BY event_date""")
        active = warehouse.execute("SELECT COUNT(*) FROM published_sales").fetchone()[0]
        detail = warehouse.execute("SELECT COALESCE(SUM(net_revenue_cents),0) FROM published_sales").fetchone()[0]
        aggregate = warehouse.execute("SELECT COALESCE(SUM(net_revenue_cents),0) FROM daily_sales").fetchone()[0]
        if detail != aggregate:
            raise ValueError("daily mart failed detail reconciliation")
        if inject_failure == "before_publish":
            raise RuntimeError("injected failure before commit")
        finished = now()
        warehouse.execute("INSERT INTO pipeline_state VALUES ('sales',?,?) ON CONFLICT(name) DO UPDATE SET watermark=excluded.watermark,published_at=excluded.published_at", (watermark, finished))
        warehouse.execute("INSERT INTO pipeline_runs VALUES (?,?,?,'succeeded',?,?,?,NULL)", (run_id, started, finished, len(rows), active, watermark))
        warehouse.commit()
        return {"status": "succeeded", "run_id": run_id, "mode": "incremental" if exists else "static_snapshot",
                "source_rows": len(rows), "active_rows": active, "net_revenue_cents": detail,
                "watermark": watermark, "warehouse_db": str(paths[1]), "raw_db": str(paths[2])}
    except Exception as exc:
        warehouse.rollback()
        # Failed attempt is recorded separately after rolling back publication.
        try:
            warehouse.execute("INSERT INTO pipeline_runs (run_id,started_at,finished_at,status,source_rows,error) VALUES (?,?,?,'failed',?,?)", (run_id, started, now(), len(rows), str(exc)))
            warehouse.commit()
        except sqlite3.Error:
            pass
        raise
    finally:
        source.close()
        warehouse.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="SQLite database containing shared v_sales or mutable sales_events")
    parser.add_argument("--warehouse", default="output/data_platform/warehouse.sqlite")
    parser.add_argument("--raw")
    parser.add_argument("--overlap-seconds", type=int, default=86400)
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()
    source = args.source
    if source is None:
        from portfolio_shared.data import ensure_database
        source = str(ensure_database())
    print(json.dumps(run(source, args.warehouse, raw_db=args.raw,
                         overlap_seconds=args.overlap_seconds, full_refresh=args.full_refresh), indent=2))


if __name__ == "__main__":
    main()
