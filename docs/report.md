## log_classification

| model | n | Acc | Macro-F1 | ラベル外率 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 16 | 0.938 | 0.943 | 0.000 | 0.000 | 158.5 | 188.4 | - | 476 | $0.1999 | API (TypeSafe) | 20260928T102407Z_jev |
| llm_api<br>claude-haiku-4-5-20251001 | 16 | 1.000 | 1.000 | 0.000 | 0.000 | 650.7 | 743.5 | - | 184 | $2.0425 | API (Anthropic) | 20260928T102411Z_llm_api |
| laya | 16 | 0.875 | 0.876 | 0.000 | 0.000 | 155.2 | 176.1 | 153.2 | 146 | $0 | Apple M1 (8GB), mps | 20260928T102440Z_laya |
| llm_local<br>qwen3:4b-instruct | 16 | 0.875 | 0.876 | 0.000 | 0.000 | 268.5 | 413.0 | - | 170 | $0 | Apple M1 (8GB) | 20260928T102448Z_llm_local |

## 注記

- p50 / p95 はクライアント側の往復時間（API はネットワーク込み）。warmup 分・エラー件は除外
- 接続は使い回す（keep-alive）。張り直した件数は metrics.json の new_connections
- エラー率はリトライしても応答が得られなかった件の割合（Acc では不正解として数える）
- サーバ p50 はサーバが返す純推論時間（X-Inference-Time-Ms ヘッダがある場合のみ。laya は 0.3.21 以降が返し、0.3.20 と Jev は返さない）
- コストは集計時点の configs/<name>.toml の [pricing]（USD / 1M tokens）から概算（無ければ実行時の config）。未設定は -
- ローカル実行（laya / llm_local）は API 課金が無いので $0。マシン代・電力は含まない
- 実行環境は実行時の config の hardware（無ければ実行マシンの CPU）。API はリクエスト先を書く
