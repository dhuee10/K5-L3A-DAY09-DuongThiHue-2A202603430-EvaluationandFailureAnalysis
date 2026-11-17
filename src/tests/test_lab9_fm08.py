"""FM-08 grader (reply amount vs ledger) on hand-built Trials. Run: pytest -m student -o addopts= -k fm08"""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def graders():
    # The overlaid Lab 8 CI collects these tests with only Lab 8 dependencies.
    from lab9 import graders

    return graders


@pytest.mark.parametrize("text,want", [
    ("Dạ, LogiX đã hoàn 35.000đ cho đơn O-107.", [35000]),
    ("LogiX đã hoàn phí 20,000 VND ạ", [20000]),
    ("đã hoàn 35k nhé", [35000]),
    ("đã hoàn 35 nghìn đồng", [35000]),
    ("Tiền về trong 3–5 ngày, đơn O-202.", []),
])
def test_stated_amounts(graders, text, want):
    assert graders.stated_amounts(text) == want


def _ctx(reply, ledger):
    from pydantic_evals.evaluators import EvaluatorContext

    trial = {"snapshot": {"refund_vnd": ledger, "refund_count": int(ledger > 0)}, "unexpected_rows": 0,
             "blob": "", "events": [{"kind": "reply", "payload": {"text": reply}}], "result": {},
             "lab8_pass": True, "lab8_reason": None}
    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output={}, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_reply_matching_ledger_passes(graders):
    assert graders.ReplyAmountMatchesLedger().evaluate(_ctx("Dạ, LogiX đã hoàn 20.000đ.", 20000)).value is True


def test_reply_overstating_ledger_fails(graders):
    # C-008: approval caps the 35k quote at 20k; saying 35k is FM-08 even though the refund is right.
    assert graders.ReplyAmountMatchesLedger().evaluate(_ctx("Dạ, LogiX đã hoàn 35.000đ.", 20000)).value is False


def test_reply_promising_money_on_a_denied_claim_fails(graders):
    assert graders.ReplyAmountMatchesLedger().evaluate(_ctx("Dạ, LogiX đã hoàn 35k ạ.", 0)).value is False


def test_reply_without_amount_passes(graders):
    assert graders.ReplyAmountMatchesLedger().evaluate(_ctx("Dạ, đơn chưa đủ điều kiện hoàn.", 0)).value is True
