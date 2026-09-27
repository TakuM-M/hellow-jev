"""共通 HTTP クライアント（リトライ条件）の検証。"""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hellow_jev.classifiers import _http
from hellow_jev.classifiers._http import _wait_sec, post_json


class _Handler(BaseHTTPRequestHandler):
    statuses: list = []
    calls = 0

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        type(self).calls += 1
        status = type(self).statuses.pop(0) if type(self).statuses else 200
        data = json.dumps({"ok": True}).encode()
        self.send_response(status)
        if status != 200:
            self.send_header("retry-after", "Wed, 21 Oct 2015 07:28:00 GMT")  # HTTP-date 形式
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(_http.time, "sleep", lambda s: None)
    _Handler.statuses = []
    _Handler.calls = 0
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_retries_5xx_and_counts_attempts(server):
    _Handler.statuses = [503, 429]
    resp = post_json(server, {}, {}, timeout=5, max_retries=3)
    assert resp.body == {"ok": True}
    assert resp.attempts == 3


def test_does_not_retry_4xx(server):
    _Handler.statuses = [404]
    with pytest.raises(RuntimeError, match="HTTP 404"):
        post_json(server, {}, {}, timeout=5, max_retries=3)
    assert _Handler.calls == 1


def test_gives_up_after_max_retries(server):
    _Handler.statuses = [500, 500, 500]
    with pytest.raises(RuntimeError, match="HTTP 500"):
        post_json(server, {}, {}, timeout=5, max_retries=2)
    assert _Handler.calls == 3


def test_retries_connection_refused(monkeypatch):
    monkeypatch.setattr(_http.time, "sleep", lambda s: None)
    with socket.socket() as s:  # 空きポートを取って閉じる → 接続拒否になる
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(RuntimeError, match="request failed"):
        post_json(f"http://127.0.0.1:{port}", {}, {}, timeout=5, max_retries=1)


def test_wait_sec():
    assert _wait_sec("3", 0) == 3.0
    assert _wait_sec("Wed, 21 Oct 2015 07:28:00 GMT", 2) == 4.0
    assert _wait_sec("100000", 0) == _http.MAX_WAIT_SEC
    assert _wait_sec(None, 1) == 2.0
