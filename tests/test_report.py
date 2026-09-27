import json

from hellow_jev.report import latest_per_name, load_runs, render


def _write_run(root, name, run_id, metrics, config_extra=None):
    d = root / f"{run_id}_{name}"
    d.mkdir()
    (d / "config.json").write_text(json.dumps({"name": name, **(config_extra or {})}))
    (d / "meta.json").write_text(json.dumps({"dataset_sha256": "abc", "host": {"machine": "x86_64", "cpu_count": 4}}))
    (d / "metrics.json").write_text(json.dumps(metrics))


def test_report_latest_and_cost(tmp_path):
    base = {"n": 2, "accuracy": 0.5, "macro_f1": 0.5, "invalid_rate": 0.0}
    _write_run(tmp_path, "jev", "20260101T000000Z", base)
    _write_run(
        tmp_path, "jev", "20260102T000000Z",
        {**base, "accuracy": 1.0,
         "latency": {"p50_ms": 250.0, "p95_ms": 310.0},
         "usage": {"per_record": {"input_tokens": 100.0}}},
        {"pricing": {"input_per_mtok": 0.5}},
    )
    runs = latest_per_name(load_runs(tmp_path))
    assert len(runs) == 1
    table = render(runs)
    # 100 tok/件 × $0.5/1M × 1 万件 = $0.5
    assert "| jev | 2 | 1.000 | 0.500 | 0.000 | - | 250.0 | 310.0 | - | 100 | $0.5000 | x86_64 4cpu |" in table


def test_consistency_warnings():
    from hellow_jev.report import consistency_warnings

    def run(name, **meta):
        base = {"dataset_sha256": "d", "task_toml_sha256": "t", "prompt_sha256": "p",
                "git_commit": "c", "git_dirty": False}
        return {"config": {"name": name}, "meta": {**base, **meta}}

    assert consistency_warnings([run("jev"), run("llm")]) == []
    w = consistency_warnings([run("jev"), run("llm", task_toml_sha256="t2", git_dirty=True)])
    assert len(w) == 2
    assert "タスク定義" in w[0]
    assert "llm" in w[1]
