# Yêu cầu review độc lập A005, gửi Thanh

**Người yêu cầu:** Tấn Phát (Research Lead). **Ngày:** 2026-10-28.
**Nhánh:** `feature/a005-qpaf-sa`.
**Reviewer:** Thanh. Research Lead chọn trong phiên làm việc, nguyên văn: "Thanh, replay thật".

## Cần review gì

- [`QPAF-M1.5-A005.md`](../../evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A005.md),
  SHA-256 `edf84064…a4a4`. Research Lead đã duyệt bản này
  ([approval-001](../../evidence/M1_FINAL/02_protocol/amendments/QPAF-M1.5-A005.approval-001.md)).
- Nội dung A005: QPAF-SA-v2, tức gate neo vào trọng số static cộng phần dư học được, loss
  listwise trên document với temperature học trên train, và chọn checkpoint trong epoch 0–20.
  Kết quả được khẳng định trên ViMDoc confirmation 8.904 query. TEST-172 đóng hẳn với A005.

Đây là bước 6 của quy trình amendment. A005 §8 yêu cầu bước này trước Stage 0, nên
**chưa có stage nào được chạy** cho đến khi anh nghiệm thu.

## Phần 1 — replay trên máy của anh (bắt buộc)

"Replay thật" nghĩa là anh tự chạy lệnh trên máy mình, từ một bản clone đầy đủ (không
shallow), rồi dán output vào phần nghiệm thu. Dùng GPT để đọc output thì được, nhưng lệnh
phải do anh chạy.

```powershell
git fetch origin
git checkout feature/a005-qpaf-sa
python scripts/verify_a005.py
python -m unittest tests.test_a005_verify -v
```

`verify_a005.py` chỉ đọc, không đọc nhãn, không train, không cấp quyền chạy. Nó kiểm:

1. **Bytes của A005** khớp với hash mà Research Lead đã duyệt.
2. **12 hash identity** ở §1, đọc từ commit `1cecddb6…59c5`. Mỗi dòng in ra phải ghi
   commit này, không phải `working-tree`.
3. **19 số và trạng thái A005 trích dẫn**, lấy lại từ file gốc:
   - kết quả M5.7 trên TEST-172 và quyết định G3;
   - số validation của M4.4/M4.5;
   - probe A001 của M4.6;
   - trọng số static `[0, 0.1, 0.9]`;
   - số ID và trạng thái seal ViMDoc của M4.1.
4. **Ablation M5.6** nằm trong ±0,002.
5. **Trọng số epoch 0** là `[0.000997, 0.100698, 0.898305]`.

Kết quả mong đợi: `"FAIL": 0`. Trên máy của Claude ngày 2026-10-28, kết quả là 35 PASS / 0 FAIL.

## Phần 2 — kiểm thiết kế (anh tự đánh giá)

Script không trả lời được các câu dưới đây. Anh ghi PASS, FAIL hoặc góp ý cho từng câu.

1. **Leakage (§6).**
   - Có đường nào để nhãn ViMDoc confirmation, hay nhãn TEST-172, lọt vào train, chọn
     checkpoint hay chọn baseline không?
   - Corpus 1.247 document dùng chung giữa train và confirmation. Việc yêu cầu phân tích
     overlap của M4.1 trước Stage 5 đã đủ chưa?
2. **Post hoc (§4).** A005 được viết sau khi đã thấy TEST-172. Các chốt sau có đủ chặn
   result shopping không?
   - một phương pháp duy nhất;
   - gate train-only với đúng ngưỡng của A004;
   - luật dừng `NO_LEARNED_DEVIATION`;
   - một lần mở ViMDoc.
3. **Hyperparameter.**
   - `ε = 1e-3`, cùng giá trị khởi tạo và khoảng clamp của `η`, có thực sự "chốt trước"
     không?
   - Có giá trị nào ngầm được chọn theo kết quả không?
   - Lập luận "học `τ` trên train" có giải quyết đúng lý do A004 đã loại loss listwise không?
4. **Công bằng (§6).**
   - QPAF-SA chứa static ở epoch 0, còn baseline vẫn được fit và chọn độc lập. Như vậy có
     công bằng không?
   - QARF-SA còn matched đúng nghĩa không?
5. **Gate profile loss (§4.3).** Lấy min theo `τ ∈ [1e-3, 1]` bằng golden-section 60 vòng.
   Cách này có làm gate dễ đạt hơn so với A004 không?
6. **Claim (§6).** Điều kiện 4 của §5 phải đạt trên ViMDoc, với CI95 dưới > 0. Kết quả âm
   của QPAF-v1 vẫn phải được báo cáo. Ranh giới này đã đủ rõ chưa?

## Cách ghi nghiệm thu

Anh trả lời bằng lời của chính anh: chấp nhận, chấp nhận kèm điều kiện, hoặc yêu cầu sửa.
Kèm theo output của Phần 1. Câu trả lời được ghi nguyên văn vào
`QPAF-M1.5-A005.signoff-001.md`, cùng mẫu với A003. Không ai được viết thay câu nghiệm thu
của anh.

Sau khi có cả hai chữ ký, governance event của A005 mới được thêm (A005 §8). Khi đó nhóm
mới xin authorization cho Stage 0: probe chỉ dùng ViDoSeek train, CPU, không train.
