"""Jev（TypeSafe AI の商用 API）による分類器。

API キーは環境変数 JEV_API_KEY から読む（config には書かない）。
仕様の調査メモは docs/notes/jev.md。
"""

from __future__ import annotations

import os

from hellow_jev.classifiers.systemone import SystemOneClassifier

DEFAULT_BASE_URL = "https://api.typesafe.ai"


class JevClassifier(SystemOneClassifier):
    def __init__(self, task, **options):
        api_key = os.environ.get("JEV_API_KEY")
        if not api_key:
            raise RuntimeError("環境変数 JEV_API_KEY が未設定です")
        base_url = (
            options.pop("base_url", None)
            or os.environ.get("JEV_API_BASE_URL")
            or DEFAULT_BASE_URL
        )
        super().__init__(task, base_url=base_url, api_key=api_key, **options)
