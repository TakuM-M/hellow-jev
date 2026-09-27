# CLAUDE.md

## プロジェクト概要

**Jev**（TypeSafe AI の判定特化 API）の手元動作調査リポジトリ。EC などのログ分類タスクで
**Jev（API）/ Laya（open weight）/ LLM（API or ローカル）** をベンチマーク比較する。
計画・未決事項は `docs/plan.md`、各対象の調査メモは `docs/notes/` を参照。

## コマンド

```bash
# ベンチマーク実行（例: LLM API。LLM_API_KEY が必要）
uv run hellow-jev --config configs/llm_api.toml

# 全 config 一括実行
./scripts/run_all.sh

# 比較表（config ごとの最新 run を集計）
uv run hellow-jev-report --out docs/report.md

# Laya 推論サーバ（Jev 互換 HTTP。別環境で起動）
pip install "laya[serve]" && LAYA_MODELS=english laya-serve

# テスト
uv run --extra dev pytest
```

## 構成の要点

- LLM は `classifiers/llm.py`。`api_format` で Anthropic Messages API / OpenAI 互換 Chat Completions を切替（`backend = "api" | "local"`）
- Jev と Laya は同じ `/v1/systemone` プロトコルなので `classifiers/systemone.py` の共通クライアントを使う（接続先・キーだけ違う）
- 分類器は `src/hellow_jev/classifiers/` に置き、`base.Classifier` を継承して `classify()` を実装する
- 新しい分類器は `classifiers/__init__.py` の `REGISTRY` に登録し、`configs/` に toml を追加する
- `configs/*.toml` はタスク名と分類器設定だけを持つ。データセット・ラベルはタスク側で一元管理する
- タスク定義（dataset / instructions / labels）は `tasks/log_classification/task.toml`、プロンプトは同ディレクトリの `prompt.md`
- ラベル外の出力は既定ラベルに寄せず `Prediction.label = None` とし、`invalid_rate` として集計する
- HTTP は `classifiers/_http.py` の `HTTPClient` に集約（全分類器で同じリトライ条件。接続は keep-alive で使い回し、張り直した件数は `metrics.json` の `new_connections`）。リトライしても失敗した件は run を止めずに `error` として記録し、`error_rate` で集計する（連続 `max_consecutive_errors` 件で打ち切り）
- 実行結果は `results/<timestamp>_<name>/` に保存される（git 管理外）。`predictions.jsonl` は 1 件ずつ追記され、`metrics.json` は完走時のみ書かれる。`meta.json` に入力ハッシュ・git commit・実行マシン情報が残る
- レイテンシは p50 / p95（warmup 除外）で比較する。`metrics.json` の `latency` を参照

## ルール

- 比較の公平性のため、全モデルで同じプロンプト・ラベル定義・データセットを使う
- モデルに渡すテキスト（instructions・ラベル description・prompt テンプレート）は英語で統一する
- Jev / Laya の API 仕様や使い方が不明な場合は推測で実装せず、確認を求める
- `data/raw/`・`data/processed/`・`results/`・`.env`（API キー）はコミットしない
- 追加依存は最小限にする（現状は標準ライブラリのみ）
- 調査で分かったことは `docs/notes/` の該当ファイルに追記する

## コミュニケーション

- 返答は日本語で、スマホで読みやすいよう簡潔にまとめる
- 作業の区切りでは commit & push する
