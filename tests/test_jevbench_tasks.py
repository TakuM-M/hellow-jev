"""jevbench 再現用タスク（tasks/jevbench_*。tasks/JEVBENCH.md）の定義と参照値を検証する。

評価データ（data/processed/jevbench_*.jsonl）は無くてよい。
"""

import tomllib

import pytest

from hellow_jev.classifiers import build_classifier
from hellow_jev.task import REPO_ROOT, TASKS_DIR, load_task

LABEL_COUNTS = {
    "jevbench_sst2": 2,
    "jevbench_agnews": 4,
    "jevbench_agnews_v2": 4,
    "jevbench_banking77": 77,
}
TASKS = list(LABEL_COUNTS)
# jevbench が Jev / Laya の choice 質問に渡す指示文（src/jevbench/classifiers/jev.py）
INSTRUCTIONS = "Which category best describes the text? Pick exactly one."
ALL_MODELS = {"jev", "laya", "llm-frontier", "llm-cheap", "bert-ft", "bert-zs"}


def _reference(name: str) -> dict:
    with open(TASKS_DIR / name / "reference.toml", "rb") as f:
        return tomllib.load(f)


@pytest.mark.parametrize("name", TASKS)
def test_task_loads(name):
    task = load_task(name)
    assert len(task.labels) == LABEL_COUNTS[name]
    assert task.instructions == INSTRUCTIONS
    assert task.state_format == "string"
    # LLM 出力の正規化（Classifier.normalize）は小文字にしてから照合するので、ラベル名も小文字に限る
    assert all(n == n.lower() for n in task.label_names)
    dataset = "jevbench_agnews.jsonl" if name.startswith("jevbench_agnews") else f"{name}.jsonl"
    assert task.dataset == REPO_ROOT / "data" / "processed" / dataset


@pytest.mark.parametrize("name", TASKS)
def test_prompt_renders(name):
    task = load_task(name)
    prompt = task.render_prompt("a {braced} text")
    assert prompt.startswith("You are a text classifier.\n" + INSTRUCTIONS)
    assert prompt.endswith("Text:\na {braced} text")
    for label in task.labels:
        assert f"- {label.name}: {label.description}" in prompt
    assert not any(p in prompt for p in ("{instructions}", "{labels}", "{log}"))


def test_prompt_is_shared():
    # 4 タスクで同じファイルにしておき、1 つだけ直して条件がずれるのを防ぐ
    assert len({(TASKS_DIR / n / "prompt.md").read_bytes() for n in TASKS}) == 1


def test_sst2_labels():
    assert load_task("jevbench_sst2").label_names == ["negative", "positive"]


def test_agnews_old_and_new_descriptions():
    old, new = load_task("jevbench_agnews"), load_task("jevbench_agnews_v2")
    assert old.label_names == new.label_names == ["world", "sports", "business", "sci_tech"]
    assert old.dataset == new.dataset
    for a, b in zip(old.labels, new.labels):
        assert a.description != b.description


def test_banking77_labels():
    task = load_task("jevbench_banking77")
    names = task.label_names
    assert len(set(names)) == 77
    # jevbench の _bank_id は "Refund_not_showing_up" / "reverted_card_payment?" を小文字化・"?" 除去する
    assert "refund_not_showing_up" in names and "reverted_card_payment" in names
    assert all(n == n.lower() and "?" not in n and " " not in n for n in names)
    for label in task.labels:  # jevbench の _bank_desc と同じ変換
        assert label.description == "Customer asks about: " + label.name.replace("_", " ")


def test_jev_and_laya_send_text_as_state(monkeypatch):
    # jevbench と同じく state はテキストそのもの。Jev / Laya で同じ質問になる
    monkeypatch.setenv("JEV_API_KEY", "k")
    task = load_task("jevbench_banking77")
    bodies = [
        build_classifier(config, task).build_request("I still have not received my new card")
        for config in ({"type": "jev", "model": "m"}, {"type": "laya", "model": "english"})
    ]
    for body in bodies:
        assert body["state"] == "I still have not received my new card"
        assert body["questions"]["label"]["instructions"] == INSTRUCTIONS
        assert body["questions"]["label"]["criteria"] == task.criteria()
    assert bodies[0]["questions"] == bodies[1]["questions"]


@pytest.mark.parametrize("name", TASKS)
def test_reference_parses(name):
    ref = _reference(name)
    assert ref["source"] == "jevbench"
    assert ref["url"].startswith("https://github.com/dhruvmehra/jevbench/")
    assert isinstance(ref["note"], str) and ref["note"]
    models = [row["model"] for row in ref["rows"]]
    assert set(models) == ({"jev"} if name == "jevbench_agnews_v2" else ALL_MODELS)
    assert len(models) == len(set(models))
    for row in ref["rows"]:
        assert isinstance(row["model_id"], str) and row["model_id"]
        # 割合は 0〜1 の小数（% ではない）
        for key in ("accuracy", "macro_f1", "error_rate"):
            assert isinstance(row[key], float) and 0 <= row[key] <= 1, (row["model"], key)
        for key in ("p50_ms", "p95_ms"):
            assert row[key] > 0
        assert row["p50_ms"] <= row["p95_ms"]
        if "cost_per_1k_usd" in row:  # $0（ローカル）は書かない
            assert row["cost_per_1k_usd"] > 0


def test_agnews_reference_split():
    # 「jev (new descriptions)」行は v2 だけに入れ、旧説明の表には元の jev 行を残す
    old = {row["model"]: row for row in _reference("jevbench_agnews")["rows"]}
    (new,) = _reference("jevbench_agnews_v2")["rows"]
    assert old["jev"]["accuracy"] == 0.843 and old["jev"]["error_rate"] == 0.004
    assert new["model"] == "jev" and new["accuracy"] == 0.858
