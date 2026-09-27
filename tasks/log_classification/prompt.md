# ログ分類プロンプト（共通テンプレート）

LLM に渡すプロンプト。`---` より下がテンプレートで、この説明部分はモデルに送られない。
`{instructions}`（task.toml）・`{labels}`・`{log}` は実行時に置き換える。
Jev / Laya はプロンプト文字列を受け取らないので、同じ instructions とラベルの description を
`choice` 質問（instructions / criteria）として渡し、条件を揃える。

---

You are a log classifier for an e-commerce system.
{instructions}

{labels}

Answer with the label name only.

Log:
{log}
