# データセット・先行ベンチマーク調査メモ

## 結論（2026-09-27 時点）

- **Jev / Laya / LLM を比べた先行ベンチマークはすでにある**（下の jevbench が最も近い）。ただし題材はどれも一般的なテキスト分類（感情・ニュース・銀行の問い合わせ意図）で、**ログ分類で比べた例は見つからなかった**
- **EC ログを本タスクの 7 ラベルで分類した公開データセットは見つからなかった**。公開されているログデータは、異常検知・ログパース・根本原因分析（RCA）向けのものばかり
- → 方針案: ①公開データで jevbench の数値を再現して自前パイプラインを検証し、②公開ログを 7 ラベルに付け直したデータと合成データを組み合わせて本評価に使う

## 先行事例

### jevbench（最も近い）

- https://github.com/dhruvmehra/jevbench （MIT）
- 分類器: Jev 1.13（OpenRouter 経由）/ Laya / GPT-5-mini / Claude Sonnet 5 / DistilBERT FT / BART-large-mnli（zero-shot NLI）
- データ: SST2（2 クラス）/ AG News（4）/ Banking77（77）。いずれも固定 seed で 500 件
- 指標: Acc / Macro-F1 / ECE / p50・p95 / スループット / $/1k。**本リポジトリの指標とほぼ同じ**
- 全 zero-shot 手法で同じラベル説明を使う（本リポジトリと同じ考え方）。LLM は JSON schema の enum で出力させている
- 結果（2026-09-22、n=500、Acc %）:

| | SST2 | AG News | Banking77 | p50 ms | $/1k（Banking77） |
| --- | --- | --- | --- | --- | --- |
| Jev | 95.4 | 84.3 | 76.4 | 約 380 | $0.083 |
| Laya | 92.0 | 90.6 | **38.2** | 41–130（ローカル） | 0 |
| GPT-5-mini | 95.0 | 80.2 | 73.6 | 約 1,300 | $0.376 |
| Claude Sonnet 5 | 95.6 | 89.6 | 77.4 | 約 2,000 | $6.43 |
| DistilBERT FT | 91.0 | 91.0 | 88.0 | 6–8 | 0 |

- 読み取れること
  - Laya はクラス数が少なければ Jev を上回るが、77 クラスで崩れる（ECE 0.51）。**本タスクの 7 クラスはその中間**なので、比べる価値がある
  - Jev の Banking77 は上位 LLM と同等の精度で、約 1/77 のコスト
  - Jev のラベル説明を書き直すと AG News が 84.3 → 85.8 に上がった。説明文の書き方で精度が変わる
- 注意（リポジトリ自身が書いているもの）: n=500 だと 95% 信頼区間は ±2.5pt。SST2 / AG News は LLM の事前学習データに含まれている可能性がある

### その他

| 名前 | 内容 | 本タスクへの示唆 |
| --- | --- | --- |
| [jev-eval](https://github.com/4esv/jev-eval) | 自前の JSONL（`id/text/label`。本リポジトリと同じ形式）で Jev と OpenRouter のモデルを比べるツール。CLINC 0.897。選択肢が 2〜151 個でも Jev のレイテンシは 0.17〜0.20s で変わらない | 選択肢の数でレイテンシが変わらない点は確認する価値がある。`open-jev` というローカル版に触れている（未調査） |
| [jev-benchmark](https://github.com/themsquared/jev-benchmark) | エージェントのツール呼び出しリスクを 4 クラスに分類。手作業ラベル 60 件（Apache-2.0）。Jev と Sonnet 5 はどちらも 91.7%、Jev のほうが約 3.3 倍速く約 40 倍安い | 件数が少ないと精度の差は出にくい。誤答の確信度は低く出ていた（較正が効いている） |
| Towards Data Science「Jev vs. LLMs」 | 3,080 件で精度・レイテンシ・較正を比較 | 本文は未読（egress 制限） |
| DataSci Ocean「193.6x Claim vs. the ~25x Reality」 | 公称の「約 200 倍速い」に対し、独立した計測では 5〜25 倍 | 速度の比較は自前で計測する必要がある。本文は未読 |
| TypeSafe 公式 4-workflow ベンチ | Jev 67.8%、$0.0004/件・0.4s。LLM は $0.03〜0.18/件・10〜38s（検索結果の要約から） | 二次情報 |
| Laya BENCHMARKS.md | `docs/notes/laya.md` を参照 | - |

## ログ系の公開データセット

| データ | 中身 | ラベル | ライセンス | 本タスクでの使い道 |
| --- | --- | --- | --- | --- |
| [Loghub](https://github.com/logpai/loghub) / Loghub-2.0 | 18 システムのログ。Web 系は Apache（エラーログ）、OpenSSH（認証）、Proxifier | 異常ラベルは HDFS・BGL など一部のみ。Loghub-2.0 はテンプレート正解付き | **研究・学術目的のみ**（引用が必要） | OpenSSH → auth / security、Apache → performance / security / normal など。**テンプレート単位でラベルを付ければ**手間が少ない |
| [RCAEval](https://github.com/phamquiluan/RCAEval)（RE2） | **Online Boutique・Sock Shop（EC デモ）**と Train Ticket に障害を注入したときのメトリクス・ログ・トレース。障害 270 件 | 根本原因のサービスと障害の種類（CPU / MEM / DISK / DELAY / LOSS / SOCKET） | 要確認（Zenodo / HF で公開） | 実際の EC マイクロサービスのログ。payment / cart / shipping サービスのログがあるので、サービス名と障害の種類から 7 ラベルに対応付けられる可能性がある。ただし障害は性能系に偏る |
| 論文「SLM on System Log Severity Classification」（arXiv 2601.07790） | Linux の journalctl。評価用 9,355 件 | syslog の重大度 | データを公開しているかは未確認 | ラベルが重大度なので本タスクとは違う。**Qwen3-4B + RAG が 95.6% で最高**だった点は、`llm_local` の選定を裏付ける |
| [itsrishub/synthetic-logs](https://huggingface.co/datasets/itsrishub/synthetic-logs)（HF） | 合成ログ | 重大度（DEBUG〜CRITICAL） | 未確認（HF にアクセスできず） | ラベル体系が違う |
| LogEval（arXiv 2407.01896） | LLM のログ解析ベンチ（パース・異常検知・障害診断・要約。各 4,000 件） | タスクごと | 未確認 | 分類というより「LLM にログが読めるか」の評価。障害診断のデータは参考になる |
| OWASP Juice Shop（EC の脆弱性デモアプリ） | 攻撃ログを自分で作る論文がある | - | MIT（アプリ） | security ラベルのデータを自前で作るなら使える |

- ハーバードの EC Apache アクセスログのように、生ログだけ公開されているものもある。ただしカテゴリのラベルは付いていない

## 方針案

1. **パイプラインの検証（すぐできる）**: Banking77 / AG News から 500 件を取り、jevbench と同じ条件で実行する。Jev・Laya の数値が jevbench と大きくずれなければ、クライアント実装と計測方法が正しいと言える
   - どちらも HF で公開されている。ラベル説明は jevbench のものを流用できる
   - 比較の本題ではないので、`tasks/` に別タスクとして置く
2. **本評価用の EC ログ（主）**: 公開ログを 7 ラベルに付け直す
   - RCAEval RE2 の Online Boutique / Sock Shop のログ（performance・payment・shipping・inventory 周り）
   - Loghub の OpenSSH / Apache（auth・security・normal）
   - ログを直接ではなく**テンプレート単位でラベル付け**し、各テンプレートから数件ずつ抽出する（ラベル付けの手間を減らし、同じ型のログばかりに偏らないようにする）
3. **足りないラベルは合成で補う**: 公開ログに少ない payment / inventory / shipping は合成する
   - 注意: 比較対象の LLM で生成すると、その LLM に有利になりうる。テンプレート + 乱数で作るか、比較対象外のモデルで作り、人が確認する
   - 結果は「実ログ由来」「合成」に分けて集計する
4. **件数**: 7 クラスで 1 クラスあたり 50〜100 件（計 350〜700 件）。n=500 で ±2.5pt なので、それより小さい差は結論にしない

## 未確認・次にやること

- [ ] RCAEval のライセンスと、ログの中身（EC 関連のサービスのログがどれだけあるか）
- [ ] Loghub の「研究・学術目的のみ」が本調査に当てはまるか（社内評価に使えるか）
- [ ] arXiv / dev.to / HF / TDS は egress 制限で本文を読めていない（検索結果の要約のみ）。数値は要確認
- [ ] `open-jev`（jev-eval で言及）が何かを調べる。判定専用×ローカルの候補になりうる

## ログ

- 2026-09-27: 初回調査。先行ベンチ（jevbench / jev-eval / jev-benchmark）と、ログ系の公開データ（Loghub / RCAEval / LogEval など）を調べた
