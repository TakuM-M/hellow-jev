"""LLM 分類器を、手元のダミー Anthropic / OpenAI 互換サーバに対して検証する。"""

import json
from http.server import BaseHTTPRequestHandler

import pytest

from hellow_jev.classifiers import build_classifier
from hellow_jev.task import load_task


class _Handler(BaseHTTPRequestHandler):
    requests: list = []
    text = '{"label": "payment"}'
    fail_first: int = 0

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append({"path": self.path, "headers": self.headers, "body": body})
        if type(self).fail_first > 0:
            type(self).fail_first -= 1
            self.send_response(429)
            self.send_header("retry-after", "0")
            self.end_headers()
            return
        if self.path == "/v1/messages":
            resp = {"content": [{"type": "text", "text": type(self).text}],
                    "usage": {"input_tokens": 100, "output_tokens": 2}}
        elif self.path == "/v1/chat/completions":
            resp = {"choices": [{"message": {"role": "assistant", "content": type(self).text}}],
                    "usage": {"prompt_tokens": 90, "completion_tokens": 3}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def server(serve):
    _Handler.requests = []
    _Handler.text = '{"label": "payment"}'
    _Handler.fail_first = 0
    return f"http://127.0.0.1:{serve(_Handler).server_port}"


def test_anthropic_request_and_parse(server, monkeypatch, task):
    monkeypatch.setenv("LLM_API_KEY", "k")
    clf = build_classifier({"type": "llm", "backend": "api", "base_url": server,
                            "model": "claude-x"}, task)
    pred = clf.classify("ERROR payment-svc charge failed")
    assert pred.label == "payment"
    assert pred.usage == {"input_tokens": 100, "output_tokens": 2}

    sent = _Handler.requests[0]
    assert sent["path"] == "/v1/messages"
    assert sent["headers"].get("x-api-key") == "k"
    assert sent["headers"].get("anthropic-version")
    body = sent["body"]
    assert body["model"] == "claude-x"
    assert body["temperature"] == 0.0
    # Jev / Laya と同じ指示文・ラベル定義を含む system が渡っていること（公平性）
    assert task.instructions in body["system"]
    assert body["messages"] == [{"role": "user", "content": "ERROR payment-svc charge failed"}]
    assert body["output_config"]["format"]["schema"]["properties"]["label"]["enum"] == task.label_names


def test_openai_local_passes_extra_body(server, task):
    _Handler.text = '{"label": "auth"}'
    clf = build_classifier({"type": "llm", "backend": "local", "base_url": server + "/v1",
                            "model": "qwen3:4b",
                            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
                           task)
    pred = clf.classify("x")
    assert pred.label == "auth"
    assert pred.usage == {"input_tokens": 90, "output_tokens": 3}
    sent = _Handler.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    assert sent["headers"].get("Authorization") is None
    assert sent["body"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_anthropic_json_output_with_system(server, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    _Handler.text = '{"label": "sports"}'
    task = load_task("jevbench_agnews")
    clf = build_classifier({"type": "llm", "backend": "api", "base_url": server,
                            "model": "claude-x"}, task)
    assert clf.classify("some news").label == "sports"
    body = _Handler.requests[0]["body"]
    assert body["system"] == task.render_system()
    assert body["messages"] == [{"role": "user", "content": "some news"}]
    schema = body["output_config"]["format"]
    assert schema["type"] == "json_schema"
    assert schema["schema"]["properties"]["label"]["enum"] == task.label_names
    assert "response_format" not in body


def test_openai_json_output_with_system(server):
    _Handler.text = '{"label": "world"}'
    task = load_task("jevbench_agnews")
    clf = build_classifier({"type": "llm", "backend": "local", "base_url": server + "/v1",
                            "model": "m"}, task)
    assert clf.classify("some news").label == "world"
    body = _Handler.requests[0]["body"]
    assert body["messages"] == [{"role": "system", "content": task.render_system()},
                                {"role": "user", "content": "some news"}]
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["properties"]["label"]["enum"] == task.label_names
    assert "output_config" not in body and "system" not in body


@pytest.mark.parametrize("text", ["world", '{"label": "World"}', '{"label": "politics"}',
                                  '{"category": "world"}', '["world"]', '{"label": "wor'])
def test_unreadable_output_is_wrong(server, text):
    # jevbench と同じく、JSON として読めない・ラベル外なら None（不正解。正規化しない）
    _Handler.text = text
    clf = build_classifier({"type": "llm", "backend": "local", "base_url": server + "/v1",
                            "model": "m"}, load_task("jevbench_agnews"))
    assert clf.classify("x").label is None


def test_retries_on_rate_limit(server, monkeypatch, task):
    monkeypatch.setenv("LLM_API_KEY", "k")
    _Handler.fail_first = 2
    clf = build_classifier({"type": "llm", "base_url": server, "model": "m"},
                           task)
    assert clf.classify("x").label == "payment"
    assert len(_Handler.requests) == 3


def test_api_requires_key(monkeypatch, task):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        build_classifier({"type": "llm", "model": "m"}, task)


def test_model_is_required(task):
    with pytest.raises(ValueError, match="model"):
        build_classifier({"type": "llm", "backend": "local"}, task)
