import json
import re
import sys

import pytest

from hellow_jev import report
from hellow_jev.report import latest_per_name, load_runs, render, task_of


def _write_run(root, name, run_id, metrics, config_extra=None, meta_extra=None):
    d = root / f"{run_id}_{name}"
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"name": name, **(config_extra or {})}))
    (d / "meta.json").write_text(json.dumps(
        {"dataset_sha256": "abc", "host": {"machine": "x86_64", "cpu_count": 4}, **(meta_extra or {})}
    ))
    (d / "metrics.json").write_text(json.dumps(metrics))


BASE = {"n": 2, "accuracy": 0.5, "macro_f1": 0.5}


def _sections(text):
    """## 見出しごとに本文を分ける（dict は見出しの出現順）。"""
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def test_report_latest_and_cost(tmp_path):
    base = {"n": 2, "accuracy": 0.5, "macro_f1": 0.5}
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
    assert "| jev | 2 | 1.000 | 0.500 | - | 250.0 | 310.0 | - | 100 | $0.5000 | x86_64 4cpu |" in table


def test_report_cost_uses_current_config_pricing(tmp_path):
    results, configs = tmp_path / "results", tmp_path / "configs"
    usage = {"usage": {"per_record": {"input_tokens": 100.0, "output_tokens": 2.0}}}
    # 実行時の config に単価が無くても、集計時点の configs/<name>.toml の [pricing] を使う
    _write_run(results, "jev", "20260101T000000Z", {**BASE, **usage})
    # 実行時の単価より集計時点の単価を優先する
    _write_run(results, "llm", "20260101T000000Z", {**BASE, **usage}, {"pricing": {"input_per_mtok": 9.0}})
    # 単価 0（ローカル実行）は $0 と出す
    _write_run(results, "local", "20260101T000000Z", {**BASE, **usage})
    # configs に無い名前は実行時の config の単価を使う
    _write_run(results, "old", "20260101T000000Z", {**BASE, **usage}, {"pricing": {"input_per_mtok": 0.5}})
    configs.mkdir()
    (configs / "jev.toml").write_text("[pricing]\ninput_per_mtok = 0.042\noutput_per_mtok = 0.0\n")
    (configs / "llm.toml").write_text("[pricing]\ninput_per_mtok = 1.0\noutput_per_mtok = 5.0\n")
    (configs / "local.toml").write_text("[pricing]\ninput_per_mtok = 0.0\noutput_per_mtok = 0.0\n")

    cost = {r[0]: r[9] for r in (report.row(run, configs) for run in load_runs(results))}
    # 100 × 0.042 / 1M × 1 万件 = $0.042
    assert cost["jev"] == "$0.0420"
    # (100 × 1 + 2 × 5) / 1M × 1 万件 = $1.1
    assert cost["llm"] == "$1.1000"
    assert cost["local"] == "$0"
    assert cost["old"] == "$0.5000"
    # configs_dir を渡さなければ実行時の config だけを見る（従来どおり）
    assert report.row(load_runs(results)[0])[9] == "-"


def test_llm_row_shows_model_on_next_line(tmp_path):
    _write_run(tmp_path, "llm_api", "20260101T000000Z", BASE,
               {"classifier": {"type": "llm", "model": "claude-haiku-4-5-20251001"}})
    # LLM 以外は model があっても config 名だけ
    _write_run(tmp_path, "jev", "20260101T000000Z", BASE, {"classifier": {"type": "jev", "model": "jev-1.13.0"}})
    names = sorted(report.row(run)[0] for run in load_runs(tmp_path))
    assert names == ["jev", "llm_api<br>claude-haiku-4-5-20251001"]


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


def test_task_of_falls_back_for_old_runs():
    assert task_of({"meta": {"task": "jevbench_sst2"}, "config": {"task": "x"}}) == "jevbench_sst2"
    assert task_of({"meta": {}, "config": {"task": "jevbench_sst2"}}) == "jevbench_sst2"
    assert task_of({"meta": {}, "config": {}}) == "log_classification"


def test_same_config_on_two_tasks_is_listed_per_task(tmp_path):
    results = tmp_path / "results"
    # meta に task がない旧形式の run は log_classification の run として扱い、最新の方が残る
    _write_run(results, "jev", "20260101T000000Z", {**BASE, "accuracy": 0.1})
    _write_run(results, "jev", "20260102T000000Z", {**BASE, "accuracy": 0.2},
               meta_extra={"task": "log_classification"})
    _write_run(results, "jev", "20260103T000000Z", {**BASE, "accuracy": 0.3},
               meta_extra={"task": "jevbench_sst2"})
    _write_run(results, "jev", "20260104T000000Z", {**BASE, "accuracy": 0.4},
               meta_extra={"task": "jevbench_sst2"})
    _write_run(results, "jev", "20260105T000000Z", {**BASE, "accuracy": 0.6},
               meta_extra={"task": "jevbench_agnews"})
    runs = latest_per_name(load_runs(results))
    assert sorted(r["metrics"]["accuracy"] for r in runs) == [0.2, 0.4, 0.6]

    sections = _sections(render(runs, tmp_path / "tasks"))
    # 本題のタスクが先頭、残りはタスク名順。共通の注記は最後に 1 回だけ
    assert list(sections) == ["log_classification", "jevbench_agnews", "jevbench_sst2", "注記"]
    assert "| jev | 2 | 0.200 |" in sections["log_classification"]
    assert "| jev | 2 | 0.400 |" in sections["jevbench_sst2"]
    assert "0.300" not in sections["jevbench_sst2"]
    assert "| jev | 2 | 0.600 |" in sections["jevbench_agnews"]
    assert "p50 / p95" in sections["注記"]


def test_consistency_warnings_are_per_task(tmp_path):
    results = tmp_path / "results"
    same = {"task_toml_sha256": "t", "prompt_sha256": "p", "git_commit": "c"}
    # タスクが違えばデータセットのハッシュが違うのは当然なので、タスクをまたいでは警告しない
    _write_run(results, "jev", "20260101T000000Z", BASE,
               meta_extra={**same, "task": "log_classification", "dataset_sha256": "d1"})
    _write_run(results, "llm_api", "20260102T000000Z", BASE,
               meta_extra={**same, "task": "log_classification", "dataset_sha256": "d1"})
    _write_run(results, "jev", "20260103T000000Z", BASE,
               meta_extra={**same, "task": "jevbench_sst2", "dataset_sha256": "d2"})
    _write_run(results, "llm_api", "20260104T000000Z", BASE,
               meta_extra={**same, "task": "jevbench_sst2", "dataset_sha256": "d2",
                           "task_toml_sha256": "t2", "git_dirty": True})

    sections = _sections(render(latest_per_name(load_runs(results)), tmp_path / "tasks"))
    assert "⚠️" not in sections["log_classification"]
    sst2 = sections["jevbench_sst2"]
    assert "⚠️ タスク定義" in sst2
    assert "未コミットの変更がある状態で実行: llm_api" in sst2
    assert "⚠️ データセット" not in sst2
    assert "⚠️" not in sections["注記"]


REFERENCE = """
source = "jevbench"
url = "https://example.com/summary.md"
note = "n=500。レイテンシは jevbench 側の環境で計測"

[[rows]]
model = "jev"
model_id = "typesafe/jev-1.13"
accuracy = 0.843
macro_f1 = 0.842
error_rate = 0.004
p50_ms = 381.0
p95_ms = 715.0
cost_per_1k_usd = 0.0184

[[rows]]
model = "gpt-4o-mini"
accuracy = 0.9
macro_f1 = 0.899
error_rate = 0.0
p50_ms = 520.0
p95_ms = 900.5
"""


def test_reference_rows_are_appended_to_their_task(tmp_path):
    tasks = tmp_path / "tasks"
    for task in ["jevbench_sst2", "jevbench_banking77"]:
        (tasks / task).mkdir(parents=True)
        (tasks / task / "reference.toml").write_text(REFERENCE)
    results = tmp_path / "results"
    _write_run(results, "jev", "20260101T000000Z", BASE, meta_extra={"task": "jevbench_sst2"})

    sections = _sections(render(latest_per_name(load_runs(results)), tasks))
    # run のないタスクは、参考値があっても表を出さない
    assert list(sections) == ["jevbench_sst2", "注記"]
    lines = sections["jevbench_sst2"].splitlines()
    ours = lines.index(
        "| jev | 2 | 0.500 | 0.500 | - | - | - | - | - | - | x86_64 4cpu | 20260101T000000Z_jev |"
    )
    # 参考値はこちらの run の後。コストは 1000 件あたり $0.0184 → 1 万件あたり $0.1840
    ref = lines.index(
        "| [jevbench] jev (typesafe/jev-1.13) | - | 0.843 | 0.842 | 0.004 | 381.0 | 715.0"
        " | - | - | $0.1840 | - | 参考値 |"
    )
    assert ours < ref
    assert lines[ref + 1] == (
        "| [jevbench] gpt-4o-mini | - | 0.900 | 0.899 | 0.000 | 520.0 | 900.5 | - | - | - | - | 参考値 |"
    )
    assert (
        "- 参考値は [jevbench](https://example.com/summary.md) の公開結果。n=500。レイテンシは jevbench 側の環境で計測"
        in lines
    )


def _main(monkeypatch, capsys, tmp_path, *args):
    monkeypatch.setattr(sys, "argv", [
        "hellow-jev-report", "--results-dir", str(tmp_path / "results"),
        "--tasks-dir", str(tmp_path / "tasks"),
        # リポジトリの configs/ の単価を読まないよう、存在しない場所を渡す
        "--configs-dir", str(tmp_path / "configs"), *args,
    ])
    report.main()
    return capsys.readouterr().out


def test_cli_all_and_task_filter(tmp_path, monkeypatch, capsys):
    results = tmp_path / "results"
    _write_run(results, "jev", "20260101T000000Z", BASE)
    _write_run(results, "jev", "20260102T000000Z", BASE, meta_extra={"task": "log_classification"})
    _write_run(results, "jev", "20260103T000000Z", BASE, meta_extra={"task": "jevbench_sst2"})
    _write_run(results, "llm_api", "20260104T000000Z", BASE, meta_extra={"task": "jevbench_agnews"})

    out = _main(monkeypatch, capsys, tmp_path)
    assert out.count("| jev | 2 |") == 2 and out.count("| llm_api | 2 |") == 1
    # --all は同じ (タスク, config 名) の古い run も含めて全部出す
    out = _main(monkeypatch, capsys, tmp_path, "--all")
    assert out.count("| jev | 2 |") == 3 and out.count("| llm_api | 2 |") == 1

    out = _main(monkeypatch, capsys, tmp_path, "--task", "jevbench_sst2", "--task", "jevbench_agnews")
    assert list(_sections(out)) == ["jevbench_agnews", "jevbench_sst2", "注記"]
    with pytest.raises(SystemExit, match="no runs found.*jevbench_typo"):
        _main(monkeypatch, capsys, tmp_path, "--task", "jevbench_typo")
