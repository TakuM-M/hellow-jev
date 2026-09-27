#!/usr/bin/env bash
# configs/ 以下の全設定でベンチマークを実行する（未実装のものはスキップ表示）。
set -u
cd "$(dirname "$0")/.."
for cfg in configs/*.toml; do
  echo "== ${cfg}"
  PYTHONPATH=src python3 -m hellow_jev.run --config "${cfg}" || echo "   (skip: failed)"
done
