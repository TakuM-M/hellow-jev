from hellow_jev.classifiers import build_classifier
from hellow_jev.classifiers.base import Classifier, Prediction
from hellow_jev.task import load_dataset, load_task


def test_baseline_runs_on_sample():
    task = load_task("log_classification")
    data = load_dataset(task.dataset)
    clf = build_classifier({"type": "baseline"}, task)
    preds = [clf.classify(r.text).label for r in data]
    assert all(p in task.label_names for p in preds)


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
