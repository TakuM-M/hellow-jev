"""ベンチマーク実行 CLI。

    python -m hellow_jev.run --config configs/baseline.toml
"""

from __future__ import annotations

import argparse
import json
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from hellow_jev.classifiers import build_classifier
from hellow_jev.metrics import evaluate
from hellow_jev.task import REPO_ROOT, load_dataset, load_task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", type=Path, help="config の dataset を上書き")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    task = load_task(REPO_ROOT / config.get("task_dir", "tasks/log_classification"))
    dataset = load_dataset(args.dataset or REPO_ROOT / config["dataset"])
    classifier = build_classifier(config["classifier"], task)

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

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{config['name']}"
    out_dir = args.out_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    with open(out_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"[{config['name']}] n={metrics['n']} accuracy={metrics['accuracy']:.3f} "
          f"macro_f1={metrics['macro_f1']:.3f} avg_latency={metrics['avg_latency_ms']:.1f}ms")
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()
