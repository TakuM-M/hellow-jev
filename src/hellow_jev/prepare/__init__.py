"""ベンチマーク用のデータを作る CLI（標準ライブラリのみ）。

    uv run hellow-jev-prepare jevbench                        # SST-2 / AG News / Banking77 を 500 件ずつ
    uv run hellow-jev-prepare jevbench --datasets banking77 --n 200 --seed 0

詳細（jevbench の抽出手順・元ファイル）は jevbench.py。汎用の取得・検証・抽出は core.py。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hellow_jev.prepare.core import DEFAULT_OUT_DIR, PrepareError, prepare, summarize
from hellow_jev.prepare.jevbench import DEFAULT_RAW_DIR, JEVBENCH


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("1 以上を指定してください")
    return n


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hellow-jev-prepare", description="ベンチマーク用のデータを作る")
    # データセット群ごとにサブコマンドを足す
    groups = parser.add_subparsers(dest="group", required=True)
    jb = groups.add_parser("jevbench", help="jevbench と同じ SST-2 / AG News / Banking77 のサンプル")
    jb.add_argument("--datasets", nargs="+", choices=list(JEVBENCH), default=list(JEVBENCH))
    jb.add_argument("--n", type=_positive_int, default=500, help="データセットごとの件数（既定 500）")
    jb.add_argument("--seed", type=int, default=0, help="抽出の seed（既定 0）")
    jb.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="元データの保存先（手動で置く場合もここ）")
    jb.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    jb.set_defaults(func=_jevbench)
    args = parser.parse_args(argv)
    args.func(args)


def _jevbench(args: argparse.Namespace) -> None:
    # 1 つ失敗しても残りは作る（例: SST-2 だけ取得元に届かない環境）
    failed = []
    for name in dict.fromkeys(args.datasets):
        try:
            p = prepare(JEVBENCH[name], args.n, args.seed, args.raw_dir, args.out_dir)
        except PrepareError as e:
            print(e, file=sys.stderr)
            failed.append(name)
            continue
        print(summarize(p, args.n, args.seed))
    if failed:
        raise SystemExit(f"失敗: {', '.join(failed)}（理由は上のメッセージを参照）")


if __name__ == "__main__":
    main()
