# jevbench の再現タスク

公開ベンチマーク [jevbench](https://github.com/dhruvmehra/jevbench)（commit `c983cc4`）を本リポジトリのパイプラインで回し、
Jev / Laya のクライアントと計測が公表値と合うかを確かめるためのタスク。

## タスク

| task | データ | ラベル数 |
| --- | --- | --- |
| `jevbench_sst2` | SST-2（映画レビューの感情） | 2 |
| `jevbench_agnews` | AG News（ニュースの話題）・旧ラベル説明 | 4 |
| `jevbench_agnews_v2` | AG News・新ラベル説明（データは同じ） | 4 |
| `jevbench_banking77` | Banking77（銀行アプリの問い合わせ意図） | 77 |

- 各 500 件。jevbench と同じ抽出（n=500, seed=0）を `hellow-jev-prepare` で作る
- 各ディレクトリの中身
  - `task.toml`: ラベル・指示文
  - `prompt.md`: LLM 用（4 つとも同じ内容）
  - `reference.toml`: jevbench の公表値（比較表の参照値）

## 出典・ライセンス

- jevbench は MIT License（Copyright (c) 2026 Dhruv Mehra）
- ラベル名・説明は `src/jevbench/datasets.py`、Jev / Laya の指示文は `src/jevbench/classifiers/jev.py` から、同じ順序・文言で写した
- Banking77 の 77 ラベルは `BANKING77_RAW` から jevbench と同じ変換（`_bank_id` / `_bank_desc`）で機械的に生成した
- 公表値は `docs/results/2026-09-22-n500-summary.md`

## AG News の旧説明 / 新説明

- `55e9102` で AG News のラベル説明だけが書き換えられた（"aligned with dataset convention"）
- 公表表の「jev (new descriptions)」行（Acc 85.8）は新説明
- それ以外の行（jev 84.3・laya・LLM・BERT）は旧説明と**推定**（明記はない）
  - その行だけ名前に "(new descriptions)" が付き、スループットも空欄
  - 直後の記事草稿（`ca57a2c`、のちに削除）に「説明を書き直したら JEV は 1.5 ポイントしか上がらなかった」（84.3 → 85.8）
  - laya・LLM・BERT の行は、コミット時刻から説明変更より前の実行と見ている
- → 旧説明を `jevbench_agnews`、新説明を `jevbench_agnews_v2` に分けた

## state_format

- jevbench は Jev / Laya の `state` にテキストそのもの（文字列）を渡す
- 本リポジトリの既定（`"object"`）は `{"log": テキスト}`。Laya は dict を JSON 文字列にして読むので、モデルへの入力が変わる
- → 4 タスクとも `state_format = "string"` にした。Jev / Laya は共通クライアントなので両方に効く

## 再現になる範囲

同じもの: 指示文・ラベル名と説明（順序も）・`choice` 質問 1 問（質問 ID `label`）・state の形

- ◯ **jev**: jevbench は OpenRouter の Decisions API 経由（`typesafe/jev-1.13`）。本リポジトリは TypeSafe の API を直接呼ぶので、レイテンシは比べられない
- ◯ **laya**: jevbench は laya 0.3.5 を in-process で実行（Apple silicon の Mac）。本リポジトリは laya-serve 経由
  - どちらも english チェックポイント（`convaiinnovations/laya` = `model = "english"`）
  - laya の版や HF の重みの更新で差が出うる（どちらも重みの版は固定していない）
- × **LLM**: jevbench は GPT-5-mini / Claude Sonnet 5（OpenRouter、system プロンプト + JSON スキーマの enum 出力）。本リポジトリの LLM config とはモデルも出力方式も違うので参考値（`prompt.md`）
- × **BERT**（bert-ft / bert-zs）: 本リポジトリに対応するものはない。参考値

### Banking77 の Laya

- Laya の選択肢は 20 個程度までが推奨（全選択肢の説明で 1 つの入力枠を分け合う）
- 77 択では崩れる見込み（jevbench: Acc 38.2%）。上位候補に絞る laya の shortlist 機能は opt-in で、jevbench も本リポジトリも使わない

## 指標の違い

- **Acc**: jevbench はエラー件を分母から除外、本リポジトリは不正解に数える
  - 公表値でエラーがあるのは AG News の jev（0.4% = 2 件）だけ。本リポジトリの数え方なら約 0.840
- **Macro-F1**: エラー件はどちらも見逃し（FN）扱い（jevbench の脚注は「除外」だがコード上はこう）
  - 平均は jevbench が全ラベル、本リポジトリは正解が 1 件以上あるラベル。500 件に全ラベルが出ていれば同じ
- **p50 / p95**: どちらも逐次実行。スループット・ECE は比べない

## 実行

```bash
uv run hellow-jev-prepare jevbench    # 評価データを作る
uv run hellow-jev --config configs/jev.toml --task jevbench_banking77
```
