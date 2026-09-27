# Laya 調査メモ

- 利用形態: open weight（使い方は検討中）
- 実装: `src/hellow_jev/classifiers/laya.py`
- 設定: `configs/laya.toml` / 環境変数 `LAYA_MODEL_PATH`, `LAYA_ENDPOINT`

## 検討中の選択肢

- [ ] transformers で直接推論
- [ ] vLLM 等の推論サーバ（OpenAI 互換 API）経由
- [ ] llama.cpp / GGUF 量子化で CPU・小規模 GPU
- [ ] ファインチューニングの要否（zero-shot / few-shot で十分か）

## 必要リソース

<!-- モデルサイズ、VRAM、推論速度などを記録 -->

## ログ
