"""Laya（open weight）による分類器。

利用方法（ローカル推論 / 推論サーバ経由など）は検討中。
backend オプションで切り替える想定（docs/notes/laya.md 参照）。
"""

from __future__ import annotations

from hellow_jev.classifiers.base import Classifier, Prediction


class LayaClassifier(Classifier):
    def classify(self, text: str) -> Prediction:
        backend = self.options.get("backend", "undecided")
        raise NotImplementedError(f"Laya ({backend}) は未実装です")
