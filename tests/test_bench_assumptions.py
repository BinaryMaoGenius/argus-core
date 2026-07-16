import bench


def test_bench_constants_exist():
    assert hasattr(bench, "NUM_PREDICT_TRIAGE")
    assert hasattr(bench, "NUM_PREDICT_NORMAL")
    assert isinstance(bench.NUM_PREDICT_TRIAGE, int)
    assert bench.NUM_PREDICT_TRIAGE > 0
