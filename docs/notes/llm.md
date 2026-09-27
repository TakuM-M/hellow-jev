# LLM（比較対象）調査メモ

- 利用形態: API or ローカル（検討中）
- 実装: `src/hellow_jev/classifiers/llm.py`（`backend = "api" | "local"`）
- 設定: `configs/llm_api.toml`, `configs/llm_local.toml`

## 判断材料

| 観点 | API | ローカル |
| --- | --- | --- |
| 精度 | 高性能モデルを使える | モデルサイズ次第 |
| コスト | 従量課金 | GPU 等の初期コスト |
| データ取り扱い | ログを外部送信する | 手元で完結 |
| 再現性 | モデル更新の影響あり | バージョン固定しやすい |

## 候補モデル

<!-- 試すモデル名を列挙 -->

## ログ
