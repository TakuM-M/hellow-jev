from hellow_jev.metrics import evaluate


def test_perfect():
    m = evaluate(["a", "b"], ["a", "b"], ["a", "b"])
    assert m["accuracy"] == 1.0
    assert m["macro_f1"] == 1.0


def test_partial():
    m = evaluate(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert abs(m["accuracy"] - 2 / 3) < 1e-9
    assert m["per_class"]["a"]["recall"] == 0.5
    assert m["per_class"]["b"]["precision"] == 0.5
