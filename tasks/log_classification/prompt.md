# ログ分類プロンプト（共通テンプレート）

LLM に渡すプロンプト。`---` より下がテンプレートで、この説明部分はモデルに送られない。
`[system]` 以下が system メッセージ、`[user]` 以下が user メッセージになる。
`{instructions}`（task.toml）・`{labels}`・`{text}` は実行時に置き換える。
Jev / Laya はプロンプト文字列を受け取らないので、同じ instructions とラベルの description を
`choice` 質問（instructions / criteria）として渡し、条件を揃える。

## 形式

jevbench の LLM プロンプト（`tasks/jevbench_*/prompt.md`）と同じ形にしている:

- system: 役割・指示文・ラベル一覧・JSON で答える指示。user: 分類するログだけ
- 答えは `classifiers/llm.py` が `{"label": <ラベル名の enum>}` の JSON スキーマで縛る。
  Jev / Laya と同じく「選択肢から 1 つ選ぶ」条件になり、ラベル外は生成されない
- jevbench と違い、指示文（`{instructions}`）は入れる（全モデルで同じ指示文を使うルール。CLAUDE.md）

---

[system]
You are a log classifier for an e-commerce system.
{instructions}

{labels}

Respond with JSON only: {"label": "<label id>"}.

[user]
{text}
