import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from portfolio_shared.data import AS_OF, export_csv, generate, read_only


class SharedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"demo.sqlite"
        cls.reference=generate(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_ledger_reconciles_to_generator_reference(self):
        with read_only(self.path) as conn:
            actual=conn.execute("SELECT SUM(net_revenue_cents),SUM(cogs_cents) FROM v_sales").fetchone()
            self.assertEqual(tuple(actual),(self.reference["net_revenue_cents"],self.reference["cogs_cents"]))
            rows=conn.execute("SELECT substr(event_date,1,4), SUM(net_revenue_cents), SUM(cogs_cents) FROM v_sales GROUP BY 1").fetchall()
            for year,revenue,cost in rows:
                self.assertEqual(revenue,self.reference["annual"][year]["net_revenue_cents"])
                self.assertEqual(cost,self.reference["annual"][year]["cogs_cents"])

    def test_receivables_reconcile_without_join_multiplication(self):
        with read_only(self.path) as conn:
            actual=conn.execute("SELECT SUM(invoice_amount_cents),SUM(credit_cents),SUM(paid_cents),SUM(outstanding_cents) FROM v_receivables").fetchone()
            expected=tuple(self.reference[x] for x in ("invoice_amount_cents","credit_cents","paid_cents","outstanding_cents"))
            self.assertEqual(tuple(actual),expected)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM v_receivables WHERE outstanding_cents<0").fetchone()[0],0)

    def test_valid_relationships_and_return_limits(self):
        with read_only(self.path) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(),[])
            self.assertEqual(conn.execute("SELECT count(*) FROM returns r JOIN order_lines l USING(line_id) WHERE r.quantity>l.quantity OR r.refund_cents>l.line_amount_cents").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sales_ledger WHERE event_date>?",(AS_OF,)).fetchone()[0],0)

    def test_read_only_connection_rejects_writes(self):
        with read_only(self.path) as conn:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM sales_ledger")

    def test_generation_is_reproducible(self):
        second=Path(self.temp.name)/"second.sqlite"
        self.assertEqual(generate(second),self.reference)
        with read_only(self.path) as a, read_only(second) as b:
            self.assertEqual(a.execute("SELECT * FROM sales_ledger ORDER BY event_id").fetchall(),b.execute("SELECT * FROM sales_ledger ORDER BY event_id").fetchall())

    def test_csv_exports_include_checksums(self):
        result=export_csv(self.path,Path(self.temp.name)/"csv")
        self.assertEqual(len(result["files"]),9)
        self.assertEqual(len(result["files"]["sales_ledger"]["sha256"]),64)


if __name__=="__main__":
    unittest.main()
