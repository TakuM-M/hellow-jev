"""全モデル共通の分類器インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hellow_jev.task import Task


@dataclass
class Prediction:
    label: str
    raw: Any = None  # モデルの生出力（デバッグ・誤り分析用）
    usage: dict[str, Any] = field(default_factory=dict)  # トークン数などコスト情報


class Classifier(ABC):
    def __init__(self, task: Task, **options: Any) -> None:
        self.task = task
        self.options = options

    @abstractmethod
    def classify(self, text: str) -> Prediction: ...

    def normalize(self, output: str, fallback: str = "normal") -> str:
        """モデル出力をラベル名に正規化する。未知ラベルは fallback。"""
        cleaned = output.strip().strip("`\"'.").lower()
        for name in self.task.label_names:
            if cleaned == name or cleaned.startswith(name):
                return name
        return fallback
