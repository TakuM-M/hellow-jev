# hellow-jev

**Jev**（TypeSafe AI の判定特化 API）を手元から呼び出して調べるためのリポジトリ。
EC などのログ分類を題材に、**Jev / Laya / LLM** の 3 つをベンチマークで比較する。

計画の詳細は [`docs/plan.md`](docs/plan.md) を参照。

## ディレクトリ構成

```
.
├── configs/                 # 実行設定（モデルごとに 1 ファイル。タスク名・分類器設定・warmup・実行環境・単価）
├── data/
│   ├── samples/             # 動作確認用の合成サンプル（コミットする）
│   ├── raw/                 # 生ログ（git 管理外）
│   └── processed/           # 前処理済みデータ（git 管理外）
├── docs/
│   ├── plan.md              # 調査計画・評価観点・マイルストーン
│   └── notes/               # Jev / Laya / LLM それぞれの調査メモ
├── results/                 # 実行結果（git 管理外）
├── scripts/                 # 一括実行などのスクリプト
├── src/hellow_jev/
│   ├── classifiers/         # Jev / Laya / LLM の分類器と共通 HTTP クライアント
│   ├── envfile.py           # .env の読み込み
│   ├── metrics.py           # 評価指標
│   ├── prepare/             # 評価データを取得・抽出する CLI（core: 汎用処理、jevbench: データ定義）
│   ├── run.py               # ベンチマーク実行 CLI
│   ├── report.py            # 比較表（Markdown）を作る CLI
│   ├── task.py              # タスク定義・データの読み込み
│   └── util.py              # ハッシュ・書き込み・Markdown 表などの共通処理
├── tasks/
│   ├── log_classification/  # 本題のタスク定義（データセット・ラベル）と共通プロンプト
│   └── jevbench_*/          # 公開ベンチ jevbench の再現用タスク（説明は tasks/JEVBENCH.md）
└── tests/
```

## 使い方

```bash
cp .env.example .env         # API キーなどを設定（実行時に自動で読み込む。既存の環境変数が優先）

# 1 つだけ実行（LLM API の例。LLM_API_KEY が必要）
uv run hellow-jev --config configs/llm_api.toml

# 全 config をまとめて実行
./scripts/run_all.sh

# 比較表を作る（タスクごとに表を分け、(タスク, config) ごとに最新の run を集計）
uv run hellow-jev-report --out docs/report.md

# テスト
uv run --extra dev pytest
```

Laya は推論サーバ `laya-serve` を別環境で立ててから実行する（手順は [`docs/notes/laya.md`](docs/notes/laya.md)）。

### jevbench の再現（パイプラインの検証）

公開ベンチ [jevbench](https://github.com/dhruvmehra/jevbench) と同じ 500 件・同じラベル説明で Jev / Laya を回し、
公表値と比べて、このリポジトリのクライアントと計測が正しいかを確かめる（詳細は [`tasks/JEVBENCH.md`](tasks/JEVBENCH.md)）。

```bash
uv run hellow-jev-prepare jevbench                           # SST-2 / AG News / Banking77 を 500 件ずつ作る
./scripts/run_jevbench.sh configs/jev.toml configs/laya.toml # 4 タスク × 指定 config（省略時は configs/*.toml）
uv run hellow-jev-report --out docs/report.md                # jevbench の公表値も参考値として並ぶ
```

1 タスクだけ回すときは `uv run hellow-jev --config configs/jev.toml --task jevbench_banking77`。

結果は `results/<timestamp>_<name>/` に次のファイルとして保存される。

| ファイル | 中身 |
| --- | --- |
| `config.json` | 実行時の config |
| `meta.json` | データ・タスク定義・プロンプトのハッシュ、git commit、実行マシン情報 |
| `predictions.jsonl` | 1 件ごとの予測（1 件ずつ追記） |
| `metrics.json` | 評価指標・レイテンシ（完走時のみ出力） |

各対象の実装状況は [`docs/plan.md`](docs/plan.md) の「比較対象」を参照（二重管理を避けるため、ここには書かない）。
