# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: `seeded_regression` C-002@11

Output thật (rút gọn payload):

```
== seeded_regression C-002@11  lab8 grader: FAIL (status resolved != denied)
   1 handoff            {"allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"], ...}
   2 investigator       {"lookup_order": {"visible": true, "reason": "ok", "order": {"order_id": "O-202", "status": "delivered", ...
   3 model_override     {"delay_days": 5}
   4 quote              {"amount_vnd": 20000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"], ...}
   5 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   6 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."}
  refund_vnd     ledger=20000    label=0   <-- differs
  refund_count   ledger=1        label=0   <-- differs
  status         result=resolved label=denied
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261117-35b7` (`reports/eval_seeded_regression.json`, dòng E-002 seed 11) |
| Triệu chứng | `pass_rate` FAIL (`status resolved != denied`), `db_fact_kept` FAIL (1 override event), `refund_amount_correct` FAIL (ledger 20000 ≠ nhãn 0), `proposal_correct` FAIL (20000 ≠ 0). Reply "đã hoàn 20.000đ" khớp ledger — nhìn reply thì tưởng ổn, nhưng ledger đã ghi một khoản không được phép. |
| Bước sai đầu tiên | **#3 `model_override` `{"delay_days": 5}`** — ticket "Đơn giao trễ 5 ngày" đè lên `delay_days` của DB. |
| Vì sao là bước *đầu tiên* | #1 `handoff` đúng hợp đồng (chỉ tool read-only, `facts: {}`); #2 `investigator` đọc đơn O-202 từ DB với `status: delivered` (không trễ) — dữ kiện đúng. Mọi bước sau #3 chỉ là hệ quả: #4 quote 20.000đ được tính lại từ delay giả, #6 reply báo đúng số đã ghi. |
| Failure mode | **FM-03** ticket_trust (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed` C-002@11: #1 handoff, #2 investigator giống hệt, **không có `model_override`**, #3 `quote {"amount_vnd": 0, "reason": "no_entitlement"}`, #4 reply "chưa đủ điều kiện hoàn"; ledger 0 = nhãn; lab8 PASS. |
| Regression test | `src/tests/test_lab9_trace_case.py`: `test_trace_case_first_wrong_step_is_model_override` (assert event đầu tiên sai là `model_override {"delay_days": 5}` ngay sau `handoff, investigator`; `DbFactKept`, `RefundAmountCorrect`, `ProposalCorrect` đều False) và `test_trace_case_fixed_keeps_the_db_fact` (cùng claim@seed trên `fixed`: không có override, 3 grader True). Đã chạy: fail trên variant lỗi như mong đợi, pass trên `fixed` (`pytest -m student -o addopts= -k trace_case` → 2 passed). Ở mức eval set, item E-002 (FM-03) đã nằm trong v1 và gate chặn qua `refund_amount_correct`, `proposal_correct`. |
| Chưa chắc chắn | Trace không cho biết *vì sao* model chọn tin ticket (MockLLM bật cứng công tắc `ticket_trust`; với LLM thật cần log prompt/completion). Biến thể `quiet_override` cùng lỗi nhưng **không** ghi event `model_override` → `db_fact_kept` mù; chỉ grader mức outcome (`refund_amount_correct`, `proposal_correct`) bắt được. Vì vậy gate không được dựa vào `db_fact_kept` để chặn. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
