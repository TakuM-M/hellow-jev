# ログ分類プロンプト（共通テンプレート）

jev / laya / llm で同一のプロンプトを使い、条件を揃える。
`{instructions}`（task.toml）・`{labels}`・`{log}` は実行時に置換する。
Jev / Laya はプロンプト文字列を受け取らないため、同じ instructions と label description を
`choice` 質問（instructions / criteria）として渡す。

---

You are a log classifier for an e-commerce system.
{instructions}

{labels}

Answer with the label name only.

Log:
{log}
