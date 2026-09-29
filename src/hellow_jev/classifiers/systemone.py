"""Jev の `/v1/systemone` ワイヤプロトコルのクライアント（Jev / Laya 共通）。

Laya の `laya-serve` は Jev と同じプロトコルを話すため、接続先を変えるだけで
同じリクエストを両者に投げられる（docs/notes/jev.md, docs/notes/laya.md 参照）。

リクエスト:
    {"model": ..., "state": <state>,
     "questions": {"label": {"type": "choice", "instructions": ..., "criteria": {name: desc}}}}
    state の形はタスクの state_format（task.toml）で選ぶ。Jev / Laya のどちらにも同じ形で渡る:
      "object"（既定）: {"log": <テキスト>}
      "string"        : <テキスト>（jevbench と同じ。tasks/JEVBENCH.md）
    Laya は dict の state を JSON 文字列にしてから読む（laya の serialize_state）ため、
    形式が違うとモデルへの入力も変わる。
レスポンス:
    {"model": ..., "answers": {"label": {"choice": ..., "probabilities": {...}}},
     "usage": {"input_tokens": ..., "output_tokens": ...}}
"""

from __future__ import annotations

from typing import Any

from hellow_jev.classifiers._http import HTTPClient
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
        max_retries: int = 3,  # LLM と同じ既定値（リトライ条件を揃える）
        **options: Any,
    ) -> None:
        super().__init__(task, **options)
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.api_key = api_key
        self.model = model
        self.http = HTTPClient(timeout=timeout, max_retries=max_retries)

    def build_state(self, text: str) -> str | dict[str, str]:
        fmt = self.task.state_format
        if fmt == "object":
            # 実例（docs/notes/jev.md）と同じオブジェクト形式。
            # 実例のキーは "body" で、"log" キー・質問 ID "label" での実 API 呼び出しは未検証
            return {"log": text}
        if fmt == "string":
            # jevbench と同じ（テキストそのもの）。jevbench は Jev を OpenRouter の Decisions API 経由、
            # Laya を laya ライブラリ直接で、どちらもこの形・質問 ID "label" で呼んでいる
            return text
        # load_task で検証済みだが、Task を直接作った場合に黙って既定の形で送らないよう止める
        raise ValueError(f"unknown state_format: {fmt!r}")

    def build_request(self, text: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "state": self.build_state(text),
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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = self.http.post(self.url, headers, self.build_request(text))
        raw = resp.body
        server_ms = resp.headers.get("X-Inference-Time-Ms")

        answer = raw.get("answers", {}).get(QUESTION_ID, {})
        choice = answer.get("choice")
        return Prediction(
            # 選択肢から選ぶ方式なので通常ラベル外は出ないが、念のため検証する
            label=choice if choice in self.task.label_names else None,
            raw=raw,
            usage=raw.get("usage", {}),
            server_ms=float(server_ms) if server_ms else None,
            attempts=resp.attempts,
            new_connection=resp.new_connection,
        )
