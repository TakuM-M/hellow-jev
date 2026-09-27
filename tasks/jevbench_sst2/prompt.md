# jevbench 再現用プロンプト（LLM 用。4 タスク共通）

LLM に渡すプロンプト。`---` より下がテンプレートで、この説明部分はモデルに送られない。
`{instructions}`（task.toml）・`{labels}`（`- ラベル名: 説明` の行）・`{log}`（分類するテキスト）は実行時に置き換える。
jevbench_sst2 / agnews / agnews_v2 / banking77 で同じ内容にしている（直すときは 4 つとも直す）。

## 元にしたもの

jevbench の LLM 用 system プロンプト（`src/jevbench/classifiers/llm.py` の `build_messages`）:
"You are a text classifier. Classify the user's text into exactly one of these labels." の後に
`Labels:` とラベル一覧、最後に JSON だけで答えるよう指示する（`Respond with JSON only: ...`）。
分類するテキストは別の user メッセージで渡している。

## 本リポジトリの LLM クライアントに合わせた変更

- user メッセージ 1 通にまとめる（`classifiers/llm.py` は system プロンプトを使わない）
- JSON スキーマ（ラベルの enum）で出力を縛らず、ラベル名だけを答えさせる。ラベル外の出力は invalid として集計する
- 指示文は jevbench が Jev / Laya に渡すもの（`{instructions}`）を使う。全モデルで同じ指示文を使うというこのリポジトリのルールに従う
- Jev / Laya はプロンプト文字列を受け取らない。同じ instructions とラベル説明を `choice` 質問で渡す（state はテキストそのもの）

## 再現になる範囲

jevbench の LLM は OpenRouter 経由の GPT-5-mini / Claude Sonnet 5 で、JSON スキーマの enum で出力を縛り、
reasoning effort も指定している。本リポジトリの LLM config とはモデルも出力方式も違うので、LLM の行は参考値。
直接の再現になるのは Jev と Laya の行だけ（tasks/JEVBENCH.md）。

---

You are a text classifier.
{instructions}

Labels:
{labels}

Answer with the label name only.

Text:
{log}
