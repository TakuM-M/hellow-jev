# hellow-jev

OSS **Jev** の手元動作調査用リポジトリ。
EC などのログ分類タスクを題材に、**Jev / Laya / LLM** の 3 つをベンチマーク的に比較する。

詳細な計画は [`docs/plan.md`](docs/plan.md) を参照。

## ディレクトリ構成

```
.
├── configs/                 # 実行設定（モデルごとに 1 ファイル。タスク名と分類器設定のみ）
├── data/
│   ├── samples/             # 動作確認用の合成サンプル（コミット対象）
│   ├── raw/                 # 生ログ（git 管理外）
│   └── processed/           # 前処理済みデータ（git 管理外）
├── docs/
│   ├── plan.md              # 調査計画・評価観点・マイルストーン
│   └── notes/               # jev / laya / llm それぞれの調査メモ
├── notebooks/               # 分析用ノートブック
├── results/                 # 実行結果（git 管理外）
├── scripts/                 # 一括実行などのスクリプト
├── src/hellow_jev/
│   ├── classifiers/         # baseline / jev / laya / llm の分類器
│   ├── metrics.py           # 評価指標
│   ├── run.py               # ベンチマーク実行 CLI
│   └── task.py              # タスク定義・データ読み込み
├── tasks/log_classification/  # タスク定義（データセット・ラベル）・共通プロンプト
└── tests/
```

## 使い方

```bash
cp .env.example .env         # API キー等を設定

# 単体実行（baseline はモデル不要で動く）
uv run hellow-jev --config configs/baseline.toml

# 全設定を一括実行
./scripts/run_all.sh

# テスト
uv run --extra dev pytest
```

結果は `results/<timestamp>_<name>/` に `config.json` / `meta.json`（データ・プロンプトのハッシュ、git commit）/ `metrics.json` / `predictions.jsonl` として保存される。

各対象の実装状況は [`docs/plan.md`](docs/plan.md) の「比較対象」を参照（二重管理を避けるためここには書かない）。
