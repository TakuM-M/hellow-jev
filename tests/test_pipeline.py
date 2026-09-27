from hellow_jev.classifiers import build_classifier
from hellow_jev.task import REPO_ROOT, load_dataset, load_task


def test_baseline_runs_on_sample():
    task = load_task(REPO_ROOT / "tasks/log_classification")
    data = load_dataset(REPO_ROOT / "data/samples/ec_logs_sample.jsonl")
    clf = build_classifier({"type": "baseline"}, task)
    preds = [clf.classify(r.text).label for r in data]
    assert all(p in task.label_names for p in preds)


def test_prompt_renders():
    task = load_task(REPO_ROOT / "tasks/log_classification")
    prompt = task.render_prompt("ERROR something")
    assert "ERROR something" in prompt
    assert "- payment:" in prompt
