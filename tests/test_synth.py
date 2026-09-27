import json

from hellow_jev.synth import DEFAULT_OUT, DEFAULT_PER_LABEL, DEFAULT_SEED, generate
from hellow_jev.task import load_dataset, load_task


def test_committed_synth_dataset_is_up_to_date():
    # テンプレートを変えたのに再生成し忘れると、評価データとコードが食い違う
    task = load_task("log_classification")
    expected = generate(task.label_names, DEFAULT_PER_LABEL, DEFAULT_SEED)
    lines = DEFAULT_OUT.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == expected
    assert len(load_dataset(DEFAULT_OUT, task.label_names)) == len(expected)


def test_generate_is_balanced_and_deterministic():
    labels = load_task("log_classification").label_names
    records = generate(labels, 3, seed=1)
    assert records == generate(labels, 3, seed=1)
    assert sorted(r["label"] for r in records) == sorted(labels * 3)
