"""Loopback-only local portfolio demonstration server; no cloud calls."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from portfolio_shared.data import AS_OF, DEFAULT_DB, ROOT, ensure_database


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, database=DEFAULT_DB, **kwargs):
        self.database=Path(database)
        super().__init__(*args,**kwargs)

    def send_bytes(self, body: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload, status=200):
        self.send_bytes(json.dumps(payload,allow_nan=False).encode(),"application/json; charset=utf-8",status)

    def do_GET(self):
        route=urlsplit(self.path).path
        if route=="/api/health":
            return self.send_json({"status":"ok","source":"synthetic","as_of":AS_OF})
        if route=="/api/dashboard":
            from projects.analytics_dashboard.metrics import dashboard
            return self.send_json(dashboard(str(self.database)))
        if route=="/api/verification":
            path=ROOT/"artifacts"/"verification.json"
            return self.send_json(json.loads(path.read_text()) if path.exists() else {"status":"not_run"})
        if route in ("/","/index.html"):
            return self.file(ROOT/"web"/"index.html")
        if route in ("/assistant","/assistant/"):
            return self.file(ROOT/"web"/"assistant.html")
        if route in ("/pipeline","/pipeline/"):
            return self.file(ROOT/"web"/"pipeline.html")
        if route in ("/dashboard","/dashboard/"):
            return self.file(ROOT/"projects"/"analytics_dashboard"/"index.html")
        prefixes={"/web/":ROOT/"web","/dashboard/":ROOT/"projects"/"analytics_dashboard","/docs/":ROOT/"docs"}
        for prefix,base in prefixes.items():
            if route.startswith(prefix):
                target=(base/route[len(prefix):]).resolve()
                if not target.is_relative_to(base.resolve()):
                    return self.send_json({"error":"Not found"},404)
                # Serve only explicitly public web/document assets, never source databases.
                if target.suffix.lower() not in (".html",".css",".js",".svg",".png",".md"):
                    return self.send_json({"error":"Not found"},404)
                return self.file(target)
        return self.send_json({"error":"Not found"},404)

    def file(self,path):
        if not path.is_file():
            return self.send_json({"error":"Not found"},404)
        content_type=mimetypes.guess_type(str(path))[0] or "text/plain"
        if path.suffix==".md":
            content_type="text/plain"
        self.send_bytes(path.read_bytes(),content_type+"; charset=utf-8")

    def do_POST(self):
        if urlsplit(self.path).path!="/api/ask":
            return self.send_json({"error":"Not found"},404)
        origin=self.headers.get("Origin")
        allowed_origin=f"http://127.0.0.1:{self.server.server_port}"
        if origin and origin!=allowed_origin:
            return self.send_json({"error":"Origin not allowed"},403)
        if self.headers.get("Content-Type","").split(";")[0]!="application/json":
            return self.send_json({"error":"JSON required"},415)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<1 or length>4096:
                return self.send_json({"error":"Invalid request size"},413)
            payload=json.loads(self.rfile.read(length))
            question=payload.get("question") if isinstance(payload,dict) else None
            if not isinstance(question,str) or not question.strip() or len(question)>1000:
                return self.send_json({"error":"Question must contain 1–1000 characters"},400)
        except (ValueError,TypeError,UnicodeDecodeError):
            return self.send_json({"error":"Invalid JSON request"},400)
        from projects.ai_analytics.engine import answer
        return self.send_json(answer(question,str(self.database)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--database",default=str(DEFAULT_DB))
    args=parser.parse_args()
    database=ensure_database(args.database)
    server=ThreadingHTTPServer(("127.0.0.1",args.port),partial(Handler,database=database))
    print(f"Synthetic portfolio demo: http://127.0.0.1:{args.port}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=="__main__":
    main()
