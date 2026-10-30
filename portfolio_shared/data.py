"""Deterministic fictional distributor data. No client records or client code."""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "artifacts" / "distributor.sqlite"
AS_OF = "2025-12-31"
DATA_VERSION = "1.0.0"
SEED = 41729

SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY,name TEXT NOT NULL,segment TEXT NOT NULL,region TEXT NOT NULL);
CREATE TABLE products(product_id INTEGER PRIMARY KEY,sku TEXT NOT NULL UNIQUE,name TEXT NOT NULL,category TEXT NOT NULL,unit_cost_cents INTEGER NOT NULL,list_price_cents INTEGER NOT NULL);
CREATE TABLE orders(order_id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers,order_date TEXT NOT NULL,status TEXT NOT NULL);
CREATE TABLE order_lines(line_id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders,product_id INTEGER NOT NULL REFERENCES products,quantity INTEGER NOT NULL CHECK(quantity>0),unit_price_cents INTEGER NOT NULL,unit_cost_cents INTEGER NOT NULL,discount_bps INTEGER NOT NULL,line_amount_cents INTEGER NOT NULL);
CREATE TABLE returns(return_id INTEGER PRIMARY KEY,line_id INTEGER NOT NULL REFERENCES order_lines,return_date TEXT NOT NULL,quantity INTEGER NOT NULL,refund_cents INTEGER NOT NULL,cost_reversal_cents INTEGER NOT NULL);
CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL UNIQUE REFERENCES orders,invoice_date TEXT NOT NULL,due_date TEXT NOT NULL);
CREATE TABLE payments(payment_id INTEGER PRIMARY KEY,invoice_id INTEGER NOT NULL REFERENCES invoices,payment_date TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0));
CREATE TABLE inventory(snapshot_date TEXT NOT NULL,product_id INTEGER NOT NULL REFERENCES products,on_hand_units INTEGER NOT NULL,reorder_point INTEGER NOT NULL,PRIMARY KEY(snapshot_date,product_id));
CREATE TABLE sales_ledger(event_id TEXT PRIMARY KEY,event_date TEXT NOT NULL,order_id INTEGER NOT NULL,customer_id INTEGER NOT NULL,product_id INTEGER NOT NULL,net_revenue_cents INTEGER NOT NULL,cogs_cents INTEGER NOT NULL,units INTEGER NOT NULL,kind TEXT NOT NULL);
CREATE VIEW v_sales AS SELECT s.*, c.name AS customer_name,c.segment,c.region,p.name AS product_name,p.category FROM sales_ledger s JOIN customers c USING(customer_id) JOIN products p USING(product_id);
CREATE VIEW v_receivables AS
WITH totals AS (SELECT order_id,SUM(line_amount_cents) amount FROM order_lines GROUP BY order_id),
credits AS (SELECT l.order_id,SUM(r.refund_cents) amount FROM returns r JOIN order_lines l USING(line_id) WHERE r.return_date<='2025-12-31' GROUP BY l.order_id),
paid AS (SELECT invoice_id,SUM(amount_cents) amount FROM payments WHERE payment_date<='2025-12-31' GROUP BY invoice_id)
SELECT i.invoice_id,o.customer_id,c.name customer_name,c.segment,c.region,i.invoice_date,i.due_date,
t.amount invoice_amount_cents,COALESCE(cr.amount,0) credit_cents,COALESCE(pa.amount,0) paid_cents,
t.amount-COALESCE(cr.amount,0)-COALESCE(pa.amount,0) outstanding_cents,
MAX(0,CAST(julianday('2025-12-31')-julianday(i.due_date) AS INTEGER)) days_overdue
FROM invoices i JOIN orders o USING(order_id) JOIN customers c USING(customer_id) JOIN totals t USING(order_id)
LEFT JOIN credits cr USING(order_id) LEFT JOIN paid pa USING(invoice_id)
WHERE i.invoice_date<='2025-12-31';
CREATE INDEX idx_sales_date ON sales_ledger(event_date);
"""


def generate(path: str | Path = DEFAULT_DB) -> dict:
    """Write a complete deterministic DB atomically; return reference metrics."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".building.sqlite")
    temporary.unlink(missing_ok=True)
    rng = random.Random(SEED)
    conn = sqlite3.connect(temporary)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO metadata VALUES (?,?)", [("version",DATA_VERSION),("as_of",AS_OF),("seed",str(SEED)),("source","100% synthetic")])
        segments = ["Industrial", "Retail", "Hospitality", "Healthcare"]
        regions = ["North", "South", "East", "West"]
        for customer_id in range(1,81):
            conn.execute("INSERT INTO customers VALUES (?,?,?,?)",(customer_id,f"Demo Customer {customer_id:03d}",segments[(customer_id-1)%4],regions[(customer_id//4)%4]))
        categories = ["Electrical", "Safety", "Packaging", "Maintenance"]
        products = {}
        for product_id in range(1,25):
            price = rng.randint(80,340)*100
            cost = price*rng.randint(56,77)//100
            category = categories[(product_id-1)%4]
            products[product_id]=(price,cost,category)
            conn.execute("INSERT INTO products VALUES (?,?,?,?,?,?)",(product_id,f"DEMO-{product_id:03d}",f"{category} item {product_id:02d}",category,cost,price))
        as_of = date.fromisoformat(AS_OF)
        reference = {"source":"100% synthetic", "data_version":DATA_VERSION,"as_of":AS_OF,"annual":{},"net_revenue_cents":0,"cogs_cents":0,"invoice_amount_cents":0,"credit_cents":0,"paid_cents":0,"outstanding_cents":0}
        order_id = line_id = return_id = payment_id = 0
        for year in (2024,2025):
            annual = reference["annual"].setdefault(str(year),{"net_revenue_cents":0,"cogs_cents":0})
            for month in range(1,13):
                count=195+(month%4)*5+(12 if year==2025 else 0)
                for _ in range(count):
                    order_id+=1
                    ordered=date(year,month,rng.randint(1,calendar.monthrange(year,month)[1]))
                    customer=rng.randint(1,80)
                    conn.execute("INSERT INTO orders VALUES (?,?,?,?)",(order_id,customer,ordered.isoformat(),"invoiced"))
                    due=ordered+timedelta(days=rng.choice([30,30,45,60]))
                    conn.execute("INSERT INTO invoices VALUES (?,?,?,?)",(order_id,order_id,ordered.isoformat(),due.isoformat()))
                    invoice_total=credits_total=0
                    for _ in range(rng.choice([1,2,2,3])):
                        line_id+=1
                        product=rng.randint(1,24)
                        price,cost,category=products[product]
                        qty=rng.randint(20,80)
                        discount=rng.choice([0,0,200,500,800])
                        # Deliberate synthetic margin squeeze, not a measured client result.
                        if year==2025 and month>=7 and category=="Electrical":
                            cost=cost*116//100
                            discount+=500
                        amount=(qty*price*(10000-discount)+5000)//10000
                        cogs=qty*cost
                        conn.execute("INSERT INTO order_lines VALUES (?,?,?,?,?,?,?,?)",(line_id,order_id,product,qty,price,cost,discount,amount))
                        conn.execute("INSERT INTO sales_ledger VALUES (?,?,?,?,?,?,?,?,?)",(f"sale-{line_id}",ordered.isoformat(),order_id,customer,product,amount,cogs,qty,"sale"))
                        invoice_total+=amount
                        annual["net_revenue_cents"]+=amount
                        annual["cogs_cents"]+=cogs
                        if rng.random()<0.07:
                            returned=ordered+timedelta(days=rng.randint(2,25))
                            if returned<=as_of:
                                return_id+=1
                                units=rng.randint(1,max(1,qty//3))
                                refund=(amount*units+qty//2)//qty
                                reversed_cost=cost*units
                                conn.execute("INSERT INTO returns VALUES (?,?,?,?,?,?)",(return_id,line_id,returned.isoformat(),units,refund,reversed_cost))
                                conn.execute("INSERT INTO sales_ledger VALUES (?,?,?,?,?,?,?,?,?)",(f"return-{return_id}",returned.isoformat(),order_id,customer,product,-refund,-reversed_cost,-units,"return"))
                                credits_total+=refund
                                # Returns are recognized on their posting dates, including year boundaries.
                                return_year=str(returned.year)
                                reference["annual"].setdefault(return_year,{"net_revenue_cents":0,"cogs_cents":0})
                                reference["annual"][return_year]["net_revenue_cents"]-=refund
                                reference["annual"][return_year]["cogs_cents"]-=reversed_cost
                    receivable=invoice_total-credits_total
                    paid=0
                    # Payment is simulated after credit notes; do not create overpaid balances.
                    if (as_of-ordered).days>70:
                        payment_date=max(ordered+timedelta(days=rng.randint(27,65)),ordered+timedelta(days=26))
                        if customer%11==0 and year==2025 and month>=8:
                            paid=receivable//2
                        else:
                            paid=receivable
                    elif (as_of-ordered).days>30:
                        payment_date=ordered+timedelta(days=29)
                        paid=receivable*rng.choice([0,50,100])//100
                    else:
                        payment_date=ordered
                    if paid:
                        payment_id+=1
                        conn.execute("INSERT INTO payments VALUES (?,?,?,?)",(payment_id,order_id,payment_date.isoformat(),paid))
                    reference["invoice_amount_cents"]+=invoice_total
                    reference["credit_cents"]+=credits_total
                    reference["paid_cents"]+=paid
        for product,(price,cost,category) in products.items():
            for month in range(1,13):
                snapshot=date(2025,month,calendar.monthrange(2025,month)[1]).isoformat()
                on_hand=rng.randint(50,700)
                if product%7==0 and month>=10:
                    on_hand+=1600
                conn.execute("INSERT INTO inventory VALUES (?,?,?,?)",(snapshot,product,on_hand,180))
        reference["net_revenue_cents"]=sum(x["net_revenue_cents"] for x in reference["annual"].values())
        reference["cogs_cents"]=sum(x["cogs_cents"] for x in reference["annual"].values())
        reference["outstanding_cents"]=reference["invoice_amount_cents"]-reference["credit_cents"]-reference["paid_cents"]
        reference["counts"]={"orders":order_id,"order_lines":line_id,"returns":return_id,"payments":payment_id}
        conn.execute("INSERT INTO metadata VALUES (?,?)",("reference_metrics",json.dumps(reference,sort_keys=True)))
        conn.commit()
    except Exception:
        conn.close()
        temporary.unlink(missing_ok=True)
        raise
    conn.close()
    temporary.replace(destination)
    return reference


def ensure_database(path: str | Path | None = None) -> Path:
    path=Path(path) if path else DEFAULT_DB
    if not path.exists():
        generate(path)
    return path


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def read_only(path: str | Path | None = None) -> sqlite3.Connection:
    db=ensure_database(path)
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,factory=ClosingConnection)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def export_csv(database: str | Path, directory: str | Path) -> dict:
    """Export a typed AWS-friendly CSV bundle; metadata is excluded."""
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    manifest={"source":"100% synthetic","data_version":DATA_VERSION,"files":{}}
    with read_only(database) as conn:
        for table in ("customers","products","orders","order_lines","returns","invoices","payments","inventory","sales_ledger"):
            rows=conn.execute(f"SELECT * FROM {table} ORDER BY 1")
            path=directory/f"{table}.csv"
            with path.open("w",newline="") as handle:
                writer=csv.writer(handle)
                writer.writerow([col[0] for col in rows.description])
                writer.writerows(rows)
            manifest["files"][table]={"path":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",default=str(DEFAULT_DB))
    parser.add_argument("--export-csv")
    args=parser.parse_args()
    path=ensure_database(args.database)
    with read_only(path) as conn:
        print(json.dumps(json.loads(conn.execute("SELECT value FROM metadata WHERE key='reference_metrics'").fetchone()[0]),indent=2))
    if args.export_csv:
        export_csv(path,args.export_csv)


if __name__=="__main__":
    main()
