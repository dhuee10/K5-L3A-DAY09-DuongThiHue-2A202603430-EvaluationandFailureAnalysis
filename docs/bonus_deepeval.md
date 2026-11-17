# Bonus: port 3 grader sang DeepEval và so khớp kết quả

```bash
cd src
pip install -r bonus_lab9/requirements-bonus.txt     # deepeval==4.3.4 (không cần cho CI eval-gate)
python -m bonus_lab9.deepeval_port                   # ghi reports/bonus_deepeval.json
python -m pytest -q -m student -o addopts= -k bonus_deepeval
```

## Cách port

`src/bonus_lab9/deepeval_port.py` viết lại **độc lập** (không import `lab9.graders`) ba grader dưới dạng
`deepeval.metrics.BaseMetric`, mỗi trial là một `deepeval.test_case.LLMTestCase`:

| Metric lab9 (pydantic-evals) | Metric DeepEval | FM | Đọc từ |
|---|---|---|---|
| `approval_bypass` (`ApprovalBypass`) | `NoApprovalBypass` | FM-07, FM-02 | ledger snapshot + `unexpected_rows` + nhãn `approval_ok` |
| `refund_amount_correct` (`RefundAmountCorrect`) | `LedgerRefundAmount` | FM-03..06 | ledger `refund_vnd` vs nhãn |
| `reply_amount_matches_ledger` (`ReplyAmountMatchesLedger`) | `ReplyMatchesLedger` | FM-08 | event `reply` (= `actual_output`) vs ledger |

- Cả ba là metric **code**: `measure()` không gọi LLM, không cần API key, không đăng nhập Confident AI
  (gọi `metric.measure(test_case)` trực tiếp, telemetry tắt). Tiền và approval luôn chấm bằng code.
- Trial được chạy lại bằng đúng task của `lab9.eval` (SQLite mới cho mỗi item@seed, MockLLM), rồi so **từng dòng
  (item, seed)** với report pydantic-evals đã commit (`baseline_v1.json`, `eval_fixed.json`,
  `eval_seeded_regression.json`); với 3 probe chưa có report, phía pydantic-evals chạy `run_eval` ngay trong process.

## Kết quả (eval set v1 `35b7d324c778`, 14 item × 5 seed = 70 dòng/shape)

| Shape | Metric | pydantic-evals | DeepEval | Khớp từng dòng |
|---|---|---|---|---|
| swarm | approval_bypass / refund_amount_correct / reply_amount_matches_ledger | 0 / 0.9857 / 1.0 | 0 / 0.9857 / 1.0 | 100% / 100% / 100% |
| fixed | — | 0 / 1.0 / 1.0 | 0 / 1.0 / 1.0 | 100% / 100% / 100% |
| seeded_regression | — | 0 / 0.8571 / 0.7857 | 0 / 0.8571 / 0.7857 | 100% / 100% / 100% |
| probe_sibling_refund (FM-07) | — | **20** / 0.7143 / 1.0 | **20** / 0.7143 / 1.0 | 100% / 100% / 100% |
| probe_misreport (FM-08) | — | 0 / 1.0 / **0.8571** | 0 / 1.0 / **0.8571** | 100% / 100% / 100% |
| probe_round_down (FM-04) | — | 0 / **0.7143** / 1.0 | 0 / **0.7143** / 1.0 | 100% / 100% / 100% |

Tổng: 6 shape × 70 dòng × 3 metric = **1 260 phán quyết, 0 bất đồng**. Ba probe được thêm để phép so không
"rỗng": mỗi metric đều có shape mà nó thực sự bắn (20 vi phạm approval, 10 reply sai tiền, 20 ledger sai số).

## Nhận xét

- Hai harness cho cùng kết quả vì cả hai chấm **trạng thái** (ledger, event) chứ không chấm văn bản; đổi framework
  không đổi định nghĩa "đúng". Đây là lý do tiền/approval phải là code: kết quả tái lập được qua công cụ.
- Khác biệt thực tế: pydantic-evals cho `Dataset`/`Case` gọn và report có cấu trúc; DeepEval mạnh ở metric LLM
  (G-Eval…) nhưng mặc định hướng tới Confident AI — ở đây phải gọi `measure()` trực tiếp để chạy offline hoàn toàn.
- Giới hạn: chỉ port 3/7 metric; chưa port `pass_rate` (grader Lab 8) và chưa chạy trên eval set v2.
