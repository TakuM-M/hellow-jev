"""results/ の実行結果を集計して比較表（Markdown）を出す。

    uv run hellow-jev-report                     # 標準出力へ
    uv run hellow-jev-report --out docs/report.md
    uv run hellow-jev-report --task jevbench_sst2 --task jevbench_agnews   # タスクを絞る

タスクごとに表を分け、(タスク, config 名) ごとに最新の run を 1 行にする（--all で全 run）。
tasks/<task>/reference.toml があれば、公開ベンチマークの参考値をその表の末尾に足す。
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from hellow_jev.task import REPO_ROOT, TASKS_DIR

# 本題のタスク。表の先頭に出す。meta に task がない旧形式の run もこのタスクとみなす
MAIN_TASK = "log_classification"

# 行どうしで一致していないと同一条件の比較にならない meta の項目
CONSISTENCY_KEYS = {
    "dataset_sha256": "データセット",
    "task_toml_sha256": "タスク定義（instructions・ラベル説明）",
    "prompt_sha256": "プロンプト",
    "git_commit": "コード（git commit）",
}

COLUMNS = [
    "model", "n", "Acc", "Macro-F1", "ラベル外率", "エラー率", "p50 ms", "p95 ms", "件/秒",
    "サーバ p50 ms", "入力tok/件", "コスト/1万件", "実行環境", "run",
]

# 全タスクの表に共通の注記（最後に 1 回だけ出す）
NOTES = [
    "- p50 / p95 はクライアント側の往復時間（API はネットワーク込み）。warmup 分・エラー件は除外",
    "- 接続は使い回す（keep-alive）。張り直した件数は metrics.json の new_connections",
    "- エラー率はリトライしても応答が得られなかった件の割合（Acc では不正解として数える）",
    "- サーバ p50 はサーバが返す純推論時間（X-Inference-Time-Ms ヘッダがある場合のみ。PyPI 版 laya 0.3.20 は返さない）",
    "- コストは config の [pricing]（USD / 1M tokens）から概算。未設定は -",
]


def load_runs(results_dir: Path) -> list[dict]:
    runs = []
    for d in sorted(results_dir.iterdir()) if results_dir.is_dir() else []:
        if not (d / "metrics.json").is_file():
            continue
        runs.append({
            "dir": d,
            "config": json.loads((d / "config.json").read_text()),
            "meta": json.loads((d / "meta.json").read_text()),
            "metrics": json.loads((d / "metrics.json").read_text()),
        })
    return runs


def task_of(run: dict) -> str:
    # meta に task がない旧形式の run は config、それもなければ本題のタスクとみなす
    return run["meta"].get("task") or run["config"].get("task") or MAIN_TASK


def latest_per_name(runs: list[dict]) -> list[dict]:
    """(タスク, config 名) ごとに最新の run を残す。同じ config を別タスクで回した run は両方残る。"""
    # ディレクトリ名がタイムスタンプ始まりなので、名前順の後勝ちで最新になる
    latest: dict[tuple[str, str], dict] = {}
    for run in runs:
        latest[task_of(run), run["config"]["name"]] = run
    return list(latest.values())


def _cost_per_10k(config: dict, per_record: dict) -> str:
    pricing = config.get("pricing")
    if not pricing:
        return "-"
    usd = (
        per_record.get("input_tokens", 0) * pricing.get("input_per_mtok", 0)
        + per_record.get("output_tokens", 0) * pricing.get("output_per_mtok", 0)
    ) / 1e6 * 10_000
    return f"${usd:.4f}"


def row(run: dict) -> list[str]:
    m, config, meta = run["metrics"], run["config"], run["meta"]
    # 旧形式（latency 統計なし）の run も表示できるようにする
    lat = m.get("latency") or {}
    server = m.get("server_latency") or {}
    per_record = (m.get("usage") or {}).get("per_record", {})
    host = meta.get("host", {})
    env = config.get("hardware") or " ".join(
        str(x) for x in (host.get("machine"), f"{host['cpu_count']}cpu" if host.get("cpu_count") else None) if x
    ) or "-"

    def ms(d: dict, key: str) -> str:
        return f"{d[key]:.1f}" if key in d else "-"

    return [
        config["name"],
        str(m["n"]),
        f"{m['accuracy']:.3f}",
        f"{m['macro_f1']:.3f}",
        f"{m.get('invalid_rate', 0):.3f}",
        f"{m['error_rate']:.3f}" if "error_rate" in m else "-",
        ms(lat, "p50_ms"),
        ms(lat, "p95_ms"),
        f"{m['throughput_per_sec']:.1f}" if "throughput_per_sec" in m else "-",
        ms(server, "p50_ms"),
        f"{per_record['input_tokens']:.0f}" if "input_tokens" in per_record else "-",
        _cost_per_10k(config, per_record),
        env,
        run["dir"].name,
    ]


def load_reference(path: Path) -> dict | None:
    """公開ベンチマークの参考値（tasks/<task>/reference.toml）。なければ None。"""
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path}: {e}") from e


def _num(value: float | None, spec: str) -> str:
    return "-" if value is None else format(value, spec)


def reference_row(ref: dict, r: dict) -> list[str]:
    """参考値の 1 行。こちらの run と取り違えないよう model に出典を付け、run 列は「参考値」にする。"""
    model = f"[{ref.get('source', '参考')}] {r['model']}"
    if r.get("model_id"):
        model += f" ({r['model_id']})"
    cost = r.get("cost_per_1k_usd")
    cells = {
        "model": model,
        "Acc": _num(r.get("accuracy"), ".3f"),
        "Macro-F1": _num(r.get("macro_f1"), ".3f"),
        "エラー率": _num(r.get("error_rate"), ".3f"),
        "p50 ms": _num(r.get("p50_ms"), ".1f"),
        "p95 ms": _num(r.get("p95_ms"), ".1f"),
        "コスト/1万件": "-" if cost is None else f"${cost * 10:.4f}",  # 1000 件あたり → 1 万件あたり
        "run": "参考値",
    }
    return [cells.get(column, "-") for column in COLUMNS]


def reference_note(ref: dict) -> str:
    source = ref.get("source", "参考")
    if ref.get("url"):
        source = f"[{source}]({ref['url']})"
    return f"- 参考値は {source} の公開結果。{ref.get('note', '')}".rstrip()


def consistency_warnings(runs: list[dict]) -> list[str]:
    """ラベル説明だけ直して一部のモデルを再実行した、などの条件ずれを表の下に警告する。"""
    warnings = []
    for key, what in CONSISTENCY_KEYS.items():
        if len({r["meta"].get(key) for r in runs}) > 1:
            warnings.append(f"- ⚠️ {what}が run 間で異なる（同一条件の比較になっていない）")
    dirty = [r["config"]["name"] for r in runs if r["meta"].get("git_dirty")]
    if dirty:
        warnings.append(f"- ⚠️ 未コミットの変更がある状態で実行: {', '.join(dirty)}")
    return warnings


def _table(rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(COLUMNS) + " |",
        "| " + " | ".join("---" for _ in COLUMNS) + " |",
        *("| " + " | ".join(cells) + " |" for cells in rows),
    ]


def render(runs: list[dict], tasks_dir: Path = TASKS_DIR) -> str:
    """タスクごとに見出し・表・注記を並べる。本題のタスクを先頭に、残りはタスク名順。"""
    by_task: dict[str, list[dict]] = {}
    for run in runs:
        by_task.setdefault(task_of(run), []).append(run)
    lines: list[str] = []
    for task in sorted(by_task, key=lambda t: (t != MAIN_TASK, t)):
        task_runs = by_task[task]
        rows = [row(r) for r in task_runs]
        notes = []
        ref = load_reference(tasks_dir / task / "reference.toml")
        if ref:
            rows += [reference_row(ref, r) for r in ref.get("rows", [])]
            notes.append(reference_note(ref))
        # 別タスクどうしはデータもタスク定義も違って当然なので、条件ずれはタスク内だけで見る
        notes += consistency_warnings(task_runs)
        lines += [f"## {task}", "", *_table(rows), ""]
        if notes:
            lines += [*notes, ""]
    lines += ["## 注記", "", *NOTES]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--tasks-dir", type=Path, default=TASKS_DIR, help="参考値 <task>/reference.toml を探す場所"
    )
    parser.add_argument("--task", action="append", help="このタスクの run だけ出す（複数回指定可）")
    parser.add_argument(
        "--all", action="store_true", help="(タスク, config 名) ごとの最新だけでなく全 run を出す"
    )
    parser.add_argument("--out", type=Path, help="Markdown の書き出し先（省略時は標準出力）")
    args = parser.parse_args()

    runs = load_runs(args.results_dir)
    if args.task:
        runs = [r for r in runs if task_of(r) in args.task]
    if not args.all:
        runs = latest_per_name(runs)
    if not runs:
        only = f" (task: {', '.join(args.task)})" if args.task else ""
        raise SystemExit(f"no runs found in {args.results_dir}{only}")
    table = render(runs, args.tasks_dir)
    if args.out:
        args.out.write_text(table, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(table, end="")


if __name__ == "__main__":
    main()
