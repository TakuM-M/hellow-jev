# CLAUDE.md

## プロジェクト概要

OSS **Jev** の手元動作調査リポジトリ。EC などのログ分類タスクで
**Jev（API）/ Laya（open weight）/ LLM（API or ローカル）** をベンチマーク比較する。
計画・未決事項は `docs/plan.md`、各対象の調査メモは `docs/notes/` を参照。

## コマンド

```bash
# ベンチマーク実行（baseline はモデル不要）
PYTHONPATH=src python3 -m hellow_jev.run --config configs/baseline.toml

# 全 config 一括実行
./scripts/run_all.sh

# テスト
uv run --extra dev pytest
```

## 構成の要点

- 分類器は `src/hellow_jev/classifiers/` に置き、`base.Classifier` を継承して `classify()` を実装する
- 新しい分類器は `classifiers/__init__.py` の `REGISTRY` に登録し、`configs/` に toml を追加する
- ラベル定義は `tasks/log_classification/labels.toml`、プロンプトは同ディレクトリの `prompt.md`
- 実行結果は `results/<timestamp>_<name>/` に保存される（git 管理外）

## ルール

- 比較の公平性のため、全モデルで同じプロンプト・ラベル定義・データセットを使う
- Jev / Laya の API 仕様や使い方が不明な場合は推測で実装せず、確認を求める
- `data/raw/`・`data/processed/`・`results/`・`.env`（API キー）はコミットしない
- 追加依存は最小限にする（現状は標準ライブラリのみ）
- 調査で分かったことは `docs/notes/` の該当ファイルに追記する

## コミュニケーション

- 返答は日本語で、スマホで読みやすいよう簡潔にまとめる
- 作業の区切りでは commit & push する
