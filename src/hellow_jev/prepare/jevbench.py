"""jevbench（SST-2 / AG News / Banking77）のデータ定義。

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

import csv
import io

from hellow_jev.prepare.core import DatasetSpec, PrepareError, RawFile, Rows
from hellow_jev.task import REPO_ROOT

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "jevbench"


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
        out_name="jevbench_sst2.jsonl",
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
        out_name="jevbench_agnews.jsonl",
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
        out_name="jevbench_banking77.jsonl",
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
