"""Jev の `/v1/systemone` ワイヤプロトコルのクライアント（Jev / Laya 共通）。

Laya の `laya-serve` は Jev と同じプロトコルを話すため、接続先を変えるだけで
同じリクエストを両者に投げられる（docs/notes/jev.md, docs/notes/laya.md 参照）。

リクエスト:
    {"model": ..., "state": {"log": <ログ>},
     "questions": {"label": {"type": "choice", "instructions": ..., "criteria": {name: desc}}}}
レスポンス:
    {"model": ..., "answers": {"label": {"choice": ..., "probabilities": {...}}},
     "usage": {"input_tokens": ..., "output_tokens": ...}}
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from hellow_jev.classifiers.base import Classifier, Prediction

QUESTION_ID = "label"


class SystemOneClassifier(Classifier):
    """`POST {base_url}/v1/systemone` に choice 質問 1 問を投げて分類する。"""

    def __init__(
        self,
        task,
        *,
        base_url: str,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        **options: Any,
    ) -> None:
        super().__init__(task, **options)
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def build_request(self, text: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            # state は文字列も受け付けるが、Jev 実呼び出しで確認済みのオブジェクト形式に揃える
            "state": {"log": text},
            "questions": {
                QUESTION_ID: {
                    "type": "choice",
                    "instructions": self.task.instructions,
                    "criteria": self.task.criteria(),
                }
            },
        }
        if self.model:
            body["model"] = self.model
        return body

    def classify(self, text: str) -> Prediction:
        data = json.dumps(self.build_request(text), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.loads(resp.read())
                server_ms = resp.headers.get("X-Inference-Time-Ms")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"{self.url} returned HTTP {e.code}: {detail}") from e

        answer = raw.get("answers", {}).get(QUESTION_ID, {})
        choice = answer.get("choice")
        return Prediction(
            # 選択肢から選ぶ方式なので通常ラベル外は出ないが、念のため検証する
            label=choice if choice in self.task.label_names else None,
            raw=raw,
            usage=raw.get("usage", {}),
            server_ms=float(server_ms) if server_ms else None,
        )
