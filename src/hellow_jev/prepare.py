"""ベンチマーク用のデータを作る CLI（標準ライブラリのみ）。

    uv run hellow-jev-prepare jevbench                        # SST-2 / AG News / Banking77 を 500 件ずつ
    uv run hellow-jev-prepare jevbench --datasets banking77 --n 200 --seed 0

## jevbench

公開ベンチマーク jevbench（https://github.com/dhruvmehra/jevbench 、MIT、commit c983cc4）の
`src/jevbench/datasets.py` と同じサンプルを、Hugging Face（HF）を使わずに作る。jevbench の抽出手順:

1. HF の評価 split を行順のまま全件読む（SST-2 = stanfordnlp/sst2 の validation 872 行、
   AG News = fancyzhx/ag_news の test 7600 行、Banking77 = legacy-datasets/banking77 の test 3080 行）
2. `rng = random.Random(seed)` で全件を `rng.shuffle`（rng の最初の使用）し、先頭 n 件を使う（n=500, seed=0）

並べ替えは件数だけで決まるので、全件の行数と行順が HF と同じならサンプルも同じになる。
逆に行数が 1 行でも違うと別のサンプルになるため、全件の行数とラベル別件数を検証し、合わなければ止める。

HF のデータは各データセットの loading script が元ファイルを読んで作ったもの。ここでは同じ元ファイルを
同じ手順で読む（huggingface/datasets の GitHub タグ 2.0.0 / 2.3.0 にある datasets/<name>/*.py と同じ処理）:

- AG News: CharCnn_Keras の ag_news_csv/test.csv。ヘッダなしの `label, title, description`。
  text = title + " " + description（バックスラッシュ等はそのまま）。label 1〜4 → world / sports / business / sci_tech
- Banking77: PolyAI の banking_data/test.csv。先頭のヘッダを飛ばして `text, category`。
  ラベルは jevbench と同じく意図名を lower() して "?" を除く（Refund_not_showing_up → refund_not_showing_up）
- SST-2: GLUE の SST-2.zip 内の SST-2/dev.tsv。`sentence<TAB>label`（QUOTE_NONE）。文末の空白も含めてそのまま。
  label 0 → negative、1 → positive

どれも HF の script と同じく `open(path, encoding="utf-8")` 相当（universal newlines）で読む。

元ファイルは data/raw/jevbench/ に保存し、次回からはダウンロードせずに使う。URL に届かない環境では
同じ場所に手動で置けばよい（置き場所は失敗時のメッセージに出る）。
出力は data/processed/jevbench_<name>.jsonl（jevbench の抽出順。id は `<name>-<全件での行番号>`）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import io
import json
import os
import random
import sys
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hellow_jev.task import REPO_ROOT, Record

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "jevbench"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "processed"
DOWNLOAD_TIMEOUT_SEC = 60

Rows = list[tuple[str, str]]  # (text, label)。HF と同じ行順


class PrepareError(Exception):
    """元データの取得・検証の失敗。メッセージはそのまま利用者に見せる。"""


# ---- ラベル（jevbench の DATASETS と同じ id） ----

SST2_LABELS = ["negative", "positive"]  # HF の label 0, 1
AGNEWS_LABELS = ["world", "sports", "business", "sci_tech"]  # HF の label 0〜3（CSV では 1〜4）
# Banking77 の意図名。HF の ClassLabel の順で、jevbench の BANKING77_RAW と同じ
BANKING77_RAW = [
    "activate_my_card", "age_limit", "apple_pay_or_google_pay", "atm_support",
    "automatic_top_up", "balance_not_updated_after_bank_transfer",
    "balance_not_updated_after_cheque_or_cash_deposit", "beneficiary_not_allowed",
    "cancel_transfer", "card_about_to_expire", "card_acceptance", "card_arrival",
    "card_delivery_estimate", "card_linking", "card_not_working",
    "card_payment_fee_charged", "card_payment_not_recognised",
    "card_payment_wrong_exchange_rate", "card_swallowed", "cash_withdrawal_charge",
    "cash_withdrawal_not_recognised", "change_pin", "compromised_card",
    "contactless_not_working", "country_support", "declined_card_payment",
    "declined_cash_withdrawal", "declined_transfer",
    "direct_debit_payment_not_recognised", "disposable_card_limits",
    "edit_personal_details", "exchange_charge", "exchange_rate", "exchange_via_app",
    "extra_charge_on_statement", "failed_transfer", "fiat_currency_support",
    "get_disposable_virtual_card", "get_physical_card", "getting_spare_card",
    "getting_virtual_card", "lost_or_stolen_card", "lost_or_stolen_phone",
    "order_physical_card", "passcode_forgotten", "pending_card_payment",
    "pending_cash_withdrawal", "pending_top_up", "pending_transfer", "pin_blocked",
    "receiving_money", "Refund_not_showing_up", "request_refund",
    "reverted_card_payment?", "supported_cards_and_currencies", "terminate_account",
    "top_up_by_bank_transfer_charge", "top_up_by_card_charge",
    "top_up_by_cash_or_cheque", "top_up_failed", "top_up_limits", "top_up_reverted",
    "topping_up_by_card", "transaction_charged_twice", "transfer_fee_charged",
    "transfer_into_account", "transfer_not_received_by_recipient", "transfer_timing",
    "unable_to_verify_identity", "verify_my_identity", "verify_source_of_funds",
    "verify_top_up", "virtual_card_not_working", "visa_or_mastercard",
    "why_verify_identity", "wrong_amount_of_cash_received",
    "wrong_exchange_rate_for_cash_withdrawal",
]
_BANKING77_RAW_SET = frozenset(BANKING77_RAW)


def banking77_label(raw: str) -> str:
    """jevbench の `_bank_id` と同じ変換（reverted_card_payment? → reverted_card_payment など）。"""
    return raw.lower().replace("?", "")


# ---- 元ファイルの読み込み（HF の loading script と同じ処理） ----


def _text(data: bytes) -> io.TextIOWrapper:
    # HF の script の open(path, encoding="utf-8") と同じく universal newlines で読む（CRLF → LF）
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")


def _hf_csv(data: bytes):
    # HF の ag_news.py / banking77.py と同じ設定
    return csv.reader(
        _text(data), quotechar='"', delimiter=",", quoting=csv.QUOTE_ALL, skipinitialspace=True
    )


def parse_agnews(data: bytes) -> Rows:
    rows = []
    reader = _hf_csv(data)
    for row in reader:
        if len(row) != 3:
            raise PrepareError(f"{reader.line_num} 行目: label,title,description の 3 列ではありません")
        label, title, description = row
        if label not in ("1", "2", "3", "4"):
            raise PrepareError(f"{reader.line_num} 行目: 想定外のラベル {label!r}")
        rows.append((" ".join((title, description)), AGNEWS_LABELS[int(label) - 1]))
    return rows


def parse_banking77(data: bytes) -> Rows:
    reader = _hf_csv(data)
    header = next(reader, None)
    if header != ["text", "category"]:
        raise PrepareError(f"先頭行がヘッダ text,category ではありません: {header!r}")
    rows = []
    for row in reader:
        if len(row) != 2:
            raise PrepareError(f"{reader.line_num} 行目: text,category の 2 列ではありません")
        text, raw = row
        if raw not in _BANKING77_RAW_SET:
            raise PrepareError(f"{reader.line_num} 行目: 想定外の意図名 {raw!r}")
        rows.append((text, banking77_label(raw)))
    return rows


def parse_sst2(data: bytes) -> Rows:
    # HF の sst2.py と同じ DictReader(delimiter="\t", quoting=QUOTE_NONE)。引用符も文末の空白もそのまま残す
    reader = csv.DictReader(_text(data), delimiter="\t", quoting=csv.QUOTE_NONE)
    if reader.fieldnames != ["sentence", "label"]:
        raise PrepareError(f"ヘッダが sentence<TAB>label ではありません: {reader.fieldnames!r}")
    rows = []
    for row in reader:
        if None in row or row["label"] not in ("0", "1"):
            raise PrepareError(f"{reader.line_num} 行目: sentence<TAB>label（0 / 1）の形式ではありません")
        rows.append((row["sentence"], SST2_LABELS[int(row["label"])]))
    return rows


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
    name: str  # jevbench のデータセット名。id の接頭辞と出力ファイル名に使う
    hf: str  # jevbench が読む HF のデータセットと split（表示用）
    raw_files: tuple[RawFile, ...]  # 上から順に「置いてあるか」を見て、無ければ上から順にダウンロードを試す
    parse: Callable[[bytes], Rows]
    expected: dict[str, int]  # 全件のラベル別件数。行数が違うとサンプルが別物になるので厳密に照合する


AGNEWS_URL = "https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/master/data/ag_news_csv/test.csv"
BANKING77_URL = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv"
SST2_URL = "https://dl.fbaipublicfiles.com/glue/data/SST-2.zip"
# GLUE の SST-2/dev.tsv を含む GitHub リポジトリ（コミット固定）。独立した 16 リポジトリで同一内容だったファイルで、
# 行数・ラベル別件数・HF sst2 の dataset_infos.json（validation の num_bytes 106361）とも整合する
SST2_MIRRORS = (
    "https://raw.githubusercontent.com/tatsu-lab/mlm_inductive_bias/"
    "2d99e2477293036949ba356c88513729244dc1f9/finetuning/data/SST-2/dev.tsv",
    "https://raw.githubusercontent.com/DAMO-NLP-SG/PMR/"
    "c62949339cc2a32bd336f006c80bcc84b0924e04/GLUE/Data/SST-2/dev.tsv",
)
SST2_DEV_SHA256 = "54a9c12c77e402fc14d6a66a506f24d999f596b0176eb777c972cccc2f9cc4b0"

# 配布元ファイルの sha256 は HF の dataset_infos.json（download_checksums）に記録された値
JEVBENCH: dict[str, DatasetSpec] = {
    "sst2": DatasetSpec(
        name="sst2",
        hf="stanfordnlp/sst2 validation",
        raw_files=(
            RawFile(
                "SST-2.zip",
                how_to_get=f"{SST2_URL} をそのまま保存",
                urls=(SST2_URL,),
                sha256="d67e16fb55739c1b32cdce9877596db1c127dc322d93c082281f64057c16deaa",
                member="SST-2/dev.tsv",
                member_sha256=SST2_DEV_SHA256,
            ),
            RawFile(
                "SST-2/dev.tsv",
                how_to_get="SST-2.zip を展開した中の SST-2/dev.tsv",
                mirrors=SST2_MIRRORS,
                sha256=SST2_DEV_SHA256,
            ),
        ),
        parse=parse_sst2,
        expected={"negative": 428, "positive": 444},
    ),
    "agnews": DatasetSpec(
        name="agnews",
        hf="fancyzhx/ag_news test",
        raw_files=(
            RawFile(
                "ag_news_csv/test.csv",
                how_to_get=f"{AGNEWS_URL} をそのまま保存",
                urls=(AGNEWS_URL,),
                sha256="521465c2428ed7f02f8d6db6ffdd4b5447c1c701962353eb2c40d548c3c85699",
            ),
        ),
        parse=parse_agnews,
        expected={label: 1900 for label in AGNEWS_LABELS},
    ),
    "banking77": DatasetSpec(
        name="banking77",
        hf="legacy-datasets/banking77 test",
        raw_files=(
            RawFile(
                "banking_data/test.csv",
                how_to_get=f"{BANKING77_URL} をそのまま保存",
                urls=(BANKING77_URL,),
                sha256="d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d",
            ),
        ),
        parse=parse_banking77,
        expected={banking77_label(raw): 40 for raw in BANKING77_RAW},
    ),
}


# ---- 取得・検証・抽出 ----


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hellow-jev"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SEC) as resp:
        return resp.read()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    # 途中で止まっても壊れたファイルがキャッシュとして残らないよう、書き終えてから置き換える
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def validate(spec: DatasetSpec, rows: Rows) -> None:
    """全件の行数とラベル別件数が HF の split と一致するか確かめる。"""
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
        member_sha256 = _sha256(data)
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
            return RawData(rows, raw_file, path, _sha256(data), member_sha256, url=None)

    failures = []
    for raw_file in spec.raw_files:
        candidates = [(url, False) for url in raw_file.urls] + [(url, True) for url in raw_file.mirrors]
        for url, is_mirror in candidates:
            print(f"[{spec.name}] ダウンロード: {url}", file=sys.stderr)
            try:
                data = fetch(url)
                sha256 = _sha256(data)
                if is_mirror and sha256 != raw_file.sha256:
                    raise PrepareError(f"sha256 が確認済みのファイルと一致しないため使いません（{sha256}）")
                rows, member_sha256 = _read(spec, raw_file, data)
            except (OSError, http.client.HTTPException, PrepareError) as e:
                failures.append(f"  - {url}: {e}")
                print(f"[{spec.name}]   失敗: {e}", file=sys.stderr)
                continue
            path = raw_dir / raw_file.path
            _write_atomic(path, data)  # 検証を通ったものだけ保存する
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    # OS によらず同じバイト列（= 同じ sha256）になるよう改行は LF に固定する
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps({"id": r.id, "text": r.text, "label": r.label}, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


@dataclass
class Prepared:
    spec: DatasetSpec
    raw: RawData
    out_path: Path
    out_sha256: str
    records: list[Record]  # 出力したサンプル（jevbench の抽出順）


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
    out_path = out_dir / f"jevbench_{spec.name}.jsonl"
    write_jsonl(out_path, picked)
    return Prepared(spec, raw, out_path, _sha256(out_path.read_bytes()), picked)


# ---- 表示・CLI ----


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
