"""results/ の実行結果を集計して比較表（Markdown）を出す。

    uv run hellow-jev-report                     # 標準出力へ
    uv run hellow-jev-report --out docs/report.md

config 名ごとに最新の run を 1 行にする（--all で全 run）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hellow_jev.task import REPO_ROOT

COLUMNS = [
    "model", "n", "Acc", "Macro-F1", "ラベル外率", "エラー率", "p50 ms", "p95 ms", "件/秒",
    "サーバ p50 ms", "入力tok/件", "コスト/1万件", "実行環境", "run",
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


def latest_per_name(runs: list[dict]) -> list[dict]:
    # ディレクトリ名がタイムスタンプ始まりなので、名前順の後勝ちで最新になる
    latest: dict[str, dict] = {}
    for run in runs:
        latest[run["config"]["name"]] = run
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


def render(runs: list[dict]) -> str:
    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "| " + " | ".join("---" for _ in COLUMNS) + " |",
    ]
    lines += ["| " + " | ".join(row(r)) + " |" for r in runs]
    notes = [
        "",
        "- p50 / p95 はクライアント側の往復時間（API はネットワーク込み）。warmup 分・エラー件は除外",
        "- エラー率はリトライしても応答が得られなかった件の割合（Acc では不正解として数える）",
        "- サーバ p50 はサーバが返す純推論時間（Laya の X-Inference-Time-Ms など、取れる場合のみ）",
        "- コストは config の [pricing]（USD / 1M tokens）から概算。未設定は -",
    ]
    datasets = {r["meta"].get("dataset_sha256") for r in runs}
    if len(datasets) > 1:
        notes.append("- ⚠️ データセットのハッシュが run 間で異なる（同一条件の比較になっていない）")
    return "\n".join(lines + notes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument("--all", action="store_true", help="config 名ごとの最新だけでなく全 run を出す")
    parser.add_argument("--out", type=Path, help="Markdown の書き出し先（省略時は標準出力）")
    args = parser.parse_args()

    runs = load_runs(args.results_dir)
    if not args.all:
        runs = latest_per_name(runs)
    if not runs:
        raise SystemExit(f"no runs found in {args.results_dir}")
    table = render(runs)
    if args.out:
        args.out.write_text(table, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(table, end="")


if __name__ == "__main__":
    main()
