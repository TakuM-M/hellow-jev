from hellow_jev.classifiers.base import Classifier, Prediction
from hellow_jev.task import load_dataset, load_task


def test_task_and_dataset_load():
    task = load_task("log_classification")
    data = load_dataset(task.dataset)
    assert data
    assert all(r.label in task.label_names for r in data)


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
