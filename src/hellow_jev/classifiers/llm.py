"""汎用 LLM による分類器（生成で答えるモデルとの比較用）。

共通プロンプト（tasks/<task>/prompt.md）を 1 ターンで投げ、返ってきたラベル名を正規化する。
API 形式は 2 種類（どちらも標準ライブラリの urllib で叩く）:

    api_format = "anthropic" : Anthropic Messages API（POST {base_url}/v1/messages）
    api_format = "openai"    : OpenAI 互換 Chat Completions（POST {base_url}/chat/completions）
                               Ollama / vLLM / llama.cpp server など

backend = "api"   : 既定 api_format="anthropic"。キーは LLM_API_KEY（無ければ ANTHROPIC_API_KEY）
backend = "local" : 既定 api_format="openai"、接続先は endpoint → LLM_LOCAL_ENDPOINT → Ollama 既定
調査メモは docs/notes/llm.md。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from hellow_jev.classifiers.base import Classifier, Prediction

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
LOCAL_ENDPOINT = "http://localhost:11434/v1"  # Ollama の OpenAI 互換エンドポイント
RETRY_STATUS = {429, 500, 502, 503, 504, 529}
# Qwen3 などの思考モードが出力に混ぜる推論部分
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMClassifier(Classifier):
    def __init__(
        self,
        task,
        *,
        backend: str = "api",
        model: str | None = None,
        api_format: str | None = None,
        base_url: str | None = None,
        endpoint: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 16,
        timeout: float = 60.0,
        max_retries: int = 3,
        extra_body: dict[str, Any] | None = None,
        **options: Any,
    ) -> None:
        super().__init__(task, **options)
        if not model:
            raise ValueError("LLM の model を config で指定してください（再現性のため固定する）")
        if backend == "api":
            self.api_format = api_format or "anthropic"
            self.api_key = os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise RuntimeError("環境変数 LLM_API_KEY（または ANTHROPIC_API_KEY）が未設定です")
            default_url = ANTHROPIC_BASE_URL if self.api_format == "anthropic" else None
            self.base_url = base_url or os.environ.get("LLM_API_BASE_URL") or default_url
        elif backend == "local":
            self.api_format = api_format or "openai"
            # ローカルサーバ側でキーを要求する場合のみ
            self.api_key = os.environ.get("LLM_LOCAL_API_KEY")
            self.base_url = endpoint or os.environ.get("LLM_LOCAL_ENDPOINT") or LOCAL_ENDPOINT
        else:
            raise ValueError(f"unknown backend: {backend!r}（'api' | 'local'）")
        if self.api_format not in ("anthropic", "openai"):
            raise ValueError(f"unknown api_format: {self.api_format!r}（'anthropic' | 'openai'）")
        if not self.base_url:
            raise ValueError("base_url（または LLM_API_BASE_URL）を指定してください")

        self.backend = backend
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_body = extra_body or {}

    # --- リクエスト組み立て -------------------------------------------------

    def build_request(self, text: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        """(url, headers, body) を返す。"""
        prompt = self.task.render_prompt(text)
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        body.update(self.extra_body)
        headers = {"Content-Type": "application/json"}
        root = self.base_url.rstrip("/")
        if self.api_format == "anthropic":
            url = root + "/v1/messages"
            headers["anthropic-version"] = ANTHROPIC_VERSION
            if self.api_key:
                headers["x-api-key"] = self.api_key
        else:
            url = root + "/chat/completions"
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return url, headers, body

    # --- レスポンス解析 -----------------------------------------------------

    def parse_response(self, raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """(出力テキスト, usage) を返す。usage は input_tokens / output_tokens に揃える。"""
        if self.api_format == "anthropic":
            output = "".join(
                block.get("text", "") for block in raw.get("content", [])
                if block.get("type") == "text"
            )
            u = raw.get("usage", {})
            usage = {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens")}
        else:
            choices = raw.get("choices") or [{}]
            output = (choices[0].get("message") or {}).get("content") or ""
            u = raw.get("usage") or {}
            usage = {"input_tokens": u.get("prompt_tokens"),
                     "output_tokens": u.get("completion_tokens")}
        return output, {k: v for k, v in usage.items() if v is not None}

    # --- 実行 ---------------------------------------------------------------

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                if e.code in RETRY_STATUS and attempt < self.max_retries:
                    # レート制限・過負荷は待って再試行（その分レイテンシに乗る点に注意）
                    retry_after = e.headers.get("retry-after")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise RuntimeError(f"{url} returned HTTP {e.code}: {detail}") from e
        raise AssertionError("unreachable")

    def classify(self, text: str) -> Prediction:
        url, headers, body = self.build_request(text)
        raw = self._post(url, headers, body)
        output, usage = self.parse_response(raw)
        answer = THINK_RE.sub("", output)
        return Prediction(label=self.normalize(answer), raw=raw, usage=usage)
