"""分類結果の評価指標。"""

from __future__ import annotations

from collections import Counter

INVALID = "<invalid>"  # ラベル外出力（Prediction.label が None）を混同行列で表す名前


def evaluate(y_true: list[str], y_pred: list[str | None], labels: list[str]) -> dict:
    assert len(y_true) == len(y_pred)
    n = len(y_true)
    invalid = sum(p is None for p in y_pred)
    y_pred = [INVALID if p is None else p for p in y_pred]
    correct = sum(t == p for t, p in zip(y_true, y_pred))

    confusion: dict[str, Counter] = {t: Counter() for t in labels}
    for t, p in zip(y_true, y_pred):
        confusion.setdefault(t, Counter())[p] += 1

    per_class = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn,
        }

    supported = [m for m in per_class.values() if m["support"] > 0]
    macro_f1 = sum(m["f1"] for m in supported) / len(supported) if supported else 0.0

    return {
        "n": n,
        "accuracy": correct / n if n else 0.0,
        "macro_f1": macro_f1,
        "invalid_rate": invalid / n if n else 0.0,
        "per_class": per_class,
        "confusion": {t: dict(c) for t, c in confusion.items()},
    }


def percentile(values: list[float], q: float) -> float:
    """線形補間による分位点（q は 0〜100）。空なら 0.0。"""
    if not values:
        return 0.0
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def latency_stats(latencies_ms: list[float]) -> dict:
    """1 件あたりレイテンシの要約。比較表では p50 / p95 を主に使う。"""
    n = len(latencies_ms)
    return {
        "n": n,
        "mean_ms": sum(latencies_ms) / n if n else 0.0,
        "p50_ms": percentile(latencies_ms, 50),
        "p95_ms": percentile(latencies_ms, 95),
        "p99_ms": percentile(latencies_ms, 99),
        "min_ms": min(latencies_ms) if n else 0.0,
        "max_ms": max(latencies_ms) if n else 0.0,
    }


def usage_stats(usages: list[dict]) -> dict:
    """usage の数値項目（input_tokens など）を合計し、1 件あたり平均も出す。"""
    total: dict[str, float] = {}
    for u in usages:
        for key, value in u.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total[key] = total.get(key, 0) + value
    n = len(usages)
    return {"total": total, "per_record": {k: v / n for k, v in total.items()} if n else {}}
