"""全モデル共通の分類器インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hellow_jev.task import Task


@dataclass
class Prediction:
    label: str | None  # None = ラベル外出力（評価では不正解＋ invalid として集計）
    raw: Any = None  # モデルの生出力（デバッグ・誤り分析用）
    usage: dict[str, Any] = field(default_factory=dict)  # トークン数などコスト情報


class Classifier(ABC):
    def __init__(self, task: Task, **options: Any) -> None:
        self.task = task
        self.options = options

    @abstractmethod
    def classify(self, text: str) -> Prediction: ...

    def normalize(self, output: str) -> str | None:
        """モデル出力をラベル名に正規化する。未知ラベルは None。

        既定ラベルに寄せると「ラベル外出力の率」が見えなくなり、
        そのラベルの精度も水増しされるため、ここでは補完しない。
        """
        cleaned = output.strip().strip("`\"'.").lower()
        return cleaned if cleaned in self.task.label_names else None
