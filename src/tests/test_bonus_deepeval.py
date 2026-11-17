"""Bonus: DeepEval port agrees with the pydantic-evals graders. Skipped when deepeval is not installed
(the eval-gate CI does not install it). Run: pip install -r bonus_lab9/requirements-bonus.txt
then python -m pytest -q -m student -o addopts= -k bonus_deepeval"""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def _restore_shapes():
    from lab8.shapes import SHAPES

    before = dict(SHAPES)
    yield
    SHAPES.clear()
    SHAPES.update(before)


def test_bonus_deepeval_agrees_where_metrics_fire():
    pytest.importorskip("deepeval")
    from bonus_lab9 import deepeval_port
    from lab9 import probe, variants
    from lab9.eval import load_spec

    variants.register()
    probe.register()
    spec = load_spec()
    for shape in ("seeded_regression", "probe_sibling_refund"):
        res = deepeval_port.compare(shape, spec)
        for mid, m in res["metrics"].items():
            assert m["agreement"] == 1.0, (shape, mid, m["disagreements"][:5])
    # the comparison is not vacuous: approval_bypass really fires on the sibling-refund probe
    assert res["metrics"]["approval_bypass"]["deepeval"] == 20
