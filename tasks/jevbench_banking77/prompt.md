# jevbench 再現用プロンプト（LLM 用。4 タスク共通）

LLM に渡すプロンプト。`---` より下がテンプレートで、この説明部分はモデルに送られない。
`[system]` 以下が system メッセージ、`[user]` 以下が user メッセージになる。
`{labels}`（`- ラベル名: 説明` の行）・`{log}`（分類するテキスト）は実行時に置き換える。
jevbench_sst2 / agnews / agnews_v2 / banking77 で同じ内容にしている（直すときは 4 つとも直す）。

## 元にしたもの

jevbench の LLM 用プロンプト（`src/jevbench/classifiers/llm.py`、c983cc4）をそのまま写した:

- system: `build_messages` の文言（空行・句読点も同じ）
- user: 分類するテキストだけ
- 出力: `{"label": <ラベル名の enum>}` の JSON スキーマに縛る（`build_response_format` と同じ。`classifiers/llm.py` が全タスク共通で付ける）

## 本リポジトリの他のタスクとの違い

- **指示文（task.toml の `instructions`）を入れない**。jevbench の LLM プロンプトに無いため。
  Jev / Laya には渡しているので、「全モデルで同じ指示文」（CLAUDE.md）の例外になる。再現を優先した
- モデル・`max_tokens`・`reasoning`（jevbench は effort=low）は config 側の設定で、jevbench とは揃えていない。LLM の行は参考値のまま

---

[system]
You are a text classifier. Classify the user's text into exactly one of these labels.
Labels:
{labels}

Respond with JSON only: {"label": "<label id>"}.

[user]
{log}
