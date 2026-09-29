# Laya

- 利用形態: open weight（`laya-serve` 経由で推論）
- 実装: `src/hellow_jev/classifiers/laya.py`（本体は Jev と共通の `systemone.py`）
- 設定: `configs/laya.toml` / 環境変数 `LAYA_ENDPOINT`（サーバでキーを設定した場合は `LAYA_API_KEY`）

## 概要

- Convai Innovations、Apache-2.0、PyPI `laya`
- Jev 互換の判定モデル。BERT 系エンコーダで 1 forward pass で判定する（生成モデルではないので vLLM / llama.cpp は対象外）
- 入出力は Jev と同じ `state` + `questions`（`choice` / `score` / `noul`）

| チェックポイント | パラメータ | コンテキスト | 言語 |
| --- | --- | --- | --- |
| `english`（採用） | 421M（ModernBERT-large） | 512 tok | 英語 |
| `multilingual` | 322M（mmBERT-base） | 1,024（最大 8,192） | 100+ 言語 |
| `typed-decisions` | 421M | 1,024 | typed ワークフロー向け FT 版 |

- 推論方法: Python ライブラリ（`Router().predict(...)`）か `laya-serve`（HTTP、Jev とワイヤ互換）。後者を採用し、Jev と同じクライアントで比較する。torch 等の依存はサーバ側に閉じる
- 未確認の選択肢: ONNX（`laya[onnx]`）/ MLX（`laya-mlx`）/ ファインチューニング

## laya-serve の挙動（ソースで確認）

- 推論するチェックポイントはリクエストの `model` で決まる。未読込なら初回に遅延ロード（数秒）
- `LAYA_MODELS` は起動時に先読みする一覧（空なら全部）で、使えるモデルの制限ではない
- 未知の `model` 名はエラーにならず、言語判定の自動選択に黙って切り替わる → クライアントで 3 つの正式名以外を拒否し、レスポンスの `routing.model` が config と違えばエラーにする
- レスポンスのトップレベル `model` は固定値 `"laya-rl-agent"`。実際のチェックポイントは `routing.model`
- dict の `state` は JSON 文字列にしてから読むので、`state_format` でモデルへの入力が変わる
- `X-Inference-Time-Ms`（サーバ側の推論時間）は PyPI 0.3.21 以降と GitHub main で返る。0.3.20 には無い

## セットアップ（Apple M1 8GB で確認）

```bash
pip install "laya[serve]"   # 0.3.21、Python 3.12、別 venv
LAYA_HOST=127.0.0.1 LAYA_MODELS=english LAYA_THREADS=4 laya-serve
```

- `LAYA_HOST` の既定は `0.0.0.0`（LAN に公開される）なので 127.0.0.1 を指定する
- 他の環境変数: `LAYA_PORT`（既定 8000）/ `LAYA_DEVICE` / `LAYA_PRELOAD` / `LAYA_MAX_LOADED` / `LAYA_MAX_CONCURRENT` / `LAYA_LOG_LEVEL`。CLI 引数は無い
- `GET /health` で読込済みモデル・重みのリビジョン・デバイスが取れる（english = `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`、device は自動で `mps`）
- 起動時の `RuntimeWarning: this checkpoint ships invalid temperatures ...` は confidence の較正の話で、choice には関係しない見込み
- ディスク: venv 約 750MB、重み約 800MB

## 実測（M1 8GB, mps）

- log_classification: 往復 p50 ≈ 149 ms、サーバ推論 p50 ≈ 147 ms（HTTP 分 ≈ 2 ms）。T4 の公表値（39.5 ms）の約 4 倍
- usage: input ≈ 146 tok/件、output 0
- 精度は `docs/notes/dataset.md`

## 公表性能（BENCHMARKS.md、Tesla T4）

- レイテンシ: 1 問 39.5 ms（multilingual 32.8）、10 問 158.6 ms（72.3）。スループット 103–332 問/秒
- 精度: AG News 0.953 / Emotion 0.600 / Banking77 0.425〜0.492
- typed-decisions ベンチ: ベース 0.36（多数派ベースライン未満）、FT 版 0.766
- 日本語（MASSIVE intent 20 択）: english 0.530 / multilingual 0.640

## 注意点

- 選択肢は 20 個程度までが推奨（全選択肢の説明で 192〜256 トークンの枠を共有）。`criteria` の説明は短めにする
- english 版の入力上限は 512 トークン
- 日本語・文脈依存の判定は弱い（中国語業務判定 64 件で multilingual 20/64、Jev 64/64）
- 確率は過信気味。温度スケーリングで改善する

## 参考

- https://github.com/NandhaKishorM/laya
- https://huggingface.co/convaiinnovations/laya
- https://pypi.org/project/laya/
