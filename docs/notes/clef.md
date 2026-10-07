# Clef

- 利用形態: API（Workers AI）。open weight（Apache-2.0）もある
- 実装: 未実装（`systemone.SystemOneClassifier` を継承し URL とレスポンスの剥がしを上書きする見込み）
- 環境変数: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`

## 概要

- Cloudflare、2026-10-01 公開。テキスト・画像入力、64K コンテキスト
- `clef`（27B、Qwen3.8-27B ベース）/ `clef-flash`（9B）
- 重みは公開されているが専用の判定ヘッドが要り、vLLM 等では動かない

## API 仕様

`POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{clef,clef-flash}`

- ボディは Jev と同じ（`docs/notes/jev.md`）。`temperature` は 422
- レスポンスは `{"result": {"model", "answers", "usage"}, "success", "errors", "messages"}` に包まれる

## 料金

- input $0.24（Clef）/ $0.09（Clef-flash）/ 1M tokens、output は無課金

## 公表値の注意

- 「Jev より 13 倍速い」は Jev p50 524 ms との比較。本リポジトリの Jev 実測は 162〜175 ms

公式ページは egress 制限で未読。上記は検索結果の抜粋と GitHub の実装 PR によるもので、実装前に実 API で確認する（2026-10-07）。
