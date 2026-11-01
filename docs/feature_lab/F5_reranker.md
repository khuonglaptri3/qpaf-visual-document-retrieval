# F5 — Reranker zero-shot trên top-K làm tín hiệu thứ tư

**Người chạy:** Research Lead · **Chi phí:** khoảng 59k cặp (query, OCR trang) trên một GPU Modal, không train

Đọc [README](README.md) trước để nắm protocol chung. File này chỉ mô tả phần riêng của F5.

## 1. Vì sao có F5

Sau khi F1 và F2 bị bác bỏ (31/10/2026), một lượt chẩn đoán out-of-fold (cùng fold, cùng lưới 66 điểm, không
train) cho thấy giới hạn nằm ở **thông tin của ba kênh**, không nằm ở gate:

| Quan sát | ViMDoc | ViDoSeek |
| --- | --- | --- |
| Chỉ kênh visual / static | 0,9525 / 0,9586 | 0,8613 / 0,8655 |
| Static với z-score, top-50 min-max | ±0,0001 | −0,0005, +0,0009 (không ý nghĩa) |
| Static với RRF k=60 | **−0,0056** | **−0,0051** |
| Phần nDCG mất do positive ở hạng 2–10 | 63/83 | 113/130 |

Trên ViDoSeek (mỗi query đúng một trang liên quan), khi positive ở hạng 2–10 thì **570/573** trang xếp trên nó
thuộc *cùng document*. Trong 256 query chưa đúng ở top-1, positive là trang tốt nhất trong document của nó theo
BM25/dense/visual chỉ 26/32/7 lần. Xếp document bằng một bộ trọng số rồi xếp trang bằng bộ khác chỉ được +0,0002.
Nghĩa là ba kênh đều không phân biệt được các trang anh em; gate trộn lại chúng cũng không thể.

**Giả thuyết H-F5:** một cross-encoder đọc đồng thời câu hỏi và nội dung trang phân biệt được các trang này,
nên nâng nDCG@10 trên ViDoSeek rõ hơn trên ViMDoc.

## 2. Thiết kế (chốt trước khi chấm)

| Mục | Giá trị |
| --- | --- |
| Model | `BAAI/bge-reranker-v2-m3` @ `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, fp16, `max_length` 1024 |
| Input | Câu query + OCR trang trong `qpaf-lab-share/assets/<dataset>_page_text.jsonl` (OCR rỗng vẫn chấm) |
| Trang được chấm | Top-20 trang của mỗi query theo static anchor **của fold chứa query** (anchor fit trên các fold khác) |
| Luật trộn | Trong top-20: `2 + (1−λ)·minmax(fused) + λ·minmax(rerank)`; ngoài top-20 giữ điểm fused. λ = 0 trùng static |
| λ | Lưới {0; 0,1; …; 1}, fit trên các fold train, hòa thì lấy λ nhỏ hơn. Báo cáo thêm λ = 1 (chỉ reranker) |
| So sánh | Bootstrap ghép cặp như lab: với `static`, và với `baseline` QARF/QPAF đã commit |

Reranker không thấy nhãn nên điểm của nó là một tín hiệu label-free; chỉ λ và anchor dùng nhãn, và đều fit
trên fold train. K = 20 và `max_length` không được quét.

## 3. Chạy

```powershell
.venv/Scripts/python.exe scripts/lab_rerank.py pairs --dataset vidoseek --data <bundle> --page-text <share>/assets/vidoseek_page_text.jsonl --out <cache>/vidoseek_pairs.json
$env:MODAL_PROFILE='buiphat251399'; modal run scripts/modal_lab_rerank.py --pairs <cache>/vidoseek_pairs.json --out <cache>/vidoseek_scores.json
.venv/Scripts/python.exe scripts/lab_rerank.py screen --dataset vidoseek --data <bundle> --pairs <cache>/vidoseek_pairs.json --scores <cache>/vidoseek_scores.json
```

Lặp lại với `vimdoc` (data: thư mục cache ViMDoc). File cặp chứa OCR nên để ngoài repo; chỉ commit JSON kết quả
`results/lab/<dataset>/<dataset>-f5_rerank.json`.

## 4. Kết quả sàng lọc (1/11/2026, 1 lần chấm, Modal `buiphat251399`, GPU A10/A10G/T4)

| Dataset | static | F5 (λ fit theo fold) | Chỉ reranker (λ = 1) | λ các fold | F5 − static | F5 − QARF | F5 − QPAF |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| ViDoSeek | 0,8655 | **0,8986** | 0,8725 | 0,6 ×5 | **+0,0331 [+0,0237, +0,0429]** 144/770/56 | **+0,0329** 147/771/52 | **+0,0377** 156/759/55 |
| ViMDoc | 0,9586 | 0,9628 | 0,9582 | 0,7 / 0,5 / 0,5 / 0,5 / 0,4 | +0,0043 [+0,0002, +0,0083] 81/1873/46 | +0,0017 [−0,0026, +0,0058] | +0,0015 [−0,0030, +0,0059] |

Reranker một mình không hơn static; phần tăng đến từ việc trộn nó với fusion cũ. Theo luật gộp đề xuất ở README
mục 6 (thắng trên ViDoSeek, không thua trên ViMDoc), F5 được giữ. Chấm 59.400 cặp mất khoảng 2 + 9 phút GPU.

## 5. Bước sau nếu F5 thắng

QPAF trên bốn kênh (ba kênh cũ + reranker trên top-K): gate lần đầu có lý do để thích ứng theo trang, ví dụ bỏ
qua reranker text khi OCR rỗng (ViMDoc có 2.169 trang OCR rỗng). Việc này cần đổi harness từ 3 sang 4 kênh trên
`feature/lab-feature-plans`.

Các bước mở rộng F5 (λ học được, Qwen3-Reranker, reranker ảnh) nằm ở [F6–F8](F6_F8_reranker.md).
