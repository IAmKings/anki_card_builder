"""URL 抓取：SSRF 防护、重定向、超时、大小/类型限制与 URL ingest。"""

import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request

from ankicards import ingest as ingest_mod
from ankicards.cli import main
from ankicards.web import WebError, _SafeRedirect, fetch_html

PAGE = "<html><body><h1>标题</h1><p>正文</p><script>bad()</script></body></html>"


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue() + err.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/page":
            self._send(200, PAGE.encode())
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/json":
            self._send(200, b'{"a": 1}', "application/json")
        elif self.path == "/big":
            self._send(200, b"x" * 100)
        elif self.path == "/slow":
            time.sleep(0.3)
            self._send(200, PAGE.encode())
        elif self.path == "/error":
            self._send(404, b"not found")
        else:
            self._send(404, b"not found")


class FetchWebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_private_url_is_blocked_by_default(self):
        with self.assertRaises(WebError) as ctx:
            fetch_html(self.base + "/page")
        self.assertIn("内网", str(ctx.exception))

    def test_allow_private_network_fetches_and_strips_script(self):
        fetched = fetch_html(self.base + "/page", allow_private_network=True)
        self.assertEqual(fetched.final_url, self.base + "/page")
        self.assertEqual(fetched.content_type, "text/html")
        blocks = list(ingest_mod.iter_html_blocks(fetched.content))
        self.assertEqual([b.text for b in blocks], ["标题", "正文"])

    def test_redirect_final_url(self):
        fetched = fetch_html(self.base + "/redirect", allow_private_network=True)
        self.assertEqual(fetched.final_url, self.base + "/page")

    def test_non_html_content_type_rejected(self):
        with self.assertRaises(WebError) as ctx:
            fetch_html(self.base + "/json", allow_private_network=True)
        self.assertIn("不是 HTML", str(ctx.exception))

    def test_max_bytes(self):
        with self.assertRaises(WebError) as ctx:
            fetch_html(self.base + "/big", allow_private_network=True, max_bytes=10)
        self.assertIn("上限", str(ctx.exception))

    def test_timeout(self):
        with self.assertRaises(WebError) as ctx:
            fetch_html(self.base + "/slow", allow_private_network=True, timeout=0.05)
        self.assertIn("超时", str(ctx.exception))

    def test_http_error(self):
        with self.assertRaises(WebError) as ctx:
            fetch_html(self.base + "/error", allow_private_network=True)
        self.assertIn("HTTP 404", str(ctx.exception))

    def test_redirect_to_private_is_blocked(self):
        handler = _SafeRedirect(allow_private_network=False)
        req = Request("http://example.com/")
        with self.assertRaises(WebError):
            handler.redirect_request(req, None, 302, "Found", {},
                                     "http://10.0.0.1/secret")


class UrlIngestTest(FetchWebTest):
    def test_ingest_url_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "web.json"
            result = ingest_mod.ingest_url(self.base + "/page", out=out,
                                           allow_private_network=True)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "web")
            self.assertEqual(data["source"], self.base + "/page")
            self.assertEqual(data["final_url"], self.base + "/page")
            self.assertIsNone(data["source_sha256"])
            self.assertEqual(len(data["content_sha256"]), 64)
            self.assertEqual(data["units"][0]["locator"], "block:1")
            self.assertEqual(result.out_path, out.resolve())

    def test_ingest_dispatch_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest_mod.ingest(self.base + "/page", out=Path(tmp) / "x.json",
                                       allow_private_network=True)
            self.assertEqual(result.manifest["format"], "web")

    def test_cli_ingest_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "web.json"
            code, output = run_cli(["ingest", self.base + "/page",
                                    "--allow-private-network", "--out", str(out)])
            self.assertEqual(code, 0, output)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
