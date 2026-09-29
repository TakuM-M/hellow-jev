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


def test_unreadable_prediction_is_wrong():
    m = evaluate(["a", "b"], ["a", None], ["a", "b"])
    assert m["accuracy"] == 0.5
    assert "invalid_rate" not in m
    assert m["confusion"]["b"] == {"<invalid>": 1}


def test_percentile_and_latency_stats():
    from hellow_jev.metrics import latency_stats, percentile

    assert percentile([], 50) == 0.0
    assert percentile([10.0], 95) == 10.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    s = latency_stats([float(i) for i in range(1, 101)])
    assert abs(s["p50_ms"] - 50.5) < 1e-9
    assert abs(s["p95_ms"] - 95.05) < 1e-9
    assert s["min_ms"] == 1.0 and s["max_ms"] == 100.0


def test_usage_stats():
    from hellow_jev.metrics import usage_stats

    s = usage_stats([{"input_tokens": 10, "output_tokens": 0}, {"input_tokens": 30}, {}])
    assert s["total"] == {"input_tokens": 40, "output_tokens": 0}
    assert abs(s["per_record"]["input_tokens"] - 40 / 3) < 1e-9


def test_errors_are_counted_separately():
    m = evaluate(["a", "b", "b"], ["a", None, None], ["a", "b"], errors=[False, True, False])
    assert abs(m["accuracy"] - 1 / 3) < 1e-9
    assert abs(m["error_rate"] - 1 / 3) < 1e-9
    assert m["confusion"]["b"] == {"<error>": 1, "<invalid>": 1}
