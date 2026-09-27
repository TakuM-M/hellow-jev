"""分類器共通の JSON POST（リトライ付き）。

Jev / Laya / LLM でリトライ条件が違うと「安定性の差」が実装差で決まってしまうため、
全分類器がこの関数を通す。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import Any

# レート制限・過負荷・一時的なサーバエラー（529 は Anthropic の overloaded）
RETRY_STATUS = {429, 500, 502, 503, 504, 529}
MAX_WAIT_SEC = 60.0  # Retry-After が大きすぎても run が止まり続けないよう上限を設ける


@dataclass
class Response:
    body: dict[str, Any]
    headers: Message
    attempts: int  # 1 = リトライなし


def _wait_sec(retry_after: str | None, attempt: int) -> float:
    # Retry-After は秒数と HTTP-date の両形式がありうる。秒数以外は指数バックオフに戻す
    try:
        wait = float(retry_after) if retry_after is not None else 2.0**attempt
    except ValueError:
        wait = 2.0**attempt
    return min(max(wait, 0.0), MAX_WAIT_SEC)


def post_json(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    *,
    timeout: float,
    max_retries: int,
) -> Response:
    """POST して JSON を返す。一時的な失敗は最大 max_retries 回まで待って再試行する。

    再試行の待ち時間はそのまま呼び出し側のレイテンシに乗るので、attempts を記録して区別する。
    """
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return Response(json.loads(resp.read()), resp.headers, attempt + 1)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code in RETRY_STATUS and attempt < max_retries:
                time.sleep(_wait_sec(e.headers.get("retry-after"), attempt))
                continue
            raise RuntimeError(f"{url} returned HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            # 接続拒否・DNS 失敗・タイムアウト・切断（HTTPError は URLError のサブクラスなので先に処理済み）
            if attempt < max_retries:
                time.sleep(_wait_sec(None, attempt))
                continue
            raise RuntimeError(f"{url} request failed: {e}") from e
    raise AssertionError("unreachable")
