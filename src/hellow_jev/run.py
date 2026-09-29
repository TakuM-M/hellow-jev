"""ベンチマーク実行 CLI。

    uv run hellow-jev --config configs/llm_api.toml
    uv run hellow-jev --config configs/jev.toml --task jevbench_sst2   # 同じ config を別タスクで
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from hellow_jev.classifiers import Classifier, Prediction, build_classifier
from hellow_jev.envfile import load_env_file
from hellow_jev.metrics import summarize_run
from hellow_jev.task import MAIN_TASK, REPO_ROOT, TASKS_DIR, Record, Task, load_dataset, load_task
from hellow_jev.util import sha256_file


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def available_tasks() -> list[str]:
    """--task に指定できるタスク名（tasks/ 以下で task.toml を持つディレクトリ）。"""
    if not TASKS_DIR.is_dir():
        return []
    return sorted(d.name for d in TASKS_DIR.iterdir() if (d / "task.toml").is_file())


NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
# 接続先が落ちている等で連続して失敗したら、残りを無駄に待たずに打ち切る
DEFAULT_MAX_CONSECUTIVE_ERRORS = 10


def load_config(path: Path, task_override: str | None) -> dict:
    """config を読んで検証する。全件呼び出した後に落ちるとコストだけかかるので、不備は最初に検出する。"""
    with open(path, "rb") as f:
        config = tomllib.load(f)
    name = config.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise SystemExit(f"{path}: name は英数字と _ . - で指定してください（{name!r}）")
    if "classifier" not in config:
        raise SystemExit(f"{path}: [classifier] がありません")
    # --task > config の task > 本題のタスク。保存する config.json にも実際に回したタスクを残す
    config["task"] = task_override or config.get("task", MAIN_TASK)
    tasks = available_tasks()
    if config["task"] not in tasks:
        raise SystemExit(
            f"タスク {config['task']!r} がありません（指定できるもの: {', '.join(tasks) or 'なし'}）"
        )
    return config


def warm_up(classifier: Classifier, n: int) -> None:
    """接続確立・モデルロード・JIT 等の初回コストをレイテンシから除くため空打ちする。

    評価データを使うとサーバ側キャッシュで本計測が速く見えうるので、ダミーのログを使う
    （タスクによらず同じ文。目的は初回コストの除去なので、分類の中身は問わない）。
    ここで失敗した場合は疎通していないので、本計測に入らず例外のまま止める。
    """
    for i in range(n):
        classifier.classify(f"2026-01-01T00:00:0{i % 10}Z INFO warmup-svc warmup request {i}")


def build_meta(task: Task, dataset_path: Path, warmup: int) -> dict:
    """後から「どの条件で回した結果か」を突き合わせられるよう、入力のハッシュと実行環境を残す。"""
    task_dir = TASKS_DIR / task.name
    return {
        "task": task.name,
        "dataset": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "task_toml_sha256": sha256_file(task_dir / "task.toml"),
        "prompt_sha256": sha256_file(task_dir / "prompt.md"),
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


def predict_one(classifier: Classifier, record: Record) -> dict:
    """1 件分類して predictions.jsonl の 1 行にする。例外はエラーとして記録する。"""
    t0 = time.perf_counter()
    try:
        pred = classifier.classify(record.text)
        error = None
    except Exception as e:  # noqa: BLE001  1 件の失敗で run 全体を失わないため
        pred, error = Prediction(label=None), f"{type(e).__name__}: {e}"
    return {
        "id": record.id,
        "label": record.label,
        "pred": pred.label,
        "error": error,
        "latency_ms": (time.perf_counter() - t0) * 1000,
        "attempts": pred.attempts,
        "new_connection": pred.new_connection,
        "server_ms": pred.server_ms,
        "usage": pred.usage,
        "raw": pred.raw,
    }


def predict_all(
    classifier: Classifier, dataset: list[Record], out_dir: Path, name: str, max_consecutive_errors: int
) -> tuple[list[dict], float]:
    """全件を分類し (predictions, 経過秒) を返す。途中で止まっても残るよう 1 件ずつ書く。"""
    predictions = []
    consecutive_errors = 0
    start = time.perf_counter()
    with open(out_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for record in dataset:
            p = predict_one(classifier, record)
            predictions.append(p)
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            f.flush()
            consecutive_errors = consecutive_errors + 1 if p["error"] else 0
            if consecutive_errors >= max_consecutive_errors:
                raise SystemExit(
                    f"[{name}] {consecutive_errors} 件連続で失敗したため打ち切りました"
                    f"（{len(predictions)}/{len(dataset)} 件）: {p['error']}\n-> {out_dir}"
                )
    return predictions, time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--task", help="タスク名（tasks/ 以下のディレクトリ名）。config の task を上書き")
    parser.add_argument("--dataset", type=Path, help="タスク定義の dataset を上書き")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--warmup", type=int, help="計測前に捨てる呼び出し回数（config の warmup を上書き）"
    )
    args = parser.parse_args()
    load_env_file(REPO_ROOT / ".env")  # API キー等。既存の環境変数が優先

    config = load_config(args.config, args.task)
    name = config["name"]
    task = load_task(config["task"])
    dataset_path = args.dataset or task.dataset
    dataset = load_dataset(dataset_path, task.label_names)
    classifier = build_classifier(config["classifier"], task)

    warmup = args.warmup if args.warmup is not None else config.get("warmup", 0)
    warm_up(classifier, warmup)
    meta = build_meta(task, dataset_path, warmup)

    # 本計測の前に出力先を作る。metrics.json は完走時のみ書くので、
    # 比較表（report）には途中終了の run は載らない
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{name}"
    out_dir = args.out_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=False)  # 同名ディレクトリの上書きを防ぐ
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    max_errors = config.get("max_consecutive_errors", DEFAULT_MAX_CONSECUTIVE_ERRORS)
    predictions, elapsed = predict_all(classifier, dataset, out_dir, name, max_errors)
    metrics = summarize_run(predictions, task.label_names, elapsed)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))

    print(f"[{name}] task={task.name} n={metrics['n']} accuracy={metrics['accuracy']:.3f} "
          f"macro_f1={metrics['macro_f1']:.3f} "
          f"error={metrics['error_rate']:.3f} retried={metrics['retried']} "
          f"p50={metrics['latency']['p50_ms']:.1f}ms p95={metrics['latency']['p95_ms']:.1f}ms")
    print(f"-> {out_dir}")


if __name__ == "__main__":
    main()
