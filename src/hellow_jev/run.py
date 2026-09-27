"""ベンチマーク実行 CLI。

    uv run hellow-jev --config configs/llm_api.toml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from hellow_jev.classifiers import Prediction, build_classifier
from hellow_jev.envfile import load_env_file
from hellow_jev.metrics import evaluate, latency_stats, usage_stats
from hellow_jev.task import REPO_ROOT, TASKS_DIR, load_dataset, load_task


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
# 接続先が落ちている等で連続して失敗したら、残りを無駄に待たずに打ち切る
DEFAULT_MAX_CONSECUTIVE_ERRORS = 10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", type=Path, help="タスク定義の dataset を上書き")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--warmup", type=int, help="計測前に捨てる呼び出し回数（config の warmup を上書き）"
    )
    args = parser.parse_args()
    load_env_file(REPO_ROOT / ".env")  # API キー等。既存の環境変数が優先

    with open(args.config, "rb") as f:
        config = tomllib.load(f)
    # 全件呼び出した後に落ちるとコストだけかかるので、config の不備は最初に検出する
    name = config.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise SystemExit(f"{args.config}: name は英数字と _ . - で指定してください（{name!r}）")
    if "classifier" not in config:
        raise SystemExit(f"{args.config}: [classifier] がありません")
    max_consecutive_errors = config.get("max_consecutive_errors", DEFAULT_MAX_CONSECUTIVE_ERRORS)

    task = load_task(config.get("task", "log_classification"))
    dataset_path = args.dataset or task.dataset
    dataset = load_dataset(dataset_path, task.label_names)
    classifier = build_classifier(config["classifier"], task)

    # 接続確立・モデルロード・JIT 等の初回コストをレイテンシから除くため空打ちする。
    # 評価データを使うとサーバ側キャッシュで本計測が速く見えうるので、ダミーのログを使う。
    # ここで失敗した場合は疎通していないので、本計測に入らず例外のまま止める
    warmup = args.warmup if args.warmup is not None else config.get("warmup", 0)
    for i in range(warmup):
        classifier.classify(f"2026-01-01T00:00:0{i % 10}Z INFO warmup-svc warmup request {i}")

    # 後から「どの条件で回した結果か」を突き合わせられるよう、入力のハッシュを残す
    task_dir = TASKS_DIR / task.name
    meta = {
        "task": task.name,
        "dataset": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "task_toml_sha256": _sha256(task_dir / "task.toml"),
        "prompt_sha256": _sha256(task_dir / "prompt.md"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "warmup": warmup,
        # レイテンシは実行マシンに強く依存するため、比較表に載せる前提で記録する
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        },
    }

    # 途中で止まっても結果が残るよう、本計測の前に出力先を作り predictions は 1 件ずつ書く。
    # metrics.json は完走時のみ書くので、比較表（report）には途中終了の run は載らない
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{name}"
    out_dir = args.out_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=False)  # 同名ディレクトリの上書きを防ぐ
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    predictions = []
    consecutive_errors = 0
    start = time.perf_counter()
    with open(out_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for record in dataset:
            t0 = time.perf_counter()
            try:
                pred = classifier.classify(record.text)
                error = None
            except Exception as e:  # noqa: BLE001  1 件の失敗で run 全体を失わないため
                pred, error = Prediction(label=None), f"{type(e).__name__}: {e}"
            p = {
                "id": record.id,
                "label": record.label,
                "pred": pred.label,
                "error": error,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "attempts": pred.attempts,
                "server_ms": pred.server_ms,
                "usage": pred.usage,
                "raw": pred.raw,
            }
            predictions.append(p)
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            f.flush()
            consecutive_errors = consecutive_errors + 1 if error else 0
            if consecutive_errors >= max_consecutive_errors:
                raise SystemExit(
                    f"[{name}] {consecutive_errors} 件連続で失敗したため打ち切りました"
                    f"（{len(predictions)}/{len(dataset)} 件）: {error}\n-> {out_dir}"
                )
    elapsed = time.perf_counter() - start

    metrics = evaluate(
        [p["label"] for p in predictions],
        [p["pred"] for p in predictions],
        task.label_names,
        errors=[p["error"] is not None for p in predictions],
    )
    ok = [p for p in predictions if p["error"] is None]
    metrics["total_sec"] = elapsed
    metrics["avg_latency_ms"] = elapsed * 1000 / len(dataset) if dataset else 0.0
    metrics["throughput_per_sec"] = len(dataset) / elapsed if elapsed > 0 else 0.0
    # 失敗件はタイムアウト待ちなどを含むので、レイテンシ統計からは外す（件数は error_rate で見る）
    metrics["latency"] = latency_stats([p["latency_ms"] for p in ok])
    server = [p["server_ms"] for p in ok if p["server_ms"] is not None]
    metrics["server_latency"] = latency_stats(server) if server else None
    metrics["usage"] = usage_stats([p["usage"] for p in predictions])
    # リトライ待ちは latency に含まれる。p95 の悪化がレート制限由来か見分けるために残す
    metrics["retried"] = sum(p["attempts"] > 1 for p in ok)

    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))

    print(f"[{name}] n={metrics['n']} accuracy={metrics['accuracy']:.3f} "
          f"macro_f1={metrics['macro_f1']:.3f} invalid={metrics['invalid_rate']:.3f} "
          f"error={metrics['error_rate']:.3f} retried={metrics['retried']} "
          f"p50={metrics['latency']['p50_ms']:.1f}ms p95={metrics['latency']['p95_ms']:.1f}ms")
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()
