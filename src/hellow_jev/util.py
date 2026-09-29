"""複数モジュールで使う小さな共通処理（ハッシュ・書き込み・Markdown 表）。"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

# HTTP リクエストの User-Agent（分類器の API 呼び出しとデータのダウンロードで共通）
USER_AGENT = "hellow-jev"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_atomic(path: Path, data: bytes) -> None:
    # 途中で止まっても壊れたファイルが残らないよう、書き終えてから置き換える
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown の表を行のリストで返す。"""
    return [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
        *("| " + " | ".join(cells) + " |" for cells in rows),
    ]
