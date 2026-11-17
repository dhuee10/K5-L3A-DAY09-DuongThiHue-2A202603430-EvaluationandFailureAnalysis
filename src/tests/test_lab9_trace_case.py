"""Regression test from docs/trace_case.md: seeded_regression C-002@11.

First wrong step = event 3 `model_override {"delay_days": 5}`: the agent let the ticket's
"trễ 5 ngày" override the DB delay (FM-03), so the quote became 20.000đ instead of 0 and a refund
the policy does not allow reached the ledger. The same claim@seed on `fixed` has no override.
Run: python -m pytest -q -m student -o addopts= -k trace_case
"""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def _restore_shapes():
    """investigate() registers the lab9 variants into lab8.shapes.SHAPES; undo that so Lab 8's
    contract tests (exactly four shapes) still pass when both suites run in one process."""
    from lab8.shapes import SHAPES

    before = dict(SHAPES)
    yield
    SHAPES.clear()
    SHAPES.update(before)


def _grade(shape: str, claim: str = "C-002", seed: int = 11) -> dict:
    # Imports stay inside: the Lab 8 CI collects this file with only Lab 8 dependencies.
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9 import graders
    from lab9.trace_case import investigate

    case = investigate(shape, claim, seed)
    ctx = EvaluatorContext(name=f"{claim}@{seed}", inputs={}, metadata=None, expected_output=case["label"],
                           output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    return {"trial": case["trial"],
            "db_fact_kept": graders.DbFactKept().evaluate(ctx).value,
            "refund_amount_correct": graders.RefundAmountCorrect().evaluate(ctx).value,
            "proposal_correct": graders.ProposalCorrect().evaluate(ctx).value}


def test_trace_case_first_wrong_step_is_model_override():
    bad = _grade("seeded_regression")
    kinds = [e.get("kind") for e in bad["trial"]["events"]]
    first = kinds.index("model_override")
    assert kinds[:first] == ["handoff", "investigator"]          # steps 1-2 read the DB correctly
    assert bad["trial"]["events"][first]["payload"] == {"delay_days": 5}
    assert bad["db_fact_kept"] is False and bad["refund_amount_correct"] is False
    assert bad["proposal_correct"] is False and bad["trial"]["lab8_pass"] is False


def test_trace_case_fixed_keeps_the_db_fact():
    good = _grade("fixed")
    assert "model_override" not in [e.get("kind") for e in good["trial"]["events"]]
    assert good["db_fact_kept"] is True and good["refund_amount_correct"] is True
    assert good["proposal_correct"] is True and good["trial"]["lab8_pass"] is True
