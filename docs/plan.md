# 調査計画

## 目的

最近公開された OSS **Jev** を手元で動かし、EC などのログ分類タスクで
**Laya（open weight）** および **汎用 LLM** と比較して、精度・速度・コスト・運用性の観点で評価する。

## 比較対象

| 対象 | 利用形態 | ステータス |
| --- | --- | --- |
| Jev | API 利用 | API 仕様調査中 |
| Laya | open weight（ローカル推論 / 推論サーバ） | 利用方法検討中 |
| LLM | API or ローカル | どちらにするか検討中（両方の config を用意） |
| Baseline | キーワードルール | 実装済み（パイプライン疎通確認用） |

## 評価観点

1. **精度**: Accuracy / Macro-F1 / クラス別 P・R、混同行列
2. **速度**: 1 件あたりレイテンシ、スループット
3. **コスト**: API 料金・トークン数 / ローカルの場合の GPU・メモリ要件
4. **運用性**: セットアップ容易性、出力の安定性（ラベル外出力の率）、再現性

## 実験条件を揃えるためのルール

- プロンプトは `tasks/log_classification/prompt.md` を共通で使う
- 同一データセット・同一ラベル定義で評価する（`tasks/<task>/task.toml` で一元管理し、モデル別 config には書かない）
- temperature 等のサンプリング設定は config に明記する
- 実行結果は `results/<timestamp>_<name>/` に config / meta / metrics / predictions を保存

## マイルストーン

- [x] ブランチ初期化・ディレクトリ構成・共通パイプライン
- [ ] Jev の API 仕様を調べて `classifiers/jev.py` を実装
- [ ] LLM の利用形態を決定し実装（api / local）
- [ ] Laya の推論方法を決定し実装
- [ ] 評価用データセットの用意（実ログ or 公開データ）とラベル付け
- [ ] 本評価の実行・結果まとめ（`docs/report.md`）
