# Laya 調査メモ

- 利用形態: open weight
- 実装: `src/hellow_jev/classifiers/laya.py`
- 設定: `configs/laya.toml` / 環境変数 `LAYA_ENDPOINT`（, `LAYA_API_KEY`）

## 概要（2026-09-27 調査）

- 開発: Convai Innovations。**Apache-2.0**。PyPI `laya`（調査時 v0.3.20）
- **Jev 互換の OSS 判定モデル**。非自己回帰（BERT 系エンコーダ）で 1 forward pass で判定
- 入出力は Jev と同じ `state` + `questions`（`choice` / `score` / `noul`）
- 汎用 LLM でも「vLLM 等で動かす生成モデル」でもない点に注意

## チェックポイント

| 名前 | パラメータ | コンテキスト | 言語 |
| --- | --- | --- | --- |
| `laya`（english） | 421M（ModernBERT-large） | 512 tok | 英語 |
| `laya-multilingual` | 322M（mmBERT-base） | 1,024（最大 8,192） | 100+ 言語（日本語含む） |
| `laya-typed-decisions` | 421M | 1,024 | typed ワークフロー向け FT 版 |

- 重みは 1GB 未満。CPU でも動く。Router が質問ごとにチェックポイントを自動選択

## 推論方法の選択肢

- [x] **Python ライブラリ直接**: `pip install laya` → `Router().predict(state, questions)`
- [x] **HTTP サーバ（推奨）**: `pip install "laya[serve]"` → `laya-serve`
  - `POST /v1/systemone` で **Jev とワイヤ互換**
  - レスポンスヘッダ `X-Inference-Time-Ms` で純推論時間も取れる
  - 環境変数: `LAYA_DEVICE`, `LAYA_MODELS`, `LAYA_THREADS`, `LAYA_API_KEY` ほか
  - Docker / compose（CUDA 版あり）も同梱
- [ ] ONNX（`laya[onnx]`）/ MLX（Mac 向け別 repo `laya-mlx`）
- vLLM / llama.cpp は **対象外**（生成モデルではないため）
- ファインチューニング: 公式に手順あり。まずは zero-shot で評価

→ HTTP サーバ経由にすれば **Jev と同じクライアントコード** で比較でき、公平。
ただし依存追加（torch 等）はサーバ側に閉じ、本リポジトリは標準ライブラリのままにできる。

## 性能（公式 BENCHMARKS.md、Tesla T4）

| 質問数/呼び出し | laya | laya-multilingual |
| --- | --- | --- |
| 1 | 39.5 ms | 32.8 ms |
| 10 | 158.6 ms | 72.3 ms |

- スループット 103–332 問/秒（バッチ時）
- 精度（公表）: AG News 0.953 / Emotion 0.600 / **Banking77（77 クラス）0.425〜0.492**
- ベース版は typed-decisions ベンチでは多数派ベースライン以下（0.36）。FT 版で 0.766
- 日本語（MASSIVE intent 20 択）: english 0.530 / multilingual 0.640

## 注意点

- **選択肢は ~20 個以下推奨**（選択肢説明が 192〜256 トークン枠を共有）。本タスクは 7 ラベルなので OK
  - ただし `criteria` の説明文が長いと枠を圧迫 → 説明は短めに
- english 版は 512 トークン上限。ログ 1 行なら問題なし
- 日本語や文脈依存の判定は弱め: 中国語業務判定 64 件で multilingual ベースは 20/64（Jev は 64/64）
- 較正は出荷時 over-confident（温度フィットで改善）

## 必要リソース

- CPU で可（`LAYA_THREADS` は物理コア数以下に）。GPU なら T4 級で十分
- ディスク: multilingual のみで約 678MB

## 参考

- https://github.com/NandhaKishorM/laya
- https://huggingface.co/convaiinnovations/laya
- https://pypi.org/project/laya/

## ログ

- 2026-09-27: 初回調査。GitHub リポジトリ（README / BENCHMARKS.md / serve.py）を確認
- 2026-09-27: `backend = "http"`（laya-serve 経由）で実装。model は日本語の criteria に合わせ `multilingual`。実サーバでは未検証
