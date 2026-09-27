#!/usr/bin/env bash
# configs/ 以下の全設定でベンチマークを実行する。
# 失敗した config があっても残りは続行し、最後に失敗一覧を出して非 0 で終了する。
set -u
cd "$(dirname "$0")/.."
failed=()
for cfg in configs/*.toml; do
  echo "== ${cfg}"
  uv run hellow-jev --config "${cfg}" || failed+=("${cfg}")
done
if ((${#failed[@]})); then
  echo "failed: ${failed[*]}" >&2
  exit 1
fi
