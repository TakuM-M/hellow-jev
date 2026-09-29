"""比較表の下に出す誤り分析（誤った件・混同ペア・予測ラベルの確率）。

各 run の predictions.jsonl から集計する。テキストは meta の dataset から引く
（run 後にデータが変わっていれば、別の文を出さないようテキストは出さない）。
確率は Jev / Laya が返す probabilities だけを使う。LLM に確信度を出させると
全モデル共通の指示文が変わり、値の意味も揃わないため扱わない。
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from hellow_jev.classifiers.systemone import QUESTION_ID
from hellow_jev.task import load_dataset
from hellow_jev.util import md_table, sha256_file

MAX_CASES = 20  # 誤った件の表の上限。件数の多いタスク（jevbench など）で表が膨らまないようにする
MAX_PAIRS = 10  # 混同ペアの表の上限
THRESHOLDS = (0.5, 0.9)  # 保留（人に回す）の閾値
TEXT_MAX = 120  # 表に出すテキストの最大文字数


def load_predictions(run_dir: Path) -> list[dict] | None:
    path = run_dir / "predictions.jsonl"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def probabilities(p: dict) -> dict[str, float] | None:
    """Jev / Laya の応答にある choice 質問の probabilities。無ければ None（LLM・エラー件）。"""
    raw = p.get("raw")
    answer = raw.get("answers", {}).get(QUESTION_ID) if isinstance(raw, dict) else None
    probs = answer.get("probabilities") if isinstance(answer, dict) else None
    return probs if isinstance(probs, dict) and probs else None


def load_texts(meta: dict) -> dict[str, str]:
    """run 時のデータセットの id → テキスト。ファイルが無いか中身が変わっていれば空。"""
    path = Path(meta.get("dataset") or "")
    if not meta.get("dataset") or not path.is_file():
        return {}
    if meta.get("dataset_sha256") and sha256_file(path) != meta["dataset_sha256"]:
        return {}
    return {r.id: r.text for r in load_dataset(path)}


def _cell_text(text: str | None) -> str:
    if not text:
        return "-"
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= TEXT_MAX else text[: TEXT_MAX - 1] + "…"


def _pred_name(p: dict) -> str:
    if p.get("error"):
        return "(エラー)"
    return p["pred"] if p.get("pred") is not None else "(ラベル外)"


def _is_wrong(p: dict) -> bool:
    return p.get("pred") != p["label"] or bool(p.get("error"))


def _names(runs: list[dict]) -> list[str]:
    """表の列名。--all で同じ config 名が並ぶときは run ディレクトリ名で区別する。"""
    names = [r["config"]["name"] for r in runs]
    return [r["dir"].name if names.count(n) > 1 else n for r, n in zip(runs, names)]


def _case_cell(p: dict | None) -> str:
    if p is None:
        return "-"  # この run では予測していない id（データセットが run 間で異なる）
    if not _is_wrong(p):
        return "✓"
    cell = _pred_name(p)
    probs = probabilities(p)
    if probs and p.get("pred") is not None:
        cell += f" ({probs.get(p['pred'], 0.0):.2f} / {probs.get(p['label'], 0.0):.2f})"
    return cell


def cases_section(names: list[str], preds: list[list[dict]], texts: dict[str, str]) -> list[str]:
    by_id = [{p["id"]: p for p in ps} for ps in preds]
    order: dict[str, int] = {}  # データセット順（最初に現れた順）
    gold: dict[str, str] = {}
    for ps in preds:
        for p in ps:
            order.setdefault(p["id"], len(order))
            gold.setdefault(p["id"], p["label"])
    wrong = {i: sum(1 for m in by_id if i in m and _is_wrong(m[i])) for i in order}
    ids = sorted((i for i, n in wrong.items() if n), key=lambda i: (-wrong[i], order[i]))
    lines = [
        "#### 誤った件", "",
        "いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 "
        f"{MAX_CASES} 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。",
        "",
    ]
    if not ids:
        return lines + ["全モデルが全件正解。", ""]
    rows = [
        [i, _cell_text(texts.get(i)), gold[i], *(_case_cell(m.get(i)) for m in by_id)]
        for i in ids[:MAX_CASES]
    ]
    lines += md_table(["id", "テキスト", "正解", *names], rows)
    if len(ids) > MAX_CASES:
        lines.append(f"\n他 {len(ids) - MAX_CASES} 件（全件は results/<run>/predictions.jsonl）")
    return lines + [""]


def pairs_section(names: list[str], preds: list[list[dict]]) -> list[str]:
    counts: dict[tuple[str, str], Counter] = {}
    for name, ps in zip(names, preds):
        for p in ps:
            if _is_wrong(p):
                counts.setdefault((p["label"], _pred_name(p)), Counter())[name] += 1
    if not counts:
        return []
    pairs = sorted(counts, key=lambda k: (-sum(counts[k].values()), k))
    rows = [
        [f"{g} → {pr}", str(sum(counts[g, pr].values())),
         ", ".join(f"{n} {counts[g, pr][n]}" for n in names if counts[g, pr][n])]
        for g, pr in pairs[:MAX_PAIRS]
    ]
    lines = ["#### 混同ペア", "", f"正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 {MAX_PAIRS} 組）。", ""]
    lines += md_table(["正解 → 予測", "件数", "モデル別"], rows)
    if len(pairs) > MAX_PAIRS:
        lines.append(f"\n他 {len(pairs) - MAX_PAIRS} 組")
    return lines + [""]


def _scored(ps: list[dict]) -> list[tuple[float, bool]]:
    """(予測ラベルの確率, 正解か)。確率の無い件（エラー・LLM）は除く。"""
    out = []
    for p in ps:
        probs = probabilities(p)
        if probs and not p.get("error") and p.get("pred") is not None:
            out.append((probs.get(p["pred"], 0.0), p["pred"] == p["label"]))
    return out


def probability_sections(names: list[str], preds: list[list[dict]]) -> list[str]:
    scored = [(n, s) for n, s in ((n, _scored(ps)) for n, ps in zip(names, preds)) if s]
    if not scored:
        return []

    def stats(xs: list[float], pick) -> list[str]:
        return [str(len(xs)), f"{statistics.median(xs):.2f}", f"{pick(xs):.2f}"] if xs else [str(len(xs)), "-", "-"]

    rows = []
    for name, s in scored:
        ok = [x for x, c in s if c]
        ng = [x for x, c in s if not c]
        rows.append([name, *stats(ok, min), *stats(ng, max)])
    lines = ["#### 予測ラベルの確率（確率を返すモデルのみ）", ""]
    lines += md_table(["model", "正解時 n", "正解時 中央値", "正解時 最小", "誤り時 n", "誤り時 中央値", "誤り時 最大"], rows)

    rows = []
    for name, s in scored:
        cells = [name]
        for t in THRESHOLDS:
            kept = [c for x, c in s if x >= t]
            cells += [f"{1 - len(kept) / len(s):.3f}", f"{sum(kept) / len(kept):.3f}" if kept else "-"]
        rows.append(cells)
    header = ["model"] + [h for t in THRESHOLDS for h in (f"閾値 {t} 保留率", f"閾値 {t} 自動処理分 Acc")]
    lines += [
        "", "#### 自信の低い判定を人に回した場合", "",
        "「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。",
        "",
        "- 保留率: 人に回った件の割合（人の手間）",
        "- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率",
        "- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。",
        "",
        *md_table(header, rows),
    ]
    return lines + [""]


def render(runs: list[dict]) -> list[str]:
    """1 タスク分の誤り分析。predictions.jsonl のある run が無ければ空。"""
    runs = [r for r in runs if r.get("predictions") is not None]
    if not runs:
        return []
    names = _names(runs)
    preds = [r["predictions"] for r in runs]
    texts: dict[str, str] = {}
    for r in runs:
        texts.update(load_texts(r["meta"]))
    return [
        "### 誤り分析", "",
        *cases_section(names, preds, texts),
        *pairs_section(names, preds),
        *probability_sections(names, preds),
    ]
