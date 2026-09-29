from hellow_jev.task import load_dataset, load_task


def test_task_and_dataset_load():
    task = load_task("log_classification")
    assert load_dataset(task.dataset, task.label_names)


def test_prompt_renders():
    # system に指示文とラベル一覧、user にログだけ
    task = load_task("log_classification")
    system = task.render_system()
    assert task.instructions in system
    assert "- payment:" in system
    assert not any(p in system for p in ("{instructions}", "{labels}", "{log}"))
    assert task.render_prompt("ERROR something {braces}") == "ERROR something {braces}"


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


def test_unknown_classifier_option_is_rejected():
    import pytest

    from hellow_jev.classifiers import build_classifier

    task = load_task("log_classification")
    with pytest.raises(ValueError, match="temprature"):
        build_classifier({"type": "llm", "backend": "local", "model": "m", "temprature": 1.0}, task)
    with pytest.raises(ValueError, match="timeout_sec"):
        build_classifier({"type": "laya", "model": "english", "timeout_sec": 1}, task)


def test_wrong_endpoint_key_is_rejected():
    import pytest

    from hellow_jev.classifiers import build_classifier

    task = load_task("log_classification")
    with pytest.raises(ValueError, match="endpoint"):
        build_classifier({"type": "laya", "base_url": "http://x"}, task)
    with pytest.raises(ValueError, match="endpoint"):
        build_classifier({"type": "llm", "backend": "local", "model": "m",
                          "base_url": "http://x"}, task)


def _write_task(tmp_path, monkeypatch, template, extra=""):
    import hellow_jev.task as task_module

    task_dir = tmp_path / "t"
    task_dir.mkdir(exist_ok=True)
    (task_dir / "task.toml").write_text(
        f'dataset = "d.jsonl"\ninstructions = "i"\n{extra}'
        '[[labels]]\nname = "a"\ndescription = "A"\n'
    )
    (task_dir / "prompt.md").write_text("notes\n---\n" + template)
    monkeypatch.setattr(task_module, "TASKS_DIR", tmp_path)


def test_prompt_split_into_system_and_user(tmp_path, monkeypatch):
    _write_task(tmp_path, monkeypatch, "[system]\n{instructions}\n{labels}\n\n[user]\nText: {log}\n")
    task = load_task("t")
    assert task.render_system() == "i\n- a: A"
    assert task.render_prompt("x") == "Text: x"


def test_prompt_without_headers_is_user_only(tmp_path, monkeypatch):
    _write_task(tmp_path, monkeypatch, "{instructions}\nText: {log}\n")
    task = load_task("t")
    assert task.render_system() is None
    assert task.render_prompt("x") == "i\nText: x"


def test_prompt_split_errors(tmp_path, monkeypatch):
    import pytest

    for template in ("[user]\n{log}\n", "[system]\nsys\n", "x\n[system]\ns\n[user]\n{log}\n",
                     "[system]\n\n[user]\n{log}\n", "[system]\ns\n[user]\n{log}\n[user]\n"):
        _write_task(tmp_path, monkeypatch, template)
        with pytest.raises(ValueError, match="prompt.md"):
            load_task("t")

