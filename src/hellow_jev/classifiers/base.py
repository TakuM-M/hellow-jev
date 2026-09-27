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
    server_ms: float | None = None  # サーバ側の純推論時間（取れる場合のみ。ネットワーク除く）
    attempts: int = 1  # HTTP 試行回数。2 以上ならリトライ待ちがレイテンシに乗っている


class Classifier(ABC):
    def __init__(self, task: Task, **options: Any) -> None:
        # サブクラスが受け取らなかったキーはここに残る。temprature のような typo を
        # 黙って無視すると既定値のまま走り、公平性のための設定が効かないので拒否する
        if options:
            raise ValueError(f"unknown classifier options: {', '.join(sorted(options))}")
        self.task = task

    @abstractmethod
    def classify(self, text: str) -> Prediction: ...

    def normalize(self, output: str) -> str | None:
        """モデル出力をラベル名に正規化する。未知ラベルは None。

        既定ラベルに寄せると「ラベル外出力の率」が見えなくなり、
        そのラベルの精度も水増しされるため、ここでは補完しない。
        """
        cleaned = output.strip().strip("`\"'.").lower()
        return cleaned if cleaned in self.task.label_names else None
