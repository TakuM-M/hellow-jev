"""results/ の実行結果を集計して比較表（Markdown）を出す。

    uv run hellow-jev-report                     # 標準出力へ
    uv run hellow-jev-report --out docs/report.md
    uv run hellow-jev-report --task jevbench_sst2 --task jevbench_agnews   # タスクを絞る

タスクごとに表を分け、(タスク, config 名) ごとに最新の run を 1 行にする（--all で全 run）。
tasks/<task>/reference.toml があれば、公開ベンチマークの参考値をその表の末尾に足す。
表の下には predictions.jsonl から誤り分析（誤った件・混同ペア・確率）を出す（error_analysis.py）。
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from hellow_jev import error_analysis
from hellow_jev.task import MAIN_TASK, REPO_ROOT, TASKS_DIR
from hellow_jev.util import md_table

COLUMNS = [
    "model", "n", "Acc", "Macro-F1", "エラー率", "p50 ms", "p95 ms",
    "サーバ p50 ms", "入力tok/件", "コスト/1万件", "実行環境", "run",
]

# 全タスクの表に共通の注記（最後に 1 回だけ出す）
NOTES = [
    "- p50 / p95 はクライアント側の往復時間（API はネットワーク込み）。warmup 分・エラー件は除外",
    "- 接続は使い回す（keep-alive）。張り直した件数は metrics.json の new_connections",
    "- エラー率はリトライしても応答が得られなかった件の割合（Acc では不正解として数える）",
    "- サーバ p50 はサーバが返す純推論時間（X-Inference-Time-Ms ヘッダがある場合のみ。laya は 0.3.21 以降が返し、0.3.20 と Jev は返さない）",
    "- コストは集計時点の configs/<name>.toml の [pricing]（USD / 1M tokens）から概算（無ければ実行時の config）。未設定は -",
    "- ローカル実行（laya / llm_local）は API 課金が無いので $0。マシン代・電力は含まない",
    "- 実行環境は実行時の config の hardware（無ければ実行マシンの CPU）。API はリクエスト先を書く",
    "- 誤り分析の確率は Jev / Laya が返す probabilities の値（confidence ではない）。LLM は確率を返さないので確率の表から除く",
    "- jev の確率は小数 2 桁に丸めて返される。確率の表はエラー件を除く",
    "- 件数が少ないうちは、誤り分析は個別事例として読む（傾向の根拠にはならない）",
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
            "predictions": error_analysis.load_predictions(d),
        })
    return runs


def task_of(run: dict) -> str:
    return run["meta"]["task"]


def latest_per_name(runs: list[dict]) -> list[dict]:
    """(タスク, config 名) ごとに最新の run を残す。同じ config を別タスクで回した run は両方残る。"""
    # ディレクトリ名がタイムスタンプ始まりなので、名前順の後勝ちで最新になる
    latest: dict[tuple[str, str], dict] = {}
    for run in runs:
        latest[task_of(run), run["config"]["name"]] = run
    return list(latest.values())


def current_pricing(configs_dir: Path | None, name: str) -> dict | None:
    """集計時点の configs/<name>.toml の [pricing]。単価は実験条件ではないので、実行後に分かった値も反映する。"""
    path = configs_dir / f"{name}.toml" if configs_dir else None
    if not path or not path.is_file():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f).get("pricing")


def _cost_per_10k(pricing: dict | None, per_record: dict) -> str:
    if not pricing:
        return "-"
    usd = (
        per_record.get("input_tokens", 0) * pricing.get("input_per_mtok", 0)
        + per_record.get("output_tokens", 0) * pricing.get("output_per_mtok", 0)
    ) / 1e6 * 10_000
    return "$0" if usd == 0 else f"${usd:.4f}"


def row(run: dict, configs_dir: Path | None = None) -> list[str]:
    m, config, meta = run["metrics"], run["config"], run["meta"]
    server = m["server_latency"] or {}  # サーバ時間を返さない分類器（Jev・LLM）は None
    per_record = m["usage"]["per_record"]
    host = meta["host"]
    env = config.get("hardware") or " ".join(
        str(x) for x in (host.get("machine"), f"{host['cpu_count']}cpu" if host.get("cpu_count") else None) if x
    ) or "-"

    def ms(d: dict, key: str) -> str:
        return f"{d[key]:.1f}" if key in d else "-"

    # LLM は config 名だけでは中身が分からないので、使った言語モデルを次の行に出す（表のセル内改行は <br>）
    model = config["name"]
    classifier = config["classifier"]
    if classifier["type"] == "llm" and classifier.get("model"):
        model += f"<br>{classifier['model']}"

    return [
        model,
        str(m["n"]),
        f"{m['accuracy']:.3f}",
        f"{m['macro_f1']:.3f}",
        f"{m['error_rate']:.3f}",
        ms(m["latency"], "p50_ms"),
        ms(m["latency"], "p95_ms"),
        ms(server, "p50_ms"),
        f"{per_record['input_tokens']:.0f}" if "input_tokens" in per_record else "-",
        _cost_per_10k(current_pricing(configs_dir, config["name"]) or config.get("pricing"), per_record),
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


def render(runs: list[dict], tasks_dir: Path = TASKS_DIR, configs_dir: Path | None = None) -> str:
    """タスクごとに見出し・表・注記を並べる。本題のタスクを先頭に、残りはタスク名順。

    configs_dir を渡すと、コスト列の単価をそこにある現在の config から読む。
    """
    by_task: dict[str, list[dict]] = {}
    for run in runs:
        by_task.setdefault(task_of(run), []).append(run)
    lines: list[str] = []
    for task in sorted(by_task, key=lambda t: (t != MAIN_TASK, t)):
        task_runs = by_task[task]
        rows = [row(r, configs_dir) for r in task_runs]
        ref = load_reference(tasks_dir / task / "reference.toml")
        if ref:
            rows += [reference_row(ref, r) for r in ref.get("rows", [])]
        lines += [f"## {task}", "", *md_table(COLUMNS, rows), ""]
        if ref:
            lines += [reference_note(ref), ""]
        lines += error_analysis.render(task_runs)
    lines += ["## 注記", "", *NOTES, *error_analysis.NOTES]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--tasks-dir", type=Path, default=TASKS_DIR, help="参考値 <task>/reference.toml を探す場所"
    )
    parser.add_argument(
        "--configs-dir", type=Path, default=REPO_ROOT / "configs",
        help="コスト列の単価 <name>.toml の [pricing] を探す場所",
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
    table = render(runs, args.tasks_dir, args.configs_dir)
    if args.out:
        args.out.write_text(table, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(table, end="")


if __name__ == "__main__":
    main()
