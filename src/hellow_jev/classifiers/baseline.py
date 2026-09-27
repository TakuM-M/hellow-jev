"""キーワードマッチによるルールベース baseline（モデル不要・パイプライン疎通確認用）。"""

from __future__ import annotations

from hellow_jev.classifiers.base import Classifier, Prediction


class KeywordBaseline(Classifier):
    def classify(self, text: str) -> Prediction:
        lowered = text.lower()
        scores = {
            label.name: sum(kw in lowered for kw in label.keywords) for label in self.task.labels
        }
        best = max(scores, key=scores.get)
        return Prediction(label=best if scores[best] > 0 else self.task.default_label, raw=scores)
