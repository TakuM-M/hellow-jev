# 調査計画

## 目的

最近公開された OSS **Jev** を手元で動かし、EC などのログ分類タスクで
**Laya（open weight）** および **汎用 LLM** と比較して、精度・速度・コスト・運用性の観点で評価する。

## 比較対象

| 対象 | 利用形態 | ステータス |
| --- | --- | --- |
| Jev | API 利用（TypeSafe AI・クローズド） | API 形式判明（`POST /v1/systemone`） |
| Laya | open weight（`laya-serve` で Jev 互換 HTTP） | 推論方法ほぼ決定 |
| LLM | API or ローカル | どちらにするか検討中（両方の config を用意） |
| Baseline | キーワードルール | 実装済み（パイプライン疎通確認用） |

## 評価観点

1. **精度**: Accuracy / Macro-F1 / クラス別 P・R、混同行列
2. **速度**: 1 件あたりレイテンシ、スループット
3. **コスト**: API 料金・トークン数 / ローカルの場合の GPU・メモリ要件
4. **運用性**: セットアップ容易性、出力の安定性（ラベル外出力の率）、再現性

## 調査で分かった前提（2026-09-27）

- Jev / Laya は **プロンプト文字列を受け取らない**。`state`（ログ）＋ `choice` 質問（`criteria` = ラベル定義）で判定する
- よって「同じプロンプト」ではなく **同じラベル定義（`labels.toml` の description）と同じ指示文** で揃える
  - Jev/Laya: `instructions` = 指示文、`criteria` = `{name: description}`
  - LLM: `prompt.md` に同じ指示文と description を埋め込む
- Laya の `laya-serve` は Jev とワイヤ互換 → **同一クライアント**で `base_url` だけ切替可能
- 詳細は `docs/notes/{jev,laya,llm}.md`

## 最終出力（比較表）のイメージ

`results/` の各 run を集計して `docs/report.md` に表を出す（集計スクリプトを追加予定）。

| model | Acc | Macro-F1 | p50 ms | p95 ms | 件/秒 | ラベル外率 | 入力tok/件 | 概算コスト/1万件 | 実行環境 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | | | | | | | | 0 | CPU |
| jev | | | | | | 0 | | | API |
| laya | | | | | | 0 | | 0 | CPU/GPU |
| llm_api | | | | | | | | | API |
| llm_local | | | | | | | | 0 | GPU |

レイテンシ計測のルール:

- 1 件ずつ直列・ウォームアップ数件を除外し、**p50 / p95 / 平均** を出す（現状は平均のみ → 追加が必要）
- クライアント側の往復時間で揃える（API はネットワーク込みと明記）
- Laya は `X-Inference-Time-Ms` で純推論時間も併記できる
- 実行マシン（CPU/GPU）を結果に記録する

## 実験条件を揃えるためのルール

- プロンプトは `tasks/log_classification/prompt.md` を共通で使う
- 同一データセット・同一ラベル定義で評価する（`tasks/<task>/task.toml` で一元管理し、モデル別 config には書かない）
- temperature 等のサンプリング設定は config に明記する
- 実行結果は `results/<timestamp>_<name>/` に config / meta / metrics / predictions を保存

## マイルストーン

- [x] ブランチ初期化・ディレクトリ構成・共通パイプライン
- [x] 各モデルの初回調査（`docs/notes/`）
- [ ] Jev の API 仕様を調べて `classifiers/jev.py` を実装
- [ ] LLM の利用形態を決定し実装（api / local）
- [ ] Laya の推論方法を決定し実装
- [ ] 評価用データセットの用意（実ログ or 公開データ）とラベル付け
- [ ] metrics に p50/p95・ラベル外率を追加、比較表の集計スクリプト
- [ ] 本評価の実行・結果まとめ（`docs/report.md`）
