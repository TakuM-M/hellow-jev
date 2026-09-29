"""Jev / Laya 共通クライアントを、手元のダミー /v1/systemone サーバに対して検証する。"""

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hellow_jev import task as task_module
from hellow_jev.classifiers import build_classifier
from hellow_jev.task import load_task


class _Handler(BaseHTTPRequestHandler):
    requests: list = []
    choice = "payment"
    routing_model = None  # laya-serve が実際に使ったチェックポイント（None なら routing を返さない）

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                    "body": body})
        if self.path != "/v1/systemone":
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "model": "mock",
            "answers": {"label": {"type": "choice", "choice": type(self).choice,
                                  "probabilities": {type(self).choice: 1.0}}},
            "usage": {"input_tokens": 42, "output_tokens": 0},
        }
        if type(self).routing_model:
            payload["routing"] = {"model": type(self).routing_model, "reason": "explicit model"}
        resp = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Inference-Time-Ms", "12.50")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.requests = []
    _Handler.choice = "payment"
    _Handler.routing_model = None
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_laya_request_and_parse(server):
    _Handler.routing_model = "multilingual"
    task = load_task("log_classification")
    clf = build_classifier(
        {"type": "laya", "endpoint": server, "model": "multilingual"}, task
    )
    pred = clf.classify("ERROR payment-svc charge failed")
    assert pred.label == "payment"
    assert pred.usage == {"input_tokens": 42, "output_tokens": 0}
    assert pred.server_ms == 12.5

    sent = _Handler.requests[0]
    assert sent["path"] == "/v1/systemone"
    assert sent["auth"] is None
    body = sent["body"]
    assert body["model"] == "multilingual"
    assert body["state"] == {"log": "ERROR payment-svc charge failed"}
    q = body["questions"]["label"]
    assert q["type"] == "choice"
    # LLM プロンプトと同じ指示文・ラベル定義が渡っていること（公平性）
    assert q["instructions"] == task.instructions
    assert q["criteria"] == {l.name: l.description for l in task.labels}


@pytest.mark.parametrize(
    ("state_format", "expected"),
    [("object", {"log": "some text"}), ("string", "some text")],
)
def test_state_format(server, monkeypatch, state_format, expected):
    monkeypatch.setenv("JEV_API_KEY", "k")
    task = replace(load_task("log_classification"), state_format=state_format)
    for config in ({"type": "jev", "base_url": server, "model": "jev-x"},
                   {"type": "laya", "endpoint": server, "model": "english"}):
        build_classifier(config, task).classify("some text")
    # Jev / Laya は共通クライアントなので、どちらにも同じ state が渡る
    assert [r["body"]["state"] for r in _Handler.requests] == [expected, expected]


def test_unknown_state_format_is_rejected(tmp_path, monkeypatch):
    # load_task を通さずに作った Task でも、黙って既定の形で送らない
    bad = replace(load_task("log_classification"), state_format="str")
    clf = build_classifier({"type": "laya", "endpoint": "http://127.0.0.1:1", "model": "english"}, bad)
    with pytest.raises(ValueError, match="unknown state_format"):
        clf.build_request("x")

    # task.toml の typo は読み込み時に止める
    task_dir = tmp_path / "t"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        'dataset = "d.jsonl"\ninstructions = "i"\nstate_format = "str"\n'
        '[[labels]]\nname = "a"\ndescription = "A"\n'
    )
    (task_dir / "prompt.md").write_text("notes\n---\n{log}\n")
    monkeypatch.setattr(task_module, "TASKS_DIR", tmp_path)
    with pytest.raises(ValueError, match=r"state_format must be one of 'object', 'string' \(got 'str'\)"):
        load_task("t")


def test_jev_sends_bearer_key(server, monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    clf = build_classifier({"type": "jev", "base_url": server, "model": "jev-x"},
                           load_task("log_classification"))
    assert clf.classify("x").label == "payment"
    assert _Handler.requests[0]["auth"] == "Bearer test-key"
    assert _Handler.requests[0]["body"]["model"] == "jev-x"


def test_jev_requires_key(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="JEV_API_KEY"):
        build_classifier({"type": "jev"}, load_task("log_classification"))


def test_unknown_choice_is_invalid(server):
    _Handler.choice = "not-a-label"
    clf = build_classifier({"type": "laya", "endpoint": server, "model": "english"},
                           load_task("log_classification"))
    assert clf.classify("x").label is None


def test_http_error_is_reported(server):
    clf = build_classifier({"type": "laya", "endpoint": server + "/wrong", "model": "english"},
                           load_task("log_classification"))
    with pytest.raises(RuntimeError, match="HTTP 404"):
        clf.classify("x")


def test_laya_rejects_unknown_checkpoint():
    # laya-serve は未知の model を黙って自動選択に切り替えるので、クライアント側で止める
    for model in (None, "englsh", "convaiinnovations/laya"):
        config = {"type": "laya", "endpoint": "http://127.0.0.1:1"}
        if model:
            config["model"] = model
        with pytest.raises(ValueError, match="english / multilingual / typed-decisions"):
            build_classifier(config, load_task("log_classification"))


def test_laya_checkpoint_mismatch_is_error(server):
    _Handler.routing_model = "multilingual"
    clf = build_classifier({"type": "laya", "endpoint": server, "model": "english"},
                           load_task("log_classification"))
    with pytest.raises(RuntimeError, match="'multilingual'"):
        clf.classify("x")
