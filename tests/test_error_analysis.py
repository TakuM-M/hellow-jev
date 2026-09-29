import hashlib
import json
from pathlib import Path

from hellow_jev import error_analysis
from hellow_jev.error_analysis import MAX_CASES, MAX_PAIRS, render


def _pred(i, gold, pred, probs=None, error=None):
    raw = {"answers": {"label": {"choice": pred, "probabilities": probs}}} if probs else None
    return {"id": i, "label": gold, "pred": pred, "error": error, "raw": raw}


def _run(name, preds, meta=None):
    return {"dir": Path(f"results/x_{name}"), "config": {"name": name}, "meta": meta or {}, "predictions": preds}


def test_cases_show_probabilities_and_skip_llm_probability_tables():
    jev = [_pred("a", "normal", "auth", {"auth": 0.94, "normal": 0.06}),
           _pred("b", "auth", "auth", {"auth": 0.85, "security": 0.15})]
    llm = [_pred("a", "normal", "auth"), _pred("b", "auth", "auth")]
    out = "\n".join(render([_run("jev", jev), _run("llm_api", llm)]))
    assert "| a | - | normal | auth (0.94 / 0.06) | auth |" in out
    assert "| normal → auth | 2 | jev 1, llm_api 1 |" in out
    # 確率の表は確率を返すモデルだけ
    assert "| jev | 1 | 0.85 | 0.85 | 1 | 0.94 | 0.94 |" in out
    assert "| llm_api |" not in out.split("#### 予測ラベルの確率")[1]
    # 閾値 0.9 で b（0.85）を保留 → 残りは a（誤り）だけ
    assert "| jev | 0.000 | 0.500 | 0.500 | 0.000 |" in out


def test_cases_are_capped_and_sorted_by_models_wrong():
    n = MAX_CASES + 5
    a = [_pred(f"s{i:03d}", "x", "y") for i in range(n)]
    # 最後の件だけ 2 モデルが間違える → 先頭に来る
    b = [_pred(f"s{i:03d}", "x", "y" if i == n - 1 else "x") for i in range(n)]
    out = render([_run("a", a), _run("b", b)])
    rows = [line for line in out if line.startswith("| s")]
    assert len(rows) == MAX_CASES and rows[0].startswith(f"| s{n - 1:03d} |")
    assert "\n他 5 件（全件は results/<run>/predictions.jsonl）" in out


def test_pairs_are_capped():
    preds = [_pred(str(i), f"g{i}", "p") for i in range(MAX_PAIRS + 3)]
    out = render([_run("a", preds)])
    assert sum(line.startswith("| g") for line in out) == MAX_PAIRS
    assert "\n他 3 組" in out


def test_errors_and_all_correct():
    out = "\n".join(render([_run("a", [_pred("a", "x", None, error="Timeout")])]))
    assert "| a | - | x | (エラー) |" in out and "| x → (エラー) | 1 | a 1 |" in out
    out = render([_run("a", [_pred("a", "x", "x")])])
    assert "全モデルが全件正解。" in out and "#### 混同ペア" not in out
    # predictions.jsonl の無い run（旧形式）は誤り分析を出さない
    assert render([_run("a", None)]) == []


def test_text_is_shown_only_if_dataset_unchanged(tmp_path):
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"id": "a", "text": "a | b\nc", "label": "x"}) + "\n")
    sha = hashlib.sha256(data.read_bytes()).hexdigest()
    meta = {"dataset": str(data), "dataset_sha256": sha}
    out = "\n".join(render([_run("m", [_pred("a", "x", "y")], meta)]))
    assert "| a | a \\| b c | x | y |" in out
    assert error_analysis.load_texts({**meta, "dataset_sha256": "other"}) == {}
