from functools import partial
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from portfolio_shared.data import generate, read_only
from projects.ai_analytics.engine import answer
from projects.analytics_dashboard.metrics import dashboard
from projects.data_platform.pipeline import run
from server import Handler


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"source.sqlite"
        cls.ref=generate(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_three_projects_reconcile(self):
        report=dashboard(str(self.path))
        assistant=answer("2025 revenue summary",str(self.path))
        self.assertEqual(assistant["status"],"ok")
        self.assertEqual(assistant["metrics"]["net_revenue_cents"],self.ref["annual"]["2025"]["net_revenue_cents"])
        self.assertEqual(report["summary"]["revenue_cents"],self.ref["net_revenue_cents"])
        warehouse=Path(self.temp.name)/"warehouse.sqlite"
        first=run(str(self.path),str(warehouse))
        second=run(str(self.path),str(warehouse))
        self.assertEqual(first["net_revenue_cents"],second["net_revenue_cents"])
        with sqlite3.connect(warehouse) as db:
            actual=db.execute("SELECT SUM(net_revenue_cents) FROM published_sales").fetchone()[0]
        self.assertEqual(actual,report["summary"]["revenue_cents"])
        self.assertEqual(report["summary"]["receivables_cents"],self.ref["outstanding_cents"])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"source.sqlite"
        generate(cls.path)
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,database=cls.path))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=10)
        try:
            connection.request(method,path,body=body,headers=headers or {})
            response=connection.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:
            connection.close()

    def test_public_pages_and_health(self):
        for path in ("/","/assistant","/pipeline","/dashboard","/dashboard/app.js","/dashboard/styles.css","/api/health"):
            with self.subTest(path=path):
                status,headers,body=self.request("GET",path)
                self.assertEqual(status,200)
                self.assertTrue(body)
                self.assertEqual(headers["X-Content-Type-Options"],"nosniff")

    def test_assistant_round_trip(self):
        status,_,body=self.request("POST","/api/ask",json.dumps({"question":"2025 revenue summary"}),{"Content-Type":"application/json"})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["status"],"ok")

    def test_dashboard_json(self):
        status,_,body=self.request("GET","/api/dashboard")
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)["metadata"]["synthetic"])

    def test_invalid_requests(self):
        for payload in ("not-json","[]",'{"question":10}','{"question":""}'):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST","/api/ask",payload,{"Content-Type":"application/json"})[0],400)
        self.assertEqual(self.request("POST","/api/ask","x",{"Content-Type":"text/plain"})[0],415)
        self.assertEqual(self.request("POST","/api/ask","x"*5000,{"Content-Type":"application/json"})[0],413)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.request("POST","/api/ask",'{"question":"revenue"}',{"Content-Type":"application/json","Origin":"https://other.example"})[0],403)

    def test_private_files_and_traversal_blocked(self):
        for path in ("/artifacts/distributor.sqlite","/.env","/.git/config","/web/../../README.md","/dashboard/../../server.py","/docs/../server.py"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET",path)[0],404)


if __name__=="__main__":
    unittest.main()
