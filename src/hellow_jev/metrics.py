"""分類結果の評価指標。"""

from __future__ import annotations

from collections import Counter


def evaluate(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    assert len(y_true) == len(y_pred)
    n = len(y_true)
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
        "per_class": per_class,
        "confusion": {t: dict(c) for t, c in confusion.items()},
    }
