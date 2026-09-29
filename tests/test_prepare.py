"""hellow-jev-prepare（jevbench と同じサンプルの作成）。ネットワークは使わない。"""

import dataclasses
import hashlib
import io
import json
import random
import urllib.error
import zipfile

import pytest

from hellow_jev import prepare as P
from hellow_jev.prepare import core as C
from hellow_jev.prepare import jevbench as J
from hellow_jev.task import Record, load_dataset


def _no_fetch(url):
    raise AssertionError(f"ダウンロードしないはず: {url}")


def _blocked(url):
    raise urllib.error.URLError("blocked")


# ---- 全件と同じ行数・ラベル別件数の合成データ ----


def _agnews_csv(rows=None) -> bytes:
    if rows is None:
        rows = [(i % 4 + 1, f"Title {i}", f"Body {i}") for i in range(7600)]
    return "".join(f'"{label}","{title}","{body}"\n' for label, title, body in rows).encode("utf-8")


def _banking77_csv() -> bytes:
    lines = ["text,category"] + [
        f"Question {i} about {raw}?,{raw}" for i, raw in enumerate(J.BANKING77_RAW * 40)
    ]
    return "".join(line + "\r\n" for line in lines).encode("utf-8")


def _sst2_tsv() -> bytes:
    lines = ["sentence\tlabel"] + [f"sentence {i} . \t{0 if i < 428 else 1}" for i in range(872)]
    return "".join(line + "\n" for line in lines).encode("utf-8")


def _raw_dir(tmp_path, relpath, data):
    raw = tmp_path / "raw"
    (raw / relpath).parent.mkdir(parents=True, exist_ok=True)
    (raw / relpath).write_bytes(data)
    return raw


# ---- 元ファイルの読み込み（HF の loading script と同じ結果になること） ----


def test_parse_agnews_like_hf_script():
    data = (
        # 実データの先頭 2 行（HF の test[0] / test[1] と同じ text になる。空白の連続やバックスラッシュもそのまま）
        '"3","Fears for T N pension after talks","Unions representing workers at Turner   Newall say they are '
        "'disappointed' after talks with stricken parent firm Federal Mogul.\"\n"
        '"4","The Race is On (SPACE.com)","SPACE.com - TORONTO, Canada -- A second\\team of rocketeers"\n'
        '"1", "Skip initial space", "and ""quoted"", with comma"\n'
        '"2","Amélie","wins"\n'
    ).encode("utf-8")
    assert J.parse_agnews(data) == [
        ("Fears for T N pension after talks Unions representing workers at Turner   Newall say they are "
         "'disappointed' after talks with stricken parent firm Federal Mogul.", "business"),
        ("The Race is On (SPACE.com) SPACE.com - TORONTO, Canada -- A second\\team of rocketeers", "sci_tech"),
        ('Skip initial space and "quoted", with comma', "world"),
        ("Amélie wins", "sports"),
    ]
    with pytest.raises(C.PrepareError, match="想定外のラベル '5'"):
        J.parse_agnews(b'"5","t","d"\n')
    with pytest.raises(C.PrepareError, match="3 列"):
        J.parse_agnews(b'"1","t"\n')


def test_parse_banking77_like_hf_script():
    data = (
        "text,category\r\n"
        "How do I locate my card?,card_arrival\r\n"
        # 実データには先頭に改行を含む引用付きの行がある（HF と同じくそのまま残す）
        '"\nWhere can I get my PIN unblocked?",pin_blocked\r\n'
        "Where is my refund?,Refund_not_showing_up\r\n"
        "Why was my payment reverted?,reverted_card_payment?\r\n"
        "Is 1£ extra normal?,extra_charge_on_statement\r\n"
    ).encode("utf-8")
    assert J.parse_banking77(data) == [
        ("How do I locate my card?", "card_arrival"),
        ("\nWhere can I get my PIN unblocked?", "pin_blocked"),
        ("Where is my refund?", "refund_not_showing_up"),
        ("Why was my payment reverted?", "reverted_card_payment"),
        ("Is 1£ extra normal?", "extra_charge_on_statement"),
    ]
    with pytest.raises(C.PrepareError, match="想定外の意図名 'refund_not_showing_up'"):
        J.parse_banking77(b"text,category\r\nx,refund_not_showing_up\r\n")  # 元の表記（大文字 R）以外は拒否
    with pytest.raises(C.PrepareError, match="ヘッダ"):
        J.parse_banking77(b"x,card_arrival\r\n")


def test_parse_sst2_keeps_sentence_as_is():
    data = (
        "sentence\tlabel\n"
        "it 's a charming and often affecting journey . \t1\n"
        'unflinchingly "bleak" and desperate \t0\n'
    ).encode("utf-8")
    # 文末の空白・引用符も HF（QUOTE_NONE）と同じくそのまま
    assert J.parse_sst2(data) == [
        ("it 's a charming and often affecting journey . ", "positive"),
        ('unflinchingly "bleak" and desperate ', "negative"),
    ]
    with pytest.raises(C.PrepareError, match="ヘッダ"):
        J.parse_sst2(b"label\tsentence\n1\tx\n")
    with pytest.raises(C.PrepareError, match="3 行目"):
        J.parse_sst2(b"sentence\tlabel\nok \t1\nbad \t2\n")


def test_banking77_label_ids():
    ids = [J.banking77_label(raw) for raw in J.BANKING77_RAW]
    assert len(set(ids)) == 77
    assert J.banking77_label("Refund_not_showing_up") == "refund_not_showing_up"
    assert J.banking77_label("reverted_card_payment?") == "reverted_card_payment"
    # jevbench の条件（JEV の criteria キー・JSON enum に使える id）
    assert all(i == i.lower() and "?" not in i and " " not in i for i in ids)
    assert list(J.JEVBENCH["banking77"].expected) == ids


# ---- 全件の検証と抽出 ----


def test_validate_rejects_other_row_counts():
    spec = J.JEVBENCH["sst2"]
    C.validate(spec, [("s", "negative")] * 428 + [("s", "positive")] * 444)
    with pytest.raises(C.PrepareError, match="行数が 871（期待値 872）"):
        C.validate(spec, [("s", "negative")] * 428 + [("s", "positive")] * 443)
    with pytest.raises(C.PrepareError, match="negative 429（期待値 428）"):
        C.validate(spec, [("s", "negative")] * 429 + [("s", "positive")] * 443)
    with pytest.raises(C.PrepareError, match="想定外のラベル"):
        C.validate(spec, [("s", "negative")] * 428 + [("s", "positive")] * 443 + [("s", "neutral")])


def test_sample_equals_jevbench_shuffle():
    records = [Record(f"x-{i}", f"t{i}", "a") for i in range(872)]
    # jevbench: rng = random.Random(seed); rng.shuffle(全件); 先頭 n 件
    expected = list(records)
    random.Random(0).shuffle(expected)
    assert C.sample(records, 500, 0) == expected[:500]
    assert records == [Record(f"x-{i}", f"t{i}", "a") for i in range(872)]  # 元のリストは変えない
    # 並べ替えは件数だけで決まる（要素の型や中身によらず同じ位置が選ばれる）
    order = list(range(872))
    random.Random(0).shuffle(order)
    assert [r.id for r in C.sample(records, 500, 0)] == [f"x-{i}" for i in order[:500]]
    assert C.sample(records, 500, 1) != expected[:500]
    assert len(C.sample(records, 1000, 0)) == 872  # jevbench と同じくスライスするだけ


# ---- 取得・キャッシュ・出力 ----


def test_reuses_cached_raw_file(tmp_path):
    raw = _raw_dir(tmp_path, "ag_news_csv/test.csv", _agnews_csv())
    p = C.prepare(J.JEVBENCH["agnews"], 500, 0, raw, tmp_path / "out", fetch=_no_fetch)
    assert p.raw.url is None
    assert p.raw.sha256 == hashlib.sha256(_agnews_csv()).hexdigest()
    assert len(p.records) == 500


def test_downloads_once_then_uses_cache(tmp_path):
    data = _banking77_csv()
    calls = []

    def fetch(url):
        calls.append(url)
        return data

    spec = J.JEVBENCH["banking77"]
    p = C.prepare(spec, 20, 0, tmp_path / "raw", tmp_path / "out", fetch=fetch)
    assert calls == [J.BANKING77_URL] and p.raw.url == J.BANKING77_URL
    assert (tmp_path / "raw" / "banking_data" / "test.csv").read_bytes() == data
    again = C.prepare(spec, 20, 0, tmp_path / "raw", tmp_path / "out", fetch=_no_fetch)
    assert again.records == p.records


def test_invalid_download_is_not_saved(tmp_path):
    bad = _agnews_csv([(1, "t", "d")] * 10)
    raw = tmp_path / "raw"
    with pytest.raises(C.PrepareError) as e:
        C.prepare(J.JEVBENCH["agnews"], 5, 0, raw, tmp_path / "out", fetch=lambda url: bad)
    assert "行数が 10（期待値 7600）" in str(e.value)
    assert str(raw / "ag_news_csv" / "test.csv") in str(e.value)  # 手動で置く場所を案内する
    assert not (raw / "ag_news_csv" / "test.csv").exists()


def test_broken_cached_file_stops_with_its_path(tmp_path):
    rows = [(i % 4 + 1, f"Title {i}", f"Body {i}") for i in range(7596)]  # 末尾 4 行が欠けたファイル
    raw = _raw_dir(tmp_path, "ag_news_csv/test.csv", _agnews_csv(rows))
    with pytest.raises(C.PrepareError) as e:
        C.prepare(J.JEVBENCH["agnews"], 5, 0, raw, tmp_path / "out", fetch=_no_fetch)
    # 他の取得元で黙って代用せず、どのファイルが悪いかを示して止める
    assert str(raw / "ag_news_csv" / "test.csv") in str(e.value)
    assert "行数が 7596（期待値 7600）" in str(e.value) and "削除するか" in str(e.value)


def test_sst2_reads_dev_tsv_inside_zip(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("SST-2/train.tsv", "sentence\tlabel\nnot this one \t1\n")
        zf.writestr("SST-2/dev.tsv", _sst2_tsv())
    raw = _raw_dir(tmp_path, "SST-2.zip", buf.getvalue())
    p = C.prepare(J.JEVBENCH["sst2"], 872, 0, raw, tmp_path / "out", fetch=_no_fetch)
    assert p.raw.member_sha256 == hashlib.sha256(_sst2_tsv()).hexdigest()
    assert sorted(r.text for r in p.records) == sorted(text for text, _ in J.parse_sst2(_sst2_tsv()))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dev.tsv", _sst2_tsv())  # SST-2/ の下にない
    (raw / "SST-2.zip").write_bytes(buf.getvalue())
    with pytest.raises(C.PrepareError, match="zip 内に SST-2/dev.tsv がありません"):
        C.prepare(J.JEVBENCH["sst2"], 5, 0, raw, tmp_path / "out", fetch=_no_fetch)


def test_sst2_mirror_is_used_only_with_known_sha256(tmp_path):
    dev = _sst2_tsv()

    def fetch(url):
        if url == J.SST2_URL:
            raise urllib.error.URLError("blocked")
        return dev

    raw = tmp_path / "raw"
    spec = J.JEVBENCH["sst2"]
    # 形式・行数が正しくても、確認済みのファイルと同一でなければミラーは使わない
    with pytest.raises(C.PrepareError) as e:
        C.prepare(spec, 5, 0, raw, tmp_path / "out", fetch=fetch)
    message = str(e.value)
    assert "sha256 が確認済みのファイルと一致しない" in message
    assert str(raw / "SST-2.zip") in message and str(raw / "SST-2" / "dev.tsv") in message
    assert not (raw / "SST-2" / "dev.tsv").exists()

    zip_file, dev_file = spec.raw_files
    trusted = dataclasses.replace(
        spec, raw_files=(zip_file, dataclasses.replace(dev_file, sha256=hashlib.sha256(dev).hexdigest()))
    )
    p = C.prepare(trusted, 5, 0, raw, tmp_path / "out", fetch=fetch)
    assert p.raw.url == J.SST2_MIRRORS[0]
    assert (raw / "SST-2" / "dev.tsv").read_bytes() == dev


def test_output_jsonl_is_loadable_in_jevbench_order(tmp_path):
    order = list(range(7600))
    random.Random(0).shuffle(order)
    rows = [(i % 4 + 1, f"Title {i}", f"Body {i}") for i in range(7600)]
    first = order[0]
    rows[first] = (first % 4 + 1, "Amélie", "wins")  # ラベル別件数は変えない
    raw = _raw_dir(tmp_path, "ag_news_csv/test.csv", _agnews_csv(rows))
    p = C.prepare(J.JEVBENCH["agnews"], 500, 0, raw, tmp_path / "out", fetch=_no_fetch)

    path = tmp_path / "out" / "jevbench_agnews.jsonl"
    assert p.out_path == path
    assert p.out_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert list(json.loads(lines[0])) == ["id", "text", "label"]
    assert "Amélie wins" in text  # ensure_ascii=False
    loaded = load_dataset(path, J.AGNEWS_LABELS)
    assert [r.id for r in loaded] == [f"agnews-{i}" for i in order[:500]]
    assert loaded[0] == Record(f"agnews-{first}", "Amélie wins", J.AGNEWS_LABELS[first % 4])
    assert loaded[1].text == f"Title {order[1]} Body {order[1]}"


def test_cli_writes_outputs_and_summary(tmp_path, capsys):
    raw = _raw_dir(tmp_path, "banking_data/test.csv", _banking77_csv())
    out = tmp_path / "out"
    P.main(["jevbench", "--datasets", "banking77", "--n", "30", "--seed", "3",
            "--raw-dir", str(raw), "--out-dir", str(out)])
    summary = capsys.readouterr().out
    path = out / "jevbench_banking77.jsonl"
    assert len(load_dataset(path, list(J.JEVBENCH["banking77"].expected))) == 30
    assert hashlib.sha256(path.read_bytes()).hexdigest() in summary
    assert hashlib.sha256(_banking77_csv()).hexdigest() in summary
    assert "n=30" in summary and "seed=3" in summary


def test_cli_reports_where_to_place_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(C, "fetch_url", _blocked)
    raw = _raw_dir(tmp_path, "banking_data/test.csv", _banking77_csv())
    with pytest.raises(SystemExit, match="失敗: sst2"):
        P.main(["jevbench", "--datasets", "sst2", "banking77", "--raw-dir", str(raw),
                "--out-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert str(raw / "SST-2.zip") in captured.err
    # 取得できなかったデータセットがあっても、残りは作る
    assert (tmp_path / "out" / "jevbench_banking77.jsonl").is_file()
    assert not (tmp_path / "out" / "jevbench_sst2.jsonl").exists()
