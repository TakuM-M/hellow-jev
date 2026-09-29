"""分類器共通の JSON POST クライアント（リトライ・接続の使い回し付き）。

Jev / Laya / LLM でリトライ条件が違うと「安定性の差」が実装差で決まってしまうため、
全分類器がこのクライアントを通す。

urllib.request は毎回 `Connection: close` で接続を張り直すので、HTTPS では毎リクエスト
TCP + TLS ハンドシェイクがレイテンシに乗り、warmup でも除けない。ここでは http.client で
接続を保持して使い回す（keep-alive）。プロキシの環境変数（HTTPS_PROXY / NO_PROXY など）は
urllib と同じ規則（urllib.request.getproxies / proxy_bypass）で扱う。リダイレクトは追わない。
"""

from __future__ import annotations

import base64
import http.client
import json
import select
import socket
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import Any

from hellow_jev.util import USER_AGENT

# レート制限・過負荷・一時的なサーバエラー（529 は Anthropic の overloaded）
RETRY_STATUS = {429, 500, 502, 503, 504, 529}
MAX_WAIT_SEC = 60.0  # Retry-After が大きすぎても run が止まり続けないよう上限を設ける


@dataclass
class Response:
    body: dict[str, Any]
    headers: Message
    attempts: int  # 1 = リトライなし
    new_connection: bool  # 成功した試行で接続を張ったか（True なら接続確立の時間がレイテンシに乗る）


def _wait_sec(retry_after: str | None, attempt: int) -> float:
    # Retry-After は秒数と HTTP-date の両形式がありうる。秒数以外は指数バックオフに戻す
    try:
        wait = float(retry_after) if retry_after is not None else 2.0**attempt
    except ValueError:
        wait = 2.0**attempt
    return min(max(wait, 0.0), MAX_WAIT_SEC)


def _is_dropped(sock: Any) -> bool:
    """アイドル中の接続をサーバが閉じていないか。読める状態 = EOF（か想定外のデータ）なので使わない。"""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
    except (OSError, ValueError):
        return True
    return bool(readable)


def _proxy_auth(proxy: urllib.parse.SplitResult) -> dict[str, str]:
    # urllib の ProxyHandler と同じく、ユーザー名とパスワードが両方ある場合のみ付ける
    if not (proxy.username and proxy.password):
        return {}
    creds = f"{urllib.parse.unquote(proxy.username)}:{urllib.parse.unquote(proxy.password)}"
    return {"Proxy-Authorization": "Basic " + base64.b64encode(creds.encode()).decode("ascii")}


class HTTPClient:
    """JSON を POST する。接続は保持して次のリクエストで使い回す（分類器ごとに 1 つ持つ）。"""

    def __init__(self, *, timeout: float, max_retries: int) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self._conn: http.client.HTTPConnection | None = None
        self._origin: tuple[str, str] | None = None
        self._via_proxy = False  # http の URL をプロキシ経由で送る（パスを絶対 URL にする）
        self._proxy_headers: dict[str, str] = {}

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _open(self, scheme: str, netloc: str) -> None:
        proxy_url = urllib.request.getproxies().get(scheme)
        if proxy_url and not urllib.request.proxy_bypass(netloc):
            if "://" not in proxy_url:
                proxy_url = "http://" + proxy_url
            proxy = urllib.parse.urlsplit(proxy_url)
            proxy_host = proxy.netloc.rpartition("@")[2]
            auth = _proxy_auth(proxy)
            if scheme == "https":
                # CONNECT でトンネルを張り、その中で接続先と TLS を張る（urllib と同じ）
                conn = http.client.HTTPSConnection(proxy_host, timeout=self.timeout)
                conn.set_tunnel(netloc, headers=auth)
                self._via_proxy, self._proxy_headers = False, {}
            else:
                conn = http.client.HTTPConnection(proxy_host, timeout=self.timeout)
                self._via_proxy, self._proxy_headers = True, auth
        else:
            cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
            conn = cls(netloc, timeout=self.timeout)
            self._via_proxy, self._proxy_headers = False, {}
        try:
            conn.connect()
            # http.client はヘッダと本文を別々に send するので、Nagle で本文の送信が
            # 遅延 ACK 待ち（~40ms）にならないよう無効にする（urllib3 と同じ既定）
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except BaseException:
            conn.close()
            raise
        self._conn, self._origin = conn, (scheme, netloc)

    def _ensure_connection(self, scheme: str, netloc: str) -> bool:
        """使える接続を用意する。新しく張った場合は True。"""
        conn = self._conn
        if conn is not None and (
            self._origin != (scheme, netloc)
            or conn.sock is None  # サーバが Connection: close を返した
            or _is_dropped(conn.sock)  # アイドル中にサーバ側で切れた（keep-alive タイムアウトなど）
        ):
            self.close()
        if self._conn is not None:
            return False
        self._open(scheme, netloc)
        return True

    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> Response:
        """POST して JSON を返す。一時的な失敗は最大 max_retries 回まで待って再試行する。

        再試行の待ち時間はそのまま呼び出し側のレイテンシに乗るので、attempts を記録して区別する。
        """
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"unsupported URL: {url}")
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"User-Agent": USER_AGENT, **headers}
        for attempt in range(self.max_retries + 1):
            try:
                new_connection = self._ensure_connection(parts.scheme, parts.netloc)
                self._conn.request(
                    "POST",
                    url if self._via_proxy else path,
                    body=data,
                    headers={**self._proxy_headers, **headers},
                )
                resp = self._conn.getresponse()
                raw = resp.read()  # 接続を使い回すため、エラー応答でも本文は最後まで読む
            except (OSError, http.client.HTTPException) as e:
                # 接続拒否・DNS 失敗・タイムアウト・切断など。途中で失敗した接続は状態が不明なので捨てる
                self.close()
                if isinstance(e, ssl.SSLCertVerificationError) or attempt >= self.max_retries:
                    raise RuntimeError(f"{url} request failed: {e}") from e
                time.sleep(_wait_sec(None, attempt))
                continue
            if not 200 <= resp.status < 300:
                if resp.status in RETRY_STATUS and attempt < self.max_retries:
                    time.sleep(_wait_sec(resp.getheader("retry-after"), attempt))
                    continue
                detail = raw.decode("utf-8", "replace")[:500]
                raise RuntimeError(f"{url} returned HTTP {resp.status}: {detail}")
            return Response(json.loads(raw), resp.headers, attempt + 1, new_connection)
        raise AssertionError("unreachable")
