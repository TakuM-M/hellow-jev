"""データ準備の汎用処理: 元ファイルの取得（置いてあれば再利用）・全件の検証・抽出・JSONL の書き出し。

データセット固有の定義（取得元・読み方・期待件数）は DatasetSpec として各モジュール（jevbench.py）に置く。
"""

from __future__ import annotations

import csv
import http.client
import io
import json
import random
import sys
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hellow_jev.task import REPO_ROOT, Record
from hellow_jev.util import USER_AGENT, sha256_bytes, sha256_file, write_atomic

DEFAULT_OUT_DIR = REPO_ROOT / "data" / "processed"
DOWNLOAD_TIMEOUT_SEC = 60

Rows = list[tuple[str, str]]  # (text, label)。元データの行順


class PrepareError(Exception):
    """元データの取得・検証の失敗。メッセージはそのまま利用者に見せる。"""


# ---- データセットの定義 ----


@dataclass(frozen=True)
class RawFile:
    """raw ディレクトリに置く元ファイル 1 つと、その取得元。"""

    path: str  # raw ディレクトリからの相対パス。手動で置く場合もこの名前にする
    how_to_get: str  # 手動で置く場合の入手方法（失敗時のメッセージ用）
    urls: tuple[str, ...] = ()  # 配布元
    # 第三者のミラー。中身を確認済みのファイルと sha256 が一致した場合だけ使う
    mirrors: tuple[str, ...] = ()
    sha256: str | None = None  # 既知の値。配布元・手動配置のファイルは不一致でも行数・ラベルが合えば使う（警告のみ）
    member: str | None = None  # zip の場合、中の読むファイル
    member_sha256: str | None = None


@dataclass(frozen=True)
class DatasetSpec:
    name: str  # データセット名。id の接頭辞に使う
    out_name: str  # 出力ファイル名（out_dir 以下）
    hf: str  # 元になる HF のデータセットと split（表示用）
    raw_files: tuple[RawFile, ...]  # 上から順に「置いてあるか」を見て、無ければ上から順にダウンロードを試す
    parse: Callable[[bytes], Rows]
    expected: dict[str, int]  # 全件のラベル別件数。行数が違うとサンプルが別物になるので厳密に照合する


# ---- 取得・検証・抽出 ----


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SEC) as resp:
        return resp.read()


def validate(spec: DatasetSpec, rows: Rows) -> None:
    """全件の行数とラベル別件数が元の split（spec.hf）と一致するか確かめる。"""
    counts = Counter(label for _, label in rows)
    total = sum(spec.expected.values())
    problems = []
    if len(rows) != total:
        problems.append(f"行数が {len(rows)}（期待値 {total}）")
    if unknown := sorted(set(counts) - set(spec.expected)):
        problems.append(f"想定外のラベル {unknown[:5]}")
    if missing := sorted(set(spec.expected) - set(counts)):
        problems.append(f"無いラベル {missing[:5]}")
    wrong = [
        f"{label} {counts[label]}（期待値 {n}）"
        for label, n in spec.expected.items()
        if label in counts and counts[label] != n
    ]
    if wrong:
        problems.append("ラベル別件数が違う: " + ", ".join(wrong[:5]) + (" ほか" if len(wrong) > 5 else ""))
    if problems:
        raise PrepareError(
            f"全件が {spec.hf} と一致しません（" + " / ".join(problems) + "）。"
            "行数が変わるとサンプルが jevbench と別物になるため中止します"
        )


def _read(spec: DatasetSpec, raw_file: RawFile, data: bytes) -> tuple[Rows, str | None]:
    """元ファイル（zip なら中の member）を読んで全件を検証する。(全件, member の sha256) を返す。"""
    member_sha256 = None
    if raw_file.member:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                data = zf.read(raw_file.member)
        except zipfile.BadZipFile as e:
            raise PrepareError(f"zip として読めません（{e}）") from e
        except KeyError:
            raise PrepareError(f"zip 内に {raw_file.member} がありません") from None
        member_sha256 = sha256_bytes(data)
    try:
        rows = spec.parse(data)
    except (UnicodeDecodeError, csv.Error) as e:
        raise PrepareError(f"読み込めません（{type(e).__name__}: {e}）") from e
    validate(spec, rows)
    return rows, member_sha256


@dataclass
class RawData:
    rows: Rows  # 全件
    raw_file: RawFile
    path: Path
    sha256: str
    member_sha256: str | None
    url: str | None  # 今回ダウンロードした URL。置いてあったファイルを使った場合は None


def load_raw(
    spec: DatasetSpec, raw_dir: Path, fetch: Callable[[str], bytes] | None = None
) -> RawData:
    """元データの全件を読む。raw_dir に置いてあればそれを使い、無ければダウンロードして保存する。"""
    fetch = fetch or fetch_url
    # 置いてあるファイル（前回の保存・手動配置）を優先する。壊れていれば他の取得元で代用せずに止める
    for raw_file in spec.raw_files:
        path = raw_dir / raw_file.path
        if path.is_file():
            data = path.read_bytes()
            try:
                rows, member_sha256 = _read(spec, raw_file, data)
            except PrepareError as e:
                raise PrepareError(
                    f"[{spec.name}] {path}: {e}\n  削除するか、正しいファイルに置き換えてから再実行してください"
                ) from e
            return RawData(rows, raw_file, path, sha256_bytes(data), member_sha256, url=None)

    failures = []
    for raw_file in spec.raw_files:
        candidates = [(url, False) for url in raw_file.urls] + [(url, True) for url in raw_file.mirrors]
        for url, is_mirror in candidates:
            print(f"[{spec.name}] ダウンロード: {url}", file=sys.stderr)
            try:
                data = fetch(url)
                sha256 = sha256_bytes(data)
                if is_mirror and sha256 != raw_file.sha256:
                    raise PrepareError(f"sha256 が確認済みのファイルと一致しないため使いません（{sha256}）")
                rows, member_sha256 = _read(spec, raw_file, data)
            except (OSError, http.client.HTTPException, PrepareError) as e:
                failures.append(f"  - {url}: {e}")
                print(f"[{spec.name}]   失敗: {e}", file=sys.stderr)
                continue
            path = raw_dir / raw_file.path
            write_atomic(path, data)  # 検証を通ったものだけ保存する。途中で止まっても壊れたキャッシュを残さない
            return RawData(rows, raw_file, path, sha256, member_sha256, url=url)

    places = "\n".join(f"  - {raw_dir / f.path}（{f.how_to_get}）" for f in spec.raw_files)
    raise PrepareError(
        f"[{spec.name}] 元データを取得できませんでした。\n" + "\n".join(failures)
        + f"\n次のどれかにファイルを置いてから再実行してください:\n{places}"
    )


def sample(records: list[Record], n: int, seed: int) -> list[Record]:
    """jevbench と同じ抽出: random.Random(seed) で全件をシャッフル（rng の最初の使用）して先頭 n 件。"""
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:n]


def write_jsonl(path: Path, records: list[Record]) -> None:
    # バイト列で書くので、OS によらず改行は LF（= 同じ sha256）になる
    lines = (json.dumps({"id": r.id, "text": r.text, "label": r.label}, ensure_ascii=False) + "\n"
             for r in records)
    write_atomic(path, "".join(lines).encode("utf-8"))


@dataclass
class Prepared:
    spec: DatasetSpec
    raw: RawData
    out_path: Path
    out_sha256: str
    records: list[Record]  # 出力したサンプル（抽出順）


def prepare(
    spec: DatasetSpec,
    n: int,
    seed: int,
    raw_dir: Path,
    out_dir: Path,
    fetch: Callable[[str], bytes] | None = None,
) -> Prepared:
    raw = load_raw(spec, raw_dir, fetch)
    # id に全件での行番号を入れ、どの元データの行か辿れるようにする
    records = [Record(id=f"{spec.name}-{i}", text=text, label=label) for i, (text, label) in enumerate(raw.rows)]
    picked = sample(records, n, seed)
    out_path = out_dir / spec.out_name
    write_jsonl(out_path, picked)
    return Prepared(spec, raw, out_path, sha256_file(out_path), picked)


# ---- 表示 ----


def _show(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _check(actual: str, known: str | None) -> str:
    if known is None:
        return ""
    if actual == known:
        return "（既知の値と一致）"
    return f"（警告: 既知の値 {known} と不一致。行数・ラベル別件数は一致）"


def _distribution(labels: list[str], spec: DatasetSpec) -> str:
    counts = Counter(labels)
    names = list(spec.expected)
    if len(names) <= 10:
        return " / ".join(f"{name} {counts[name]}" for name in names)
    per_label = [counts[name] for name in names]
    present = sum(c > 0 for c in per_label)
    return f"{len(names)} ラベル中 {present} ラベル、1 ラベルあたり {min(per_label)}〜{max(per_label)} 件"


def summarize(p: Prepared, n: int, seed: int) -> str:
    raw, spec = p.raw, p.spec
    source = raw.url or "置いてあったファイル（前回の保存または手動配置）"
    lines = [
        f"[{spec.name}] {spec.hf}",
        f"  取得元: {source}",
        f"  元データ: {_show(raw.path)}  sha256 {raw.sha256}{_check(raw.sha256, raw.raw_file.sha256)}",
    ]
    if raw.member_sha256:
        lines.append(
            f"    {raw.raw_file.member}: sha256 {raw.member_sha256}"
            f"{_check(raw.member_sha256, raw.raw_file.member_sha256)}"
        )
    lines.append(f"  全件: {len(raw.rows)} 行（{_distribution([label for _, label in raw.rows], spec)}）")
    note = f"（全件が {len(raw.rows)} 行のため全件。jevbench と同じ扱い）" if len(p.records) < n else ""
    lines += [
        f"  出力: {_show(p.out_path)}  n={len(p.records)}{note} seed={seed}  sha256 {p.out_sha256}",
        f"  サンプルのラベル分布: {_distribution([r.label for r in p.records], spec)}",
    ]
    return "\n".join(lines)
