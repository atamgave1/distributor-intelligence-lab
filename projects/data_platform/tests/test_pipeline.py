import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch

from projects.data_platform.pipeline import FIELDS, RAW_COLUMNS, run


@contextmanager
def connection(path):
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.sqlite"
        self.warehouse = Path(self.tmp.name) / "warehouse.sqlite"
        self.raw = Path(str(self.warehouse) + ".raw.sqlite")
        with connection(self.source) as conn:
            conn.execute(f"CREATE TABLE sales_events ({RAW_COLUMNS},updated_at TEXT,is_deleted INTEGER,PRIMARY KEY(event_id))")
        self.write("s1", 10000, "2025-02-01T00:00:00Z")
        self.write("s2", 20000, "2025-02-03T00:00:00Z")

    def write(self, event_id, amount, stamp, *, deleted=0, units=2, kind="sale", cost=None):
        row = (event_id, "2025-01-15", "o-"+event_id, "c1", "p1", amount,
               int(amount * 0.6) if cost is None else cost, units, kind,
               "Synthetic Co", "Trade", "West", "Cable", "Electrical", stamp, deleted)
        with connection(self.source) as conn:
            conn.execute(f"INSERT OR REPLACE INTO sales_events VALUES ({','.join('?' for _ in row)})", row)

    def go(self, **kwargs):
        return run(str(self.source), str(self.warehouse), **kwargs)

    def query(self, sql, db=None):
        with connection(db or self.warehouse) as conn:
            return conn.execute(sql).fetchall()

    def test_initial_load_and_independent_totals(self):
        result = self.go()
        self.assertEqual(result["active_rows"], 2)
        self.assertEqual(result["net_revenue_cents"], 30000)
        self.assertEqual(self.query("SELECT * FROM daily_sales"), [("2025-01-15", 30000, 18000, 12000, 4, 2)])
        self.assertTrue(self.raw.is_file())
        self.assertEqual(self.query("SELECT COUNT(*) FROM sales_events", self.raw), [(2,)])

    def test_rerun_is_idempotent(self):
        self.go()
        before = self.query("SELECT * FROM published_sales ORDER BY event_id")
        result = self.go()
        self.assertEqual(result["source_rows"], 1)  # Cursor overlap excludes the older s1.
        self.assertEqual(before, self.query("SELECT * FROM published_sales ORDER BY event_id"))
        self.assertEqual(self.query("SELECT COUNT(*) FROM sales_events", self.raw), [(2,)])

    def test_overlap_captures_late_event_and_update(self):
        self.go()
        self.write("s1", 12000, "2025-02-02T03:00:00Z")
        self.write("s3", 5000, "2025-02-02T01:00:00Z")
        result = self.go()
        self.assertEqual(result["active_rows"], 3)
        self.assertEqual(result["net_revenue_cents"], 37000)
        self.assertEqual(result["watermark"], "2025-02-03T00:00:00Z")

    def test_soft_delete_removes_published_fact_but_keeps_tombstone(self):
        self.go()
        self.write("s2", 20000, "2025-02-04T00:00:00Z", deleted=1)
        result = self.go()
        self.assertEqual(result["active_rows"], 1)
        self.assertEqual(result["net_revenue_cents"], 10000)
        self.assertEqual(self.query("SELECT is_deleted FROM sales_events WHERE event_id='s2'", self.raw), [(1,)])

    def test_return_is_signed_and_reconciles(self):
        self.write("r1", -1000, "2025-02-04T00:00:00Z", kind="return", units=-1, cost=-600)
        result = self.go()
        self.assertEqual(result["net_revenue_cents"], 29000)
        self.assertEqual(self.query("SELECT gross_margin_cents,units FROM daily_sales"), [(11600, 3)])

    def test_failure_after_raw_rolls_back_raw_publish_and_cursor(self):
        self.go()
        old_state = self.query("SELECT * FROM pipeline_state")
        self.write("s3", 5000, "2025-02-04T00:00:00Z")
        with self.assertRaisesRegex(RuntimeError, "after raw"):
            self.go(inject_failure="after_raw")
        self.assertEqual(self.query("SELECT * FROM pipeline_state"), old_state)
        self.assertEqual(self.query("SELECT COUNT(*) FROM published_sales"), [(2,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM sales_events", self.raw), [(2,)])
        self.assertEqual(self.query("SELECT status FROM pipeline_runs ORDER BY rowid"), [("succeeded",), ("failed",)])
        self.assertEqual(self.go()["net_revenue_cents"], 35000)

    def test_failure_before_commit_keeps_last_good_marts(self):
        self.go()
        old_mart = self.query("SELECT * FROM daily_sales")
        self.write("s3", 5000, "2025-02-04T00:00:00Z")
        with self.assertRaisesRegex(RuntimeError, "before commit"):
            self.go(inject_failure="before_publish")
        self.assertEqual(old_mart, self.query("SELECT * FROM daily_sales"))
        self.assertEqual(self.go()["net_revenue_cents"], 35000)

    def test_quality_failure_does_not_publish(self):
        self.go()
        self.write("bad", 5000, "2025-02-04T00:00:00Z", kind="return", units=1)
        with self.assertRaisesRegex(ValueError, "signed sale/return"):
            self.go()
        self.assertEqual(self.query("SELECT SUM(net_revenue_cents) FROM published_sales"), [(30000,)])
        self.assertEqual(self.query("SELECT watermark FROM pipeline_state"), [("2025-02-03T00:00:00Z",)])

    def test_duplicate_source_batch_is_rejected(self):
        with connection(self.source) as conn:
            conn.executescript("ALTER TABLE sales_events RENAME TO base; CREATE VIEW sales_events AS SELECT * FROM base UNION ALL SELECT * FROM base WHERE event_id='s1';")
        with self.assertRaisesRegex(ValueError, "duplicate event_id"):
            self.go()
        self.assertEqual(self.query("SELECT COUNT(*) FROM published_sales"), [(0,)])

    def test_full_refresh_recovers_updates_outside_overlap(self):
        self.go()
        self.write("s1", 9000, "2025-02-01T01:00:00Z")
        self.assertEqual(self.go()["net_revenue_cents"], 30000)
        self.assertEqual(self.go(full_refresh=True)["net_revenue_cents"], 29000)

    def test_stale_overlap_record_cannot_overwrite_newer_raw(self):
        self.go()
        self.write("s2", 999, "2025-02-02T05:00:00Z")
        self.assertEqual(self.go()["net_revenue_cents"], 30000)

    def test_full_refresh_resets_cursor_for_replaced_source(self):
        self.go()
        with connection(self.source) as conn:
            conn.execute("DELETE FROM sales_events WHERE event_id='s2'")
        result = self.go(full_refresh=True)
        self.assertEqual(result["watermark"], "2025-02-01T00:00:00Z")
        self.assertEqual(result["active_rows"], 1)
        self.write("s3", 5000, "2025-02-01T01:00:00Z")
        self.assertEqual(self.go()["net_revenue_cents"], 15000)

    def test_empty_full_refresh_clears_marts_and_cursor(self):
        self.go()
        with connection(self.source) as conn:
            conn.execute("DELETE FROM sales_events")
        result = self.go(full_refresh=True)
        self.assertEqual(result["active_rows"], 0)
        self.assertEqual(result["net_revenue_cents"], 0)
        self.assertIsNone(result["watermark"])
        self.assertEqual(self.query("SELECT COUNT(*) FROM daily_sales"), [(0,)])

    def test_future_timestamp_batch_cannot_poison_cursor_or_publication(self):
        with patch("projects.data_platform.pipeline.now", return_value="2025-02-05T00:00:00Z"):
            self.go()
            state = self.query("SELECT * FROM pipeline_state")
            published = self.query("SELECT * FROM published_sales ORDER BY event_id")
            raw = self.query("SELECT * FROM sales_events ORDER BY event_id", self.raw)
            self.write("good", 5000, "2025-02-04T00:00:00Z")
            self.write("future", 6000, "2099-01-01T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "clock-skew tolerance"):
                self.go()
            self.assertEqual(self.query("SELECT * FROM pipeline_state"), state)
            self.assertEqual(self.query("SELECT * FROM published_sales ORDER BY event_id"), published)
            self.assertEqual(self.query("SELECT * FROM sales_events ORDER BY event_id", self.raw), raw)
            with connection(self.source) as conn:
                conn.execute("DELETE FROM sales_events WHERE event_id='future'")
            self.assertEqual(self.go()["net_revenue_cents"], 35000)

    def test_clock_skew_boundary_is_explicit_and_inclusive(self):
        with patch("projects.data_platform.pipeline.now", return_value="2025-02-05T00:00:00Z"):
            self.write("boundary", 5000, "2025-02-05T00:05:00Z")
            self.assertEqual(self.go()["net_revenue_cents"], 35000)
            self.write("beyond", 6000, "2025-02-05T00:05:01Z")
            with self.assertRaisesRegex(ValueError, "clock-skew tolerance"):
                self.go()

    def test_snapshot_adapter(self):
        with connection(self.source) as conn:
            conn.executescript("ALTER TABLE sales_events RENAME TO fixture; CREATE VIEW v_sales AS SELECT " + ",".join(FIELDS) + " FROM fixture;")
        result = self.go()
        self.assertEqual(result["mode"], "static_snapshot")
        self.assertEqual(result["net_revenue_cents"], 30000)
        self.assertEqual(self.go()["active_rows"], 2)

    def test_invalid_calendar_date_and_fractional_money_rejected(self):
        for column, value in [("event_date", "2025-02-30"), ("net_revenue_cents", 12.5)]:
            with self.subTest(column=column):
                with connection(self.source) as conn:
                    conn.execute(f"UPDATE sales_events SET {column}=? WHERE event_id='s1'", (value,))
                with self.assertRaises(ValueError):
                    self.go(full_refresh=True)
                # Restore fixture for next subtest.
                self.write("s1", 10000, "2025-02-01T00:00:00Z")

    def test_source_raw_warehouse_must_be_distinct(self):
        with self.assertRaisesRegex(ValueError, "separate files"):
            run(str(self.source), str(self.source))


if __name__ == "__main__":
    unittest.main()
