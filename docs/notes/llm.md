# LLM（比較対象）調査メモ

- 利用形態: API or ローカル（検討中）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 位置づけ

- Jev / Laya は「判定専用・生成なし」モデル。LLM は **生成で答える汎用モデル** のベースライン
- 比較の論点: 精度は LLM が上か？ レイテンシ・コストで Jev/Laya がどれだけ有利か？

## 判断材料

| 観点 | API | ローカル |
| --- | --- | --- |
| 精度 | 高性能モデルを使える | モデルサイズ次第 |
| コスト | 従量課金 | GPU 等の初期コスト |
| データ取り扱い | ログを外部送信する | 手元で完結 |
| 再現性 | モデル更新の影響あり | バージョン固定しやすい |
| レイテンシ | ネットワーク込み・生成分遅い | GPU 次第 |

## 候補モデル（案）

- API: 小型・高速クラスを優先（例: Claude Haiku 4.5 など各社の軽量モデル）
  - Jev と同じく「安くて速い」土俵で比べるため。精度上限の参考に上位モデルを 1 つ足すのも可
- ローカル: Qwen3 系 4B〜8B 程度を Ollama / vLLM の **OpenAI 互換 API** で
  - 実装を `/v1/chat/completions` 1 本にでき、標準ライブラリで書ける
- 料金・モデル ID は実装時に公式ドキュメントで確認する

## 実装メモ

- 共通プロンプト `tasks/log_classification/prompt.md` を使用、temperature=0、max_tokens 小さめ
- ラベル外出力は `normalize()` で fallback → **ラベル外出力率** も記録する
- レイテンシは TTFT ではなく **応答完了まで** の時間で比較（Jev/Laya と揃える）

## 関連（参考）

- mini-jev: Qwen3-4B の logits で Jev 風インターフェースを実現する試み
- Kev-9B: Apache-2.0 の Jev 代替（精度が Jev に近いと報告）

## ログ

- 2026-09-27: Jev / Laya 調査を踏まえ位置づけと候補を整理
