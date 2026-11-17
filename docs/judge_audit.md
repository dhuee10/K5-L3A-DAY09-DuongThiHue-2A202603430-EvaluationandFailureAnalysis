# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (backend REPLAY, verdict của judge lưu sẵn trong CSV; lớp dương = `FAIL`).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | **Đạt** — tp 24, fp 4, fn 6, tn 66 | **dùng** (chỉ cho tiêu chí giọng văn, không chặn tiền) |
| helpful (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** κ và R — tp 9, fp 0, fn 21, tn 70 | **loại** |

Tỉ lệ lỗi: tone quan sát 0.28 → hiệu chỉnh Rogan-Gladen 0.30 (gần đúng, judge ít lệch).
helpful quan sát 0.09 → hiệu chỉnh 0.30: judge **báo thiếu 3 lần** số reply có vấn đề.

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách khiếu nại. Rubric thêm: *bắt buộc xưng "LogiX"/"anh/chị"; "em/bạn/nha/nhé" ⇒ FAIL.* |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…rồi nha." | PASS | FAIL | Người | Cùng lỗi xưng hô ("bạn ơi"). Judge đánh đồng thân thiện với lịch sự. Thêm 2 ví dụ few-shot FAIL có "bạn" vào prompt judge. |
| 3 | H-029 "Dạ, vui lòng chờ…không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh bị che bởi "Dạ, vui lòng". Rubric: *chấm cả câu, không cho điểm vì từ khoá lịch sự mở đầu; câu cấm khách liên hệ ⇒ FAIL.* |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". Rubric: *không bắt buộc câu xin lỗi khi yêu cầu đã được giải quyết.* |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | Từ "refund" được CS LogiX cho phép; judge phạt tiếng Anh. Rubric thêm whitelist thuật ngữ: refund, ship, COD. |
| 6 | H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | Người | Hứa ngoài kết quả hệ thống — đây là lỗi **nội dung**, không phải giọng văn. Không sửa rubric tone; chuyển sang grader code `reply_amount_matches_ledger` (FM-08) + kiểm cụm "sẽ hoàn thêm". |
| 7 | H-070 "…đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Emoji cười trong ngữ cảnh khiếu nại. Rubric: *emoji ⇒ FAIL* (đơn giản hơn: chặn bằng regex trước khi gọi judge). |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Ghi chú gốc: nhãn người sai (đọc nhầm ticket). Hành động: **sửa nhãn người** trong bản v2 của CSV và ghi lại lý do; không đổi rubric. |
| 9 | HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | Người | Judge helpful không nhìn ledger nên không thể biết số sai. 18/21 lỗi bị bỏ sót của helpful là "sai tiền". ⇒ tiêu chí này phải là code. |
| 10 | HL-016 xin lỗi dài + "đã hoàn 55.000đ" (ledger 35.000đ) | PASS | FAIL | Người | Câu xin lỗi dài, trôi chảy làm judge chấm "hữu ích" dù sai tiền — đúng mô hình "fluent text hides a wrong refund". |

## Kết luận

- **tone_ok: dùng được** (κ 0.757, P 0.857, R 0.80 đều qua sàn). Chỉ dùng làm metric theo dõi chất lượng giọng văn; không dùng để chặn tiền/approval. Sửa rubric theo các dòng 1–5, 7 rồi calibrate lại trên nhãn mới.
- **helpful: loại, không được dùng làm gate.** Ma trận nhầm lẫn: tp 9, fp 0, **fn 21**, tn 70 → recall 0.30 (< 0.7), κ 0.375 (< 0.6). Precision 1.0 chỉ có nghĩa "khi judge nói FAIL thì đúng"; nhưng judge **bỏ sót 70% reply hỏng**, và 18/21 ca bỏ sót là sai số tiền — thứ judge không thể thấy vì không đọc ledger. Một gate dùng judge này sẽ cho merge gần như mọi regression FM-08. Thay bằng grader code `reply_amount_matches_ledger` (blocking, min 1.0) — xem `lab9/graders.py`.
- Tỉ lệ lỗi helpful đã hiệu chỉnh (0.30) cao hơn 3 lần quan sát (0.09): báo cáo dùng số quan sát sẽ đánh giá agent tốt hơn thực tế.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng/tiêu chí); cần nhãn người mới, gán mù, để có held-out thật trước khi tin số κ. Một nhãn người (H-081) đã sai ⇒ cần 2 người gán nhãn và đo κ giữa người với người.
