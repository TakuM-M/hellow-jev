#!/usr/bin/env bash
# jevbench の全タスク × 指定した config でベンチマークを実行する（同じ config をタスクだけ替えて回す）。
#   ./scripts/run_jevbench.sh                                  # configs/*.toml × 全タスク
#   ./scripts/run_jevbench.sh configs/jev.toml configs/laya.toml
#   TASKS="jevbench_banking77" ./scripts/run_jevbench.sh configs/jev.toml   # タスクを絞る（空白かカンマ区切り）
# 失敗した組み合わせがあっても残りは続行し、最後に失敗一覧を出して非 0 で終了する。
set -u
cd "$(dirname "$0")/.."

all_tasks=(jevbench_sst2 jevbench_agnews jevbench_agnews_v2 jevbench_banking77)
selected=${TASKS:-${all_tasks[*]}}
read -r -a tasks <<< "${selected//,/ }"
if (($#)); then configs=("$@"); else configs=(configs/*.toml); fi

# タスクごとの評価データ（hellow-jev-prepare で作る。agnews と agnews_v2 は同じデータ）
dataset() {
  case "$1" in
    jevbench_sst2 | jevbench_banking77) echo "data/processed/$1.jsonl" ;;
    jevbench_agnews | jevbench_agnews_v2) echo "data/processed/jevbench_agnews.jsonl" ;;
    *) return 1 ;;
  esac
}

# 何件か回した後で止まらないよう、入力がそろっているかを先に確認する
missing=()
for task in "${tasks[@]}"; do
  if ! data=$(dataset "${task}"); then
    echo "unknown task: ${task}（${all_tasks[*]} から選ぶ）" >&2
    exit 1
  fi
  [[ -f "${data}" ]] || missing+=("${data}")
done
if ((${#missing[@]})); then
  echo "データがありません:" >&2
  printf '  %s\n' "${missing[@]}" | sort -u >&2
  echo "先に uv run hellow-jev-prepare jevbench を実行してください" >&2
  exit 1
fi
for cfg in "${configs[@]}"; do
  [[ -f "${cfg}" ]] || { echo "config がありません: ${cfg}" >&2; exit 1; }
done

failed=()
for cfg in "${configs[@]}"; do
  for task in "${tasks[@]}"; do
    echo "== ${cfg} ${task}"
    uv run hellow-jev --config "${cfg}" --task "${task}" || failed+=("${cfg} ${task}")
  done
done
if ((${#failed[@]})); then
  echo "failed (config task):" >&2
  printf '  %s\n' "${failed[@]}" >&2
fi
echo "比較表: uv run hellow-jev-report --out docs/report.md"
exit $((${#failed[@]} > 0))
