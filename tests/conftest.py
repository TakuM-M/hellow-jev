"""テスト共通の fixture（ダミー HTTP サーバ・テスト用タスク）。"""

import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

from hellow_jev.task import Label, Task


@pytest.fixture
def serve():
    """serve(handler[, server_cls]) で 127.0.0.1 の空きポートにダミーサーバを立てる。終了時に止める。"""
    servers = []

    def start(handler, server_cls=HTTPServer):
        httpd = server_cls(("127.0.0.1", 0), handler)
        httpd.daemon_threads = True  # 保持中の接続があってもテスト終了を妨げない
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return httpd

    yield start
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def task():
    """分類器のテスト用タスク。本題の log_classification（暫定）のラベル変更に影響されないよう固定する。"""
    return Task(
        name="test",
        dataset=Path("unused.jsonl"),
        labels=[Label("payment", "Payment failures"), Label("auth", "Login problems")],
        instructions="Classify the log.",
        prompt_template="{text}",
        system_template="{instructions}\n{labels}",
    )
