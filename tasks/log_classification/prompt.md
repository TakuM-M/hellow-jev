# ログ分類プロンプト（共通テンプレート）

jev / laya / llm で同一のプロンプトを使い、条件を揃える。
`{labels}` と `{log}` は実行時に置換する。

---

You are a log classifier for an e-commerce system.
Classify the following log line into exactly one of these labels:

{labels}

Answer with the label name only.

Log:
{log}
