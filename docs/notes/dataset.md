# データセット・ベンチマーク

## 結論

- Jev / Laya / LLM の先行比較はある（jevbench など）が、題材は一般的なテキスト分類。ログ分類での比較例は見つからない
- EC ログを 7 ラベルで分類した公開データセットは無い。公開ログは異常検知・ログパース・RCA 向け
- 方針: ① jevbench を再現してパイプラインを検証（完了）→ ② 公開ログの付け直し + 合成データで本評価

## 先行ベンチマーク

### jevbench（最も近い）

- https://github.com/dhruvmehra/jevbench （MIT）。再現手順は `tasks/JEVBENCH.md`
- 分類器: Jev 1.13（OpenRouter 経由）/ Laya / GPT-5-mini / Claude Sonnet 5 / DistilBERT FT / BART-large-mnli
- データ: SST2（2 クラス）/ AG News（4）/ Banking77（77）、固定 seed で各 500 件
- 指標は本リポジトリとほぼ同じ（Acc / Macro-F1 / ECE / p50・p95 / スループット / $/1k）。全手法で同じラベル説明、LLM は JSON schema の enum で出力
- 公表値（2026-09-22、Acc %）:

| | SST2 | AG News | Banking77 | p50 ms | $/1k（Banking77） |
| --- | --- | --- | --- | --- | --- |
| Jev | 95.4 | 84.3 | 76.4 | 約 380 | $0.083 |
| Laya | 92.0 | 90.6 | 38.2 | 41–130（ローカル） | 0 |
| GPT-5-mini | 95.0 | 80.2 | 73.6 | 約 1,300 | $0.376 |
| Claude Sonnet 5 | 95.6 | 89.6 | 77.4 | 約 2,000 | $6.43 |
| DistilBERT FT | 91.0 | 91.0 | 88.0 | 6–8 | 0 |

- Laya は少クラスなら Jev 以上だが 77 クラスで崩れる（ECE 0.51）。本タスクの 7 クラスはその中間
- n=500 の 95% 信頼区間は ±2.5pt。SST2 / AG News は LLM の事前学習に含まれる可能性がある

### その他

| 名前 | 内容 | 示唆 |
| --- | --- | --- |
| [jev-eval](https://github.com/4esv/jev-eval) | 自前 JSONL（`id/text/label`）で Jev と OpenRouter のモデルを比較。CLINC 0.897。選択肢 2〜151 個で Jev のレイテンシは 0.17〜0.20s と一定 | `open-jev`（ローカル版？）に言及。未調査 |
| [jev-benchmark](https://github.com/themsquared/jev-benchmark) | ツール呼び出しリスクの 4 クラス分類、60 件。Jev・Sonnet 5 とも 91.7%、Jev が約 3.3 倍速く約 40 倍安い | 少数データでは精度差が出にくい |
| TDS「Jev vs. LLMs」 | 3,080 件で精度・レイテンシ・較正を比較 | 本文未読 |
| DataSci Ocean「193.6x Claim vs. the ~25x Reality」 | 公称「約 200 倍速い」に対し独立計測では 5〜25 倍 | 速度は自前で測る。本文未読 |
| TypeSafe 公式 4-workflow ベンチ | Jev 67.8%、$0.0004/件・0.4s。LLM は $0.03〜0.18/件・10〜38s | 二次情報 |

## ログ系の公開データセット

| データ | 中身 | ラベル | ライセンス | 使い道 |
| --- | --- | --- | --- | --- |
| [Loghub](https://github.com/logpai/loghub) / Loghub-2.0 | 18 システムのログ（Apache、OpenSSH、Proxifier など） | 異常ラベルは一部のみ。2.0 はテンプレート正解付き | 研究・学術目的のみ | OpenSSH → auth / security、Apache → performance / security / normal。テンプレート単位でラベル付け |
| [RCAEval](https://github.com/phamquiluan/RCAEval)（RE2） | Online Boutique・Sock Shop（EC デモ）・Train Ticket に障害注入したログ等。障害 270 件 | 原因サービスと障害種別（CPU / MEM / DISK / DELAY / LOSS / SOCKET） | 要確認 | payment / cart / shipping のログを 7 ラベルに対応付けられる可能性。性能系に偏る |
| arXiv 2601.07790（SLM on System Log Severity） | journalctl 9,355 件 | 重大度 | 未確認 | ラベル体系は違う。Qwen3-4B + RAG が最高（95.6%） |
| [itsrishub/synthetic-logs](https://huggingface.co/datasets/itsrishub/synthetic-logs) | 合成ログ | 重大度 | 未確認 | ラベル体系が違う |
| LogEval（arXiv 2407.01896） | LLM のログ解析ベンチ（各 4,000 件） | タスクごと | 未確認 | 障害診断データは参考になる |
| OWASP Juice Shop | EC の脆弱性デモアプリ | - | MIT | security ラベルのログを自作するなら使える |

## 本評価データの方針

1. 公開ログを 7 ラベルに付け直す（主）: RCAEval RE2（performance・payment・shipping・inventory）、Loghub の OpenSSH / Apache（auth・security・normal）。テンプレート単位でラベルを付け、各テンプレートから数件ずつ抽出
2. 少ないラベル（payment / inventory / shipping）は合成で補う。比較対象の LLM で生成すると有利になるので、テンプレート + 乱数か対象外のモデルで作り、人が確認する。集計は「実ログ由来」「合成」に分ける
3. 件数は 1 クラス 50〜100 件（計 350〜700 件）。±2.5pt より小さい差は結論にしない

## jevbench の再現

### データ

- `uv run hellow-jev-prepare jevbench` で作る。HF に繋がらないため、HF の loading script が読む配布元ファイルを同じ手順で読む
  - AG News / Banking77 は HF の `dataset_infos.json` のチェックサムと一致
  - SST-2 の配布元は 403 のため、sha256 を固定した GitHub ミラーで代用
  - jevbench 本体の `datasets.load()` と出力が完全一致
- 出力（n=500, seed=0）の sha256。作り直したら照合する
  - `jevbench_sst2.jsonl`（negative 256 / positive 244）: `017387da1497fea1c650240af1e25b21c2ecf95ddfc16eaa71b6bb94f7535728`
  - `jevbench_agnews.jsonl`（world 117 / sports 120 / business 128 / sci_tech 135）: `a472cdd563e1bd1ccfdf130be05decf7c5593647af70079fe4d7f566bf3054ed`
  - `jevbench_banking77.jsonl`（77 ラベル全出現、1 ラベル 1〜14 件）: `936a4a3d37d6753bb4eb2233393c9ee01916adeeab354bdaeed937f1201004d4`
- Banking77 は全ラベルが出るので、Macro-F1 の平均の取り方（jevbench は全ラベル、本リポジトリは出現ラベル）の差は影響しない
- SST-2 は全件の文末に空白がある（GLUE の形式）。jevbench と揃えるため strip しない

### 結果（2026-09-29、各 500 件、エラー 0）

Acc。括弧内は jevbench の公表値。詳細は `docs/report.md`。

| | SST-2 | AG News 旧 | AG News 新 | Banking77 | p50 ms |
| --- | --- | --- | --- | --- | --- |
| Jev（TypeSafe 直） | 0.950（0.954） | 0.844（0.843） | 0.856（0.858） | 0.768（0.764） | 165〜175 |
| Laya（M1 8GB, mps） | 0.920（0.920） | 0.906（0.906） | 0.862 | 0.382（0.382） | 102〜279 |
| Haiku 4.5 | 0.960 | 0.832 | 0.850 | 0.758 | 750〜820 |
| Qwen3-4B（M1 8GB） | 0.940 | 0.784 | 0.766 | 0.662 | 690〜1,420 |

- Jev は公表値と 0.6pt 以内、Laya は Acc・Macro-F1 とも小数第 3 位まで一致 → クライアントと指標計算は jevbench と合っている
- Jev の p50 は OpenRouter 経由の公表値（約 380ms）より速い。Laya は公表値（in-process）の約 2〜2.5 倍（HTTP 経由・M1 のため）
- Haiku は GPT-5-mini と Sonnet 5 の間。Banking77 は Jev とほぼ同じだが、コスト/1 万件は Haiku $22.9、Jev $0.83
- AG News の新ラベル説明への反応はモデルで違う: Jev +1.2pt、Laya −4.4、Haiku +1.8、Qwen −1.8

## log_classification（EC ログ 16 件のサンプル）

| | 正解数 | p50 ms |
| --- | --- | --- |
| Jev | 15/16 | 162 |
| Laya | 14/16 | 149 |
| Haiku 4.5 | 16/16 | 914 |
| Qwen3-4B | 15/16 | 546 |

- s003（`INFO auth-svc login success`、正解 normal）は Haiku 以外が auth と誤る（Jev 0.94、Laya 0.91 と高確率）。「auth = Login, session, or token issues」と「normal」の境界が曖昧なタスク定義の問題の可能性

## 計測上の注意

- Python の `http.server` のダミーサーバでは Nagle と遅延 ACK の干渉で p50 が一律約 44ms 上乗せされる。テスト用サーバには `disable_nagle_algorithm = True` を付ける（クライアントは `TCP_NODELAY` 設定済み、laya-serve は uvicorn なので影響なし）
