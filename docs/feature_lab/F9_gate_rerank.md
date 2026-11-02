# F9 — Reranker sau gate QARF/QPAF đã train

**Người chạy:** Research Lead · **Chi phí:** gate train lại trên CPU (khoảng 3 + 8 phút), 11.885 cặp mới chấm
bằng Qwen3-Reranker-4B trên Modal (khoảng 2 + 7 phút, 4 GPU mỗi dataset)

Đọc [F5](F5_reranker.md) và [F6–F8](F6_F8_reranker.md) trước. F5–F7 đặt reranker sau **static** fusion, nên con
số của chúng không cho biết gate còn đóng góp gì khi đã có reranker. F9 giữ nguyên reranker của F7 và chỉ đổi
tầng đầu: top-20 trang và điểm fused lấy từ gate QARF/QPAF baseline đã train.

## 1. Thiết kế (chốt trước khi chấm)

| Mục | Giá trị |
| --- | --- |
| Gate | Baseline của lab (`--variant baseline`): 13 feature, residual tuyến tính, listwise loss, seed 20260820, train trên 4 fold, chấm fold còn lại |
| Kiểm tra gate | Điểm theo trang phải tái tạo đúng từng dòng `baseline_qarf` / `baseline_qpaf` đã commit (lệch ≤ 1e-12); lệch thực tế 0 trên cả hai dataset |
| Reranker | `Qwen/Qwen3-Reranker-4B` như F7. Cặp đã chấm ở F7 được dùng lại; chỉ cặp mới lọt vào top-20 của gate mới chấm (ViDoSeek 3.253, ViMDoc 8.632) |
| Luật trộn | Như F5, trên điểm gate: top-20 nhận `2 + (1−λ)·minmax(gate) + λ·minmax(rerank)`. λ = 0 trùng đúng dòng baseline (script kiểm tra) |
| λ | Hằng, fit trên các fold train, lưới {0; 0,1; …; 1}, hòa lấy λ nhỏ |
| Biến thể | Chính: QPAF + 4B. Phụ: QARF + 4B. So ghép cặp với static, baseline QARF/QPAF, F7 (static + 4B) và F5 |

## 2. Chạy

```powershell
.venv/Scripts/python.exe scripts/lab_rerank.py base --dataset vidoseek --data <bundle> --out <cache>/vidoseek_gate_pages.npz
.venv/Scripts/python.exe scripts/lab_rerank.py pairs --dataset vidoseek --data <bundle> --page-text <share>/assets/vidoseek_page_text.jsonl --base <cache>/vidoseek_gate_pages.npz --skip <cache>/vidoseek_pairs.json --out <cache>/vidoseek_pairs_gate.json
$env:MODAL_PROFILE='buiphat251399'; $env:QPAF_RERANKER='qwen3-4b'; modal run scripts/modal_lab_rerank.py --pairs <cache>/vidoseek_pairs_gate.json --out <cache>/vidoseek_scores_gate_qwen3-4b.json
.venv/Scripts/python.exe scripts/lab_rerank.py stack --dataset vidoseek --data <bundle> --base <cache>/vidoseek_gate_pages.npz --pairs <cache>/vidoseek_pairs.json --scores <cache>/vidoseek_scores_qwen3-4b.json --pairs <cache>/vidoseek_pairs_gate.json --scores <cache>/vidoseek_scores_gate_qwen3-4b.json --name f9_stack_qwen4b --against results/lab/vidoseek/vidoseek-f7_qwen4b.json
```

File `.npz` điểm gate và file cặp để ngoài repo; chỉ commit `results/lab/<dataset>/<dataset>-f9_stack_qwen4b.json`.

## 3. Kết quả sàng lọc (2/11/2026, 1 lần chấm)

| Dataset | Baseline QPAF | **QPAF + 4B** | QARF + 4B | F7 static + 4B | λ các fold (QPAF) |
| --- | ---: | ---: | ---: | ---: | --- |
| ViDoSeek | 0,8609 | **0,9190** | 0,9194 | 0,9220 | 0,8 / 0,9 / 0,9 / 0,9 / 0,8 |
| ViMDoc | 0,9613 | **0,9716** | 0,9699 | 0,9706 | 0,5 ×5 |

| So sánh ghép cặp | ViDoSeek | ViMDoc |
| --- | --- | --- |
| QPAF + 4B − baseline QPAF | **+0,0581 [+0,0460, +0,0704]** 187/729/54 | **+0,0103 [+0,0069, +0,0139]** 88/1888/24 |
| QPAF + 4B − baseline QARF | +0,0533 [+0,0415, +0,0650] | +0,0105 [+0,0068, +0,0144] |
| QPAF + 4B − F7 (static + 4B) | −0,0030 [−0,0067, +0,0005] 13/934/23 | +0,0010 [−0,0027, +0,0047] 47/1912/41 |
| QPAF + 4B − QARF + 4B | −0,0004 [−0,0035, +0,0027] | +0,0017 [−0,0006, +0,0041] |
| QPAF + 4B − F5 | +0,0204 [+0,0103, +0,0304] | +0,0088 [+0,0046, +0,0130] |

## 4. Đọc kết quả

- Hệ thống "QPAF + reranker" hơn QPAF một mình có ý nghĩa trên cả hai dataset. Đây là con số đúng để báo cáo
  khi phương pháp cuối giữ gate QPAF.
- Nhưng gate không còn đóng góp gì thêm khi đã có reranker: so với static + 4B, QPAF + 4B lệch −0,003 trên ViDoSeek
  và +0,001 trên ViMDoc, cả hai đều không có ý nghĩa. QPAF và QARF cũng ngang nhau. Gần như toàn bộ mức tăng đến từ
  reranker.
- Trên ViMDoc, gate xếp tốt hơn static nên λ được fit nhỏ hơn (0,5 so với 0,8 của F7): reranker được tin ít hơn
  khi tầng đầu đã tốt.

## 5. Lưu ý

- Gate một seed (đúng như baseline đã commit), reranker chấm một lần trên GPU trộn A10/A10G.
- Cặp mới và cặp cũ được chấm ở hai lượt khác nhau của cùng model và revision; bf16 có thể lệch rất nhỏ giữa GPU.
- Held-out chưa đụng tới.
