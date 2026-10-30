"""Independent, hand-calculated fixtures; stdlib only."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

try:
    from .metrics import dashboard
except ImportError:  # unittest discovery with this folder as the top-level path
    from metrics import dashboard


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "fixture.db")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE v_sales(event_id TEXT,event_date TEXT,order_id TEXT,customer_id TEXT,product_id TEXT,
                 net_revenue_cents INTEGER,cogs_cents INTEGER,units INTEGER,kind TEXT,customer_name TEXT,
                 segment TEXT,region TEXT,product_name TEXT,category TEXT);
                CREATE TABLE v_receivables(invoice_id TEXT,customer_id TEXT,customer_name TEXT,segment TEXT,
                 region TEXT,invoice_date TEXT,due_date TEXT,invoice_amount_cents INTEGER,credit_cents INTEGER,
                 paid_cents INTEGER,outstanding_cents INTEGER,days_overdue INTEGER);
                CREATE TABLE products(product_id TEXT,sku TEXT,name TEXT,category TEXT,unit_cost_cents INTEGER,list_price_cents INTEGER);
                CREATE TABLE inventory(snapshot_date TEXT,product_id TEXT,on_hand_units INTEGER,reorder_point INTEGER);
                INSERT INTO v_sales VALUES
                 ('a','2025-01-01','o1','c1','p1',10000,6000,10,'sale','A','Retail','East','P','Tools'),
                 ('b','2025-01-02','o2','c2','p2',20000,14000,20,'sale','B','Trade','West','Q','Safety'),
                 ('c','2025-02-01','o1','c1','p1',-2000,-1200,-2,'return','A','Retail','East','P','Tools'),
                 ('future','2026-01-01','o3','c1','p1',99999,100,1,'sale','A','Retail','East','P','Tools');
                INSERT INTO v_receivables VALUES
                 ('i1','c1','A','Retail','East','2025-12-01','2025-12-31',10000,2000,3000,5000,0),
                 ('i2','c2','B','Trade','West','2025-11-01','2025-12-01',10000,0,4000,6000,30),
                 ('i3','c2','B','Trade','West','2025-10-01','2025-11-30',7000,0,0,7000,31),
                 ('paid','c1','A','Retail','East','2025-01-01','2025-02-01',1000,0,1000,0,333);
                INSERT INTO products VALUES('p1','SKU1','P','Tools',600,1000);
                INSERT INTO inventory VALUES('2025-11-30','p1',99,5),('2025-12-31','p1',4,5),('2026-01-01','p1',1000,5);
            """)

    def tearDown(self):
        self.tmp.cleanup()

    def test_signed_revenue_and_weighted_margin(self):
        data = dashboard(self.path)
        # $100 + $200 - $20 = $280; cost $60 + $140 - $12 = $188.
        self.assertEqual(data["summary"]["revenue_cents"], 28000)
        self.assertEqual(data["summary"]["gross_profit_cents"], 9200)
        self.assertAlmostEqual(data["summary"]["gross_margin_percent"], 32.8571, places=4)
        self.assertAlmostEqual(data["summary"]["return_credit_percent"], 6.6667, places=4)
        self.assertEqual(data["monthly"][1]["revenue_cents"], -2000)
        self.assertEqual(len(data["sales"]), 3)

    def test_receivables_partial_payment_and_aging_boundaries(self):
        data = dashboard(self.path)
        self.assertEqual(data["summary"]["receivables_cents"], 18000)
        self.assertEqual(data["summary"]["overdue_cents"], 13000)
        self.assertEqual([r["outstanding_cents"] for r in data["aging"]], [5000,6000,7000,0,0])
        self.assertEqual(len(data["receivables"]), 3)

    def test_inventory_snapshot_cutoff_and_cost(self):
        data = dashboard(self.path)
        self.assertEqual(data["summary"]["inventory_cost_cents"], 2400)
        self.assertEqual(data["inventory"][0]["on_hand_units"], 4)

    def test_zero_denominator_and_empty_result(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM v_sales")
            db.execute("DELETE FROM v_receivables")
        data = dashboard(self.path)
        self.assertIsNone(data["summary"]["gross_margin_percent"])
        self.assertIsNone(data["summary"]["return_credit_percent"])
        self.assertEqual(data["monthly"], [])
        self.assertEqual(data["summary"]["receivables_cents"], 0)

    def test_aging_all_boundaries(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM v_receivables")
            for index, days in enumerate([-1,0,1,30,31,60,61,90,91]):
                db.execute("INSERT INTO v_receivables VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (str(index),'c1','A','Retail','East','2025-01-01','2025-01-31',100,0,0,100,days))
        self.assertEqual([r["outstanding_cents"] for r in dashboard(self.path)["aging"]], [200,200,200,200,100])


if __name__ == "__main__":
    unittest.main()
