from hellow_jev.classifiers.base import Classifier, Prediction
from hellow_jev.task import load_dataset, load_task


def test_task_and_dataset_load():
    task = load_task("log_classification")
    assert load_dataset(task.dataset, task.label_names)


def test_prompt_renders():
    task = load_task("log_classification")
    prompt = task.render_prompt("ERROR something {braces}")
    assert "ERROR something {braces}" in prompt
    assert "- payment:" in prompt


def test_normalize_rejects_unknown_label():
    class Dummy(Classifier):
        def classify(self, text: str) -> Prediction:
            return Prediction(label=self.normalize(text))

    clf = Dummy(load_task("log_classification"))
    assert clf.classify(" `Payment`. ").label == "payment"
    assert clf.classify("normality").label is None
    assert clf.classify("I think it's payment").label is None


def test_dataset_validation(tmp_path):
    import pytest

    names = load_task("log_classification").label_names
    ok = '{"id": "a", "text": "x", "label": "payment"}\n'
    cases = {
        '{"id": "a", "text": "x", "label": "Payment"}\n': "unknown label 'Payment'",
        ok + ok: "duplicate id 'a'",
        ok + "{broken\n": ":2: invalid record",
        '{"id": "a", "text": "x", "label": "payment", "extra": 1}\n': "invalid record",
    }
    for content, message in cases.items():
        path = tmp_path / "d.jsonl"
        path.write_text(content)
        with pytest.raises(ValueError, match=message):
            load_dataset(path, names)
