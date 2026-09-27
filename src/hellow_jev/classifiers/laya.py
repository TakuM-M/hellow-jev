"""Laya（open weight）による分類器。

`laya-serve`（Jev 互換の HTTP サーバ）経由で推論する。torch 等の依存はサーバ側に閉じ、
本リポジトリは標準ライブラリのままにする。起動方法は docs/notes/laya.md 参照。

    pip install "laya[serve]"
    LAYA_MODELS=english laya-serve   # 既定で :8000

LAYA_MODELS は起動時に先読みするチェックポイントの一覧で、使えるモデルの制限ではない
（空なら全チェックポイントを先読み）。推論に使うチェックポイントはリクエストの model で決まり、
未読込なら初回リクエストで遅延ロードされる（laya 0.3.20 の serve.py / router.py で確認）。
"""

from __future__ import annotations

import os

from hellow_jev.classifiers.base import Prediction
from hellow_jev.classifiers.systemone import SystemOneClassifier

DEFAULT_ENDPOINT = "http://localhost:8000"
# laya-serve が受け付けるチェックポイント名。これ以外の model は、サーバ側でエラーにならず
# 黙って自動選択（言語判定によるルーティング）に切り替わるため、ここで拒否する
CHECKPOINTS = ("english", "multilingual", "typed-decisions")


class LayaClassifier(SystemOneClassifier):
    def __init__(self, task, **options):
        backend = options.pop("backend", "http")
        if backend != "http":
            raise ValueError(f"Laya backend {backend!r} は未対応です（'http' のみ）")
        if "base_url" in options:
            raise ValueError("Laya の接続先は endpoint で指定してください（base_url ではなく）")
        # 再現性のためチェックポイントを固定する（未指定だとログごとに自動選択される）
        if options.get("model") not in CHECKPOINTS:
            raise ValueError(
                f"Laya の model は {' / '.join(CHECKPOINTS)} のいずれかを指定してください"
                f"（{options.get('model')!r}）"
            )
        base_url = (
            options.pop("endpoint", None) or os.environ.get("LAYA_ENDPOINT") or DEFAULT_ENDPOINT
        )
        # laya-serve で LAYA_API_KEY を設定した場合のみ必要
        api_key = os.environ.get("LAYA_API_KEY")
        super().__init__(task, base_url=base_url, api_key=api_key, **options)

    def classify(self, text: str) -> Prediction:
        pred = super().classify(text)
        # レスポンスのトップレベル model は固定値（"laya-rl-agent"）なので、
        # 実際に使われたチェックポイントは routing.model で確かめる
        routing = pred.raw.get("routing") if isinstance(pred.raw, dict) else None
        served = routing.get("model") if isinstance(routing, dict) else None
        if served is not None and served != self.model:
            raise RuntimeError(f"laya-serve が {served!r} で推論しました（config は {self.model!r}）")
        return pred
