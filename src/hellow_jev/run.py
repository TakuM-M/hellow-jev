"""ベンチマーク実行 CLI。

    uv run hellow-jev --config configs/llm_api.toml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from hellow_jev.classifiers import build_classifier
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", type=Path, help="タスク定義の dataset を上書き")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--warmup", type=int, help="計測前に捨てる呼び出し回数（config の warmup を上書き）"
    )
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    task = load_task(config.get("task", "log_classification"))
    dataset_path = args.dataset or task.dataset
    dataset = load_dataset(dataset_path, task.label_names)
    classifier = build_classifier(config["classifier"], task)

    # 接続確立・モデルロード・JIT 等の初回コストをレイテンシから除くため空打ちする。
    # 評価データを使うとサーバ側キャッシュで本計測が速く見えうるので、ダミーのログを使う
    warmup = args.warmup if args.warmup is not None else config.get("warmup", 0)
    for i in range(warmup):
        classifier.classify(f"2026-01-01T00:00:0{i % 10}Z INFO warmup-svc warmup request {i}")

    predictions = []
    start = time.perf_counter()
    for record in dataset:
        t0 = time.perf_counter()
        pred = classifier.classify(record.text)
        predictions.append(
            {
                "id": record.id,
                "label": record.label,
                "pred": pred.label,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "server_ms": pred.server_ms,
                "usage": pred.usage,
                "raw": pred.raw,
            }
        )
    elapsed = time.perf_counter() - start

    metrics = evaluate(
        [p["label"] for p in predictions],
        [p["pred"] for p in predictions],
        task.label_names,
    )
    metrics["total_sec"] = elapsed
    metrics["avg_latency_ms"] = elapsed * 1000 / len(dataset) if dataset else 0.0
    metrics["throughput_per_sec"] = len(dataset) / elapsed if elapsed > 0 else 0.0
    metrics["latency"] = latency_stats([p["latency_ms"] for p in predictions])
    server = [p["server_ms"] for p in predictions if p["server_ms"] is not None]
    metrics["server_latency"] = latency_stats(server) if server else None
    metrics["usage"] = usage_stats([p["usage"] for p in predictions])

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

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{config['name']}"
    out_dir = args.out_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=False)  # 同名ディレクトリの上書きを防ぐ
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    with open(out_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"[{config['name']}] n={metrics['n']} accuracy={metrics['accuracy']:.3f} "
          f"macro_f1={metrics['macro_f1']:.3f} invalid={metrics['invalid_rate']:.3f} "
          f"p50={metrics['latency']['p50_ms']:.1f}ms p95={metrics['latency']['p95_ms']:.1f}ms")
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()
