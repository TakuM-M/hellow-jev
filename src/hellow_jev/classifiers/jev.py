"""Jev（API 利用）による分類器。

TODO: Jev の API 仕様を確認して実装する（docs/notes/jev.md に調査メモ）。
"""

from __future__ import annotations

import os

from hellow_jev.classifiers.base import Classifier, Prediction


class JevClassifier(Classifier):
    def __init__(self, task, **options):
        super().__init__(task, **options)
        self.api_key = os.environ.get("JEV_API_KEY")
        self.base_url = options.get("base_url") or os.environ.get("JEV_API_BASE_URL")

    def classify(self, text: str) -> Prediction:
        prompt = self.task.render_prompt(text)
        raise NotImplementedError(f"Jev API 呼び出しは未実装です (prompt chars={len(prompt)})")
