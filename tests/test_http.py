"""共通 HTTP クライアント（リトライ条件・接続の使い回し・プロキシ）の検証。"""

import base64
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

import pytest

from hellow_jev.classifiers import _http
from hellow_jev.classifiers._http import HTTPClient, _is_dropped, _wait_sec


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


class _KeepAliveHandler(BaseHTTPRequestHandler):
    """HTTP/1.1 で接続を保持するサーバ。close_after 件目の応答後に予告なしで接続を閉じる。"""

    protocol_version = "HTTP/1.1"
    connections: list = []  # 接続ごとの client_address
    requests: list = []  # リクエストごとの (client_address, path, headers)
    close_after = 0  # 0 = 閉じない

    def setup(self):
        super().setup()
        type(self).connections.append(self.client_address)

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        type(self).requests.append((self.client_address, self.path, dict(self.headers)))
        data = json.dumps({"n": len(type(self).requests)}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        if type(self).close_after and len(type(self).requests) == type(self).close_after:
            self.close_connection = True  # Connection: close を返さずに閉じる（keep-alive タイムアウト相当）

    def log_message(self, *args):
        pass


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(_http.time, "sleep", lambda s: None)


@pytest.fixture
def server(no_sleep):
    _Handler.statuses = []
    _Handler.calls = 0
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def keepalive_server():
    _KeepAliveHandler.connections = []
    _KeepAliveHandler.requests = []
    _KeepAliveHandler.close_after = 0
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _KeepAliveHandler)
    httpd.daemon_threads = True  # 保持中の接続があってもテスト終了を妨げない
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def _url(httpd, path="/v1/x"):
    return f"http://127.0.0.1:{httpd.server_port}{path}"


def test_retries_5xx_and_counts_attempts(server):
    _Handler.statuses = [503, 429]
    resp = HTTPClient(timeout=5, max_retries=3).post(server, {}, {})
    assert resp.body == {"ok": True}
    assert resp.attempts == 3


def test_does_not_retry_4xx(server):
    _Handler.statuses = [404]
    with pytest.raises(RuntimeError, match="HTTP 404"):
        HTTPClient(timeout=5, max_retries=3).post(server, {}, {})
    assert _Handler.calls == 1


def test_gives_up_after_max_retries(server):
    _Handler.statuses = [500, 500, 500]
    with pytest.raises(RuntimeError, match="HTTP 500"):
        HTTPClient(timeout=5, max_retries=2).post(server, {}, {})
    assert _Handler.calls == 3


def test_retries_connection_refused(no_sleep):
    with socket.socket() as s:  # 空きポートを取って閉じる → 接続拒否になる
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(RuntimeError, match="request failed"):
        HTTPClient(timeout=5, max_retries=1).post(f"http://127.0.0.1:{port}", {}, {})


def test_server_closing_each_response_is_handled(server):
    # HTTP/1.0 のサーバは毎回閉じる → 毎回張り直すが、エラーやリトライにはならない
    client = HTTPClient(timeout=5, max_retries=0)
    for _ in range(3):
        resp = client.post(server, {}, {})
        assert resp.attempts == 1 and resp.new_connection


def test_connection_is_reused(keepalive_server):
    client = HTTPClient(timeout=5, max_retries=0)
    responses = [client.post(_url(keepalive_server), {"X-Test": "1"}, {"i": i}) for i in range(3)]
    assert [r.new_connection for r in responses] == [True, False, False]
    assert [r.body["n"] for r in responses] == [1, 2, 3]
    assert len(_KeepAliveHandler.connections) == 1
    assert client._conn.sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
    _, path, headers = _KeepAliveHandler.requests[0]
    assert path == "/v1/x"
    assert headers["X-Test"] == "1"
    assert headers["User-Agent"] == "hellow-jev"


def test_reconnects_when_server_dropped_idle_connection(keepalive_server):
    _KeepAliveHandler.close_after = 1
    client = HTTPClient(timeout=5, max_retries=0)  # リトライなしでも成功すること
    assert client.post(_url(keepalive_server), {}, {}).new_connection
    deadline = time.monotonic() + 5
    while not _is_dropped(client._conn.sock):  # サーバ側のクローズが届くまで待つ
        assert time.monotonic() < deadline
        time.sleep(0.01)
    resp = client.post(_url(keepalive_server), {}, {})
    assert resp.attempts == 1 and resp.new_connection
    assert len(_KeepAliveHandler.connections) == 2


def _clear_proxy_env(monkeypatch):
    for name in ("http_proxy", "https_proxy", "no_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)


def test_http_proxy_gets_absolute_url_and_auth(keepalive_server, monkeypatch):
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("http_proxy", f"http://user:p%40ss@127.0.0.1:{keepalive_server.server_port}")
    client = HTTPClient(timeout=5, max_retries=0)
    for _ in range(2):
        client.post("http://api.example.test/v1/x?a=1", {}, {})
    assert len(_KeepAliveHandler.connections) == 1  # プロキシへの接続も使い回す
    _, path, headers = _KeepAliveHandler.requests[0]
    assert path == "http://api.example.test/v1/x?a=1"
    assert headers["Host"] == "api.example.test"
    assert headers["Proxy-Authorization"] == "Basic " + base64.b64encode(b"user:p@ss").decode()


def test_no_proxy_bypasses_proxy(keepalive_server, monkeypatch):
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")  # 使われたら接続できずに失敗する
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    assert HTTPClient(timeout=5, max_retries=0).post(_url(keepalive_server), {}, {}).body == {"n": 1}


def test_wait_sec():
    assert _wait_sec("3", 0) == 3.0
    assert _wait_sec("Wed, 21 Oct 2015 07:28:00 GMT", 2) == 4.0
    assert _wait_sec("100000", 0) == _http.MAX_WAIT_SEC
    assert _wait_sec(None, 1) == 2.0
