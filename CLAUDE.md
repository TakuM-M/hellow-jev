# CLAUDE.md

Jev（判定特化 API）/ Laya（open weight）/ LLM をログ分類でベンチマーク比較するリポジトリ。
計画は `docs/plan.md`、調査メモは `docs/notes/`、jevbench 再現は `tasks/JEVBENCH.md`。

## コマンド

```bash
uv run hellow-jev --config configs/jev.toml [--task jevbench_banking77]
uv run hellow-jev-report --out docs/report.md
uv run --extra dev pytest
```

## 構成

- 分類器は `src/hellow_jev/classifiers/`（`base.Classifier` 継承 → `REGISTRY` 登録 → `configs/*.toml` 追加）。Jev と Laya は共通の `systemone.py`
- タスク定義は `tasks/<task>/task.toml`、LLM プロンプトは `prompt.md`。config はタスク名と分類器設定のみ
- API キー・接続先は環境変数（`.env`）のみ。config に書かない

## ルール

- 公平性のため全モデルで同じ指示文・ラベル・データを使う。モデルへのテキストは英語
  - 例外: jevbench 再現タスク（`tasks/jevbench_*`）の LLM は jevbench のプロンプトをそのまま使い、指示文を渡さない（`tasks/JEVBENCH.md`）
- Jev / Laya の API 仕様が不明なら推測で実装せず確認する
- `data/`・`results/`・`.env` はコミットしない。依存は標準ライブラリのみ
- 分かったことは `docs/notes/` に追記
- 返答は日本語で完結