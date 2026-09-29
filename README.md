# hellow-jev

[English](#english) | [日本語](#日本語)

---

## English

**Jev:**
- TypeSafe AI, System One Model
- An encoder model specialized for classification (judgment).

### Overview
Using log classification (e.g. e-commerce logs) as the subject, this repository benchmarks three approaches: **Jev / Laya / LLM**.

#### Compared models

| | API | Local |
| --- | --- | --- |
| Classification-specific | Jev (TypeSafe AI, closed) | Laya (open weight) |
| General-purpose LLM | Claude Haiku 4.5 | Qwen3 4B (OpenAI-compatible API) |

No fine-tuning. All models are evaluated zero-shot.

#### Evaluation criteria and measurement

1. **Accuracy**: Accuracy / Macro-F1 / per-class P・R, confusion matrix
2. **Speed**: per-item latency (p50 / p95 / mean)
3. **Cost**: API pricing and token counts
4. **Operability**: output stability (error rate, out-of-label rate)

- Latency is measured as client-side round-trip time (API calls include the network). For Laya, pure inference time from `X-Inference-Time-Ms` can be shown alongside
- The executing machine is recorded with the results (`host` in `meta.json`, `hardware` in the config)
- The comparison table `docs/report.md` is split per task, with one row per (task, config) for the latest completed run. Tasks with `tasks/<task>/reference.toml` also list published values as references

### jevbench results (own measurements)

Accuracy (p50 latency) on [jevbench](https://github.com/dhruvmehra/jevbench) tasks, n=500 each, measured 2026-09-29. Jev / Claude Haiku 4.5 via API; Laya / Qwen3 4B on Apple M1 (8GB). Best Acc per task in bold.

| model | [SST-2](docs/report.md#jevbench_sst2) | [AG News](docs/report.md#jevbench_agnews) | [AG News v2](docs/report.md#jevbench_agnews_v2) | [Banking77](docs/report.md#jevbench_banking77) |
| --- | --- | --- | --- | --- |
| Jev | 0.950 (168 ms) | 0.844 (169 ms) | 0.856 (165 ms) | **0.768** (175 ms) |
| Laya | 0.920 (102 ms) | **0.906** (141 ms) | **0.862** (178 ms) | 0.382 (279 ms) |
| Claude Haiku 4.5 | **0.960** (799 ms) | 0.832 (749 ms) | 0.850 (768 ms) | 0.758 (820 ms) |
| Qwen3 4B | 0.940 (686 ms) | 0.784 (990 ms) | 0.766 (954 ms) | 0.662 (1416 ms) |

- AG News v2 uses jevbench's new label descriptions
- For Macro-F1, p95, cost, jevbench published values, and error analysis, see [`docs/report.md`](docs/report.md)

### Directory structure

```
.
├── configs/                 # Run configs (one file per model: task name, classifier settings, warmup, hardware, pricing)
├── data/
│   ├── samples/             # Synthetic samples for smoke tests (committed)
│   ├── raw/                 # Raw logs (not tracked by git)
│   └── processed/           # Preprocessed data (not tracked by git)
├── docs/
│   └── notes/               # Research notes for Jev / Laya / LLM
├── results/                 # Run results (not tracked by git)
├── scripts/                 # Scripts such as batch runs
├── src/hellow_jev/
│   ├── classifiers/         # Jev / Laya / LLM classifiers and shared HTTP client
│   ├── envfile.py           # Loads .env
│   ├── metrics.py           # Evaluation metrics
│   ├── prepare/             # CLI to fetch/extract evaluation data (core: generic, jevbench: data definitions)
│   ├── run.py               # Benchmark runner CLI
│   ├── report.py            # CLI to build the comparison table (Markdown)
│   ├── task.py              # Loads task definitions and data
│   └── util.py              # Shared helpers: hashing, writing, Markdown tables, etc.
├── tasks/
│   ├── log_classification/  # Main task definition (dataset, labels) and shared prompt
│   └── jevbench_*/          # Tasks reproducing the public jevbench benchmark (see tasks/JEVBENCH.md)
└── tests/
```

### Usage

```bash
cp .env.example .env         # Set API keys etc. (loaded automatically at run time; existing env vars take precedence)

# Run a single config (LLM API example; requires LLM_API_KEY)
uv run hellow-jev --config configs/llm_api.toml

# Run all configs
./scripts/run_all.sh

# Build the comparison table (one table per task, latest run per (task, config))
uv run hellow-jev-report --out docs/report.md

# Tests
uv run --extra dev pytest
```

For Laya, start the inference server `laya-serve` in a separate environment first (see [`docs/notes/laya.md`](docs/notes/laya.md)).

#### Reproducing jevbench

Compare against the published values of the public benchmark [jevbench](https://github.com/dhruvmehra/jevbench) to verify that this repository's clients and measurements are correct (details in [`tasks/JEVBENCH.md`](tasks/JEVBENCH.md)).

```bash
uv run hellow-jev-prepare jevbench                           # Build 500 items each of SST-2 / AG News / Banking77
./scripts/run_jevbench.sh configs/jev.toml configs/laya.toml # 4 tasks × given configs (defaults to configs/*.toml)
uv run hellow-jev-report --out docs/report.md                # jevbench published values are listed as references
```

---

## 日本語

**Jev:**
- TypeSafe AI, System One Model
- 判定特化のエンコードモデル。

### 概要
EC などのログ分類を題材に、**Jev / Laya / LLM** の 3 つをベンチマークで比較する。

#### 比較対象

| | API | ローカル |
| --- | --- | --- |
| 判定専用 | Jev（TypeSafe AI・クローズド） | Laya（open weight） |
| 汎用 LLM | Claude Haiku 4.5 | Qwen3 4B（OpenAI 互換 API） |

ファインチューニングはしない。全モデル zero-shot で揃える

#### 評価観点と計測

1. **精度**: Accuracy / Macro-F1 / クラス別 P・R、混同行列
2. **速度**: 1 件あたりのレイテンシ（p50 / p95 / 平均）
3. **コスト**: API 料金・トークン数
4. **運用性**: 出力の安定性（エラー率・ラベル外率）

- クライアント側の往復時間で揃える（API はネットワーク込み）。Laya は `X-Inference-Time-Ms` で純推論時間も併記できる
- 実行マシンを結果に残す（`meta.json` の `host`、config の `hardware`）
- 比較表 `docs/report.md` はタスクごとに分け、(タスク, config) ごとに最新の完走 run を 1 行にする。`tasks/<task>/reference.toml` があるタスクは公表値を参考値として並べる

### jevbench の結果（実測）

[jevbench](https://github.com/dhruvmehra/jevbench) の各タスク（各 500 件、2026-09-29 計測）の Accuracy（括弧内は p50 レイテンシ）。Jev / Claude Haiku 4.5 は API、Laya / Qwen3 4B は Apple M1 (8GB) で実行。太字はタスクごとの最高 Acc。

| model | [SST-2](docs/report.md#jevbench_sst2) | [AG News](docs/report.md#jevbench_agnews) | [AG News v2](docs/report.md#jevbench_agnews_v2) | [Banking77](docs/report.md#jevbench_banking77) |
| --- | --- | --- | --- | --- |
| Jev | 0.950 (168 ms) | 0.844 (169 ms) | 0.856 (165 ms) | **0.768** (175 ms) |
| Laya | 0.920 (102 ms) | **0.906** (141 ms) | **0.862** (178 ms) | 0.382 (279 ms) |
| Claude Haiku 4.5 | **0.960** (799 ms) | 0.832 (749 ms) | 0.850 (768 ms) | 0.758 (820 ms) |
| Qwen3 4B | 0.940 (686 ms) | 0.784 (990 ms) | 0.766 (954 ms) | 0.662 (1416 ms) |

- AG News v2 は jevbench の新ラベル説明を使ったもの
- Macro-F1・p95・コスト・jevbench 公表値・誤り分析は [`docs/report.md`](docs/report.md) を参照

### ディレクトリ構成

```
.
├── configs/                 # 実行設定（モデルごとに 1 ファイル。タスク名・分類器設定・warmup・実行環境・単価）
├── data/
│   ├── samples/             # 動作確認用の合成サンプル（コミットする）
│   ├── raw/                 # 生ログ（git 管理外）
│   └── processed/           # 前処理済みデータ（git 管理外）
├── docs/
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

### 使い方

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

#### jevbench の再現

公開ベンチ [jevbench](https://github.com/dhruvmehra/jevbench) の公表値と比べて、このリポジトリのクライアントと計測が正しいかを確かめる（詳細は [`tasks/JEVBENCH.md`](tasks/JEVBENCH.md)）。

```bash
uv run hellow-jev-prepare jevbench                           # SST-2 / AG News / Banking77 を 500 件ずつ作る
./scripts/run_jevbench.sh configs/jev.toml configs/laya.toml # 4 タスク × 指定 config（省略時は configs/*.toml）
uv run hellow-jev-report --out docs/report.md                # jevbench の公表値も参考値として並ぶ
```
