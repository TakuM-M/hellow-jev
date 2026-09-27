"""汎用 LLM による分類器（比較用ベースライン）。

backend = "api"   : 商用 API 経由
backend = "local" : ローカル推論サーバ（OpenAI 互換エンドポイント等）
どちらにするかは検討中（docs/notes/llm.md 参照）。
"""

from __future__ import annotations

from hellow_jev.classifiers.base import Classifier, Prediction


class LLMClassifier(Classifier):
    def classify(self, text: str) -> Prediction:
        backend = self.options.get("backend", "api")
        if backend == "api":
            return self._classify_api(text)
        if backend == "local":
            return self._classify_local(text)
        raise ValueError(f"unknown backend: {backend}")

    def _classify_api(self, text: str) -> Prediction:
        raise NotImplementedError("LLM (api) は未実装です")

    def _classify_local(self, text: str) -> Prediction:
        raise NotImplementedError("LLM (local) は未実装です")
