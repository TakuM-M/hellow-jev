"""run.main() を端から端まで通す（ダミー分類器を REGISTRY に一時登録）。"""

import json
import sys

import pytest

from hellow_jev import run
from hellow_jev.classifiers import REGISTRY, Classifier, Prediction


class _Flaky(Classifier):
    """fail に含まれるログだけ例外を投げ、それ以外は正解ラベルを返す。"""

    answers: dict = {}
    fail: set = set()

    def classify(self, text):
        if text in type(self).fail:
            raise RuntimeError("HTTP 503")
        return Prediction(label=type(self).answers.get(text), attempts=2)


def _run(tmp_path, monkeypatch, config_text):
    cfg = tmp_path / "c.toml"
    cfg.write_text(config_text)
    out = tmp_path / "results"
    monkeypatch.setitem(REGISTRY, "flaky", _Flaky)
    monkeypatch.setattr(sys, "argv", ["hellow-jev", "--config", str(cfg), "--out-dir", str(out)])
    run.main()
    (d,) = out.iterdir()
    return d


@pytest.fixture
def data():
    from hellow_jev.task import load_dataset, load_task

    ds = load_dataset(load_task("log_classification").dataset)
    _Flaky.answers = {r.text: r.label for r in ds}
    _Flaky.fail = {ds[0].text}
    return ds


def test_error_is_recorded_and_run_completes(tmp_path, monkeypatch, data):
    d = _run(tmp_path, monkeypatch, 'name = "t"\n[classifier]\ntype = "flaky"\n')
    preds = [json.loads(l) for l in (d / "predictions.jsonl").read_text().splitlines()]
    assert len(preds) == len(data)
    assert preds[0]["error"] == "RuntimeError: HTTP 503" and preds[0]["pred"] is None
    m = json.loads((d / "metrics.json").read_text())
    assert m["error_rate"] == 1 / len(data)
    assert m["invalid_rate"] == 0.0
    assert m["latency"]["n"] == len(data) - 1
    assert m["retried"] == len(data) - 1
    assert json.loads((d / "meta.json").read_text())["dataset_sha256"]


def test_aborts_on_consecutive_errors_but_keeps_predictions(tmp_path, monkeypatch, data):
    _Flaky.fail = {r.text for r in data[:3]}
    with pytest.raises(SystemExit, match="3 件連続"):
        _run(tmp_path, monkeypatch,
             'name = "t"\nmax_consecutive_errors = 3\n[classifier]\ntype = "flaky"\n')
    (d,) = (tmp_path / "results").iterdir()
    assert len((d / "predictions.jsonl").read_text().splitlines()) == 3
    assert not (d / "metrics.json").exists()  # 途中終了の run は比較表に載せない


def test_invalid_name_fails_before_any_call(tmp_path, monkeypatch, data):
    _Flaky.fail = set()
    with pytest.raises(SystemExit, match="name"):
        _run(tmp_path, monkeypatch, '[classifier]\ntype = "flaky"\n')
    assert not (tmp_path / "results").exists()
