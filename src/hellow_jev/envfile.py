"""リポジトリ直下の .env を環境変数に読み込む（依存を増やさないため標準ライブラリで最小実装）。

README の手順（cp .env.example .env）どおりにキーを書けば `uv run hellow-jev` で読まれるようにする。
既に設定済みの環境変数を優先し、値が空の行は無視する（.env.example の空行で既定値を潰さない）。
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> list[str]:
    """KEY=VALUE 形式を読み込み、新たに設定したキー名を返す。ファイルが無ければ何もしない。"""
    if not path.is_file():
        return []
    loaded = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            raise ValueError(f"{path}:{lineno}: KEY=VALUE 形式ではありません")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
