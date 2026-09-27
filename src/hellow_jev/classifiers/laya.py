"""Laya（open weight）による分類器。

`laya-serve`（Jev 互換の HTTP サーバ）経由で推論する。torch 等の依存はサーバ側に閉じ、
本リポジトリは標準ライブラリのままにする。起動方法は docs/notes/laya.md 参照。

    pip install "laya[serve]"
    LAYA_MODELS=multilingual laya-serve   # 既定で :8000
"""

from __future__ import annotations

import os

from hellow_jev.classifiers.systemone import SystemOneClassifier

DEFAULT_ENDPOINT = "http://localhost:8000"


class LayaClassifier(SystemOneClassifier):
    def __init__(self, task, **options):
        backend = options.pop("backend", "http")
        if backend != "http":
            raise ValueError(f"Laya backend {backend!r} は未対応です（'http' のみ）")
        base_url = (
            options.pop("endpoint", None) or os.environ.get("LAYA_ENDPOINT") or DEFAULT_ENDPOINT
        )
        # laya-serve で LAYA_API_KEY を設定した場合のみ必要
        api_key = os.environ.get("LAYA_API_KEY")
        super().__init__(task, base_url=base_url, api_key=api_key, **options)
