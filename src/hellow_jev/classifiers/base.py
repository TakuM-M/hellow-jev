"""全モデル共通の分類器インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hellow_jev.task import Task


@dataclass
class Prediction:
    label: str | None  # None = 答えが読めない・ラベル外（評価では不正解として数える）
    raw: Any = None  # モデルの生出力（デバッグ・誤り分析用）
    usage: dict[str, Any] = field(default_factory=dict)  # トークン数などコスト情報
    server_ms: float | None = None  # サーバ側の純推論時間（取れる場合のみ。ネットワーク除く）
    attempts: int = 1  # HTTP 試行回数。2 以上ならリトライ待ちがレイテンシに乗っている
    new_connection: bool = False  # 接続を張り直したか。True なら TCP/TLS 確立の時間がレイテンシに乗っている


class Classifier(ABC):
    def __init__(self, task: Task, **options: Any) -> None:
        # サブクラスが受け取らなかったキーはここに残る。temprature のような typo を
        # 黙って無視すると既定値のまま走り、公平性のための設定が効かないので拒否する
        if options:
            raise ValueError(f"unknown classifier options: {', '.join(sorted(options))}")
        self.task = task

    @abstractmethod
    def classify(self, text: str) -> Prediction: ...
