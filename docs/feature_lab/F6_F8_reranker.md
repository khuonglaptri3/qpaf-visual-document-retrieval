# F6–F8 — Mở rộng F5: λ học được, reranker lớn hơn, reranker ảnh

**Người chạy:** Research Lead · **Chi phí (Modal `buiphat251399`):** Qwen3 khoảng 1 GPU-giờ; MonoQwen2-VL khoảng
7 GPU-giờ cho ViDoSeek, cộng khoảng 12 GPU-giờ của lượt ViMDoc bị cắt

Đọc [F5](F5_reranker.md) trước. F6–F8 giữ nguyên pool, fold, top-20 theo anchor của fold, luật trộn và bootstrap
của F5; mỗi feature chỉ đổi một chỗ.

## 1. Giả thuyết (chốt trước khi chấm)

| Feature | Đổi gì so với F5 | Giả thuyết |
| --- | --- | --- |
| F6 | λ hằng → λ học theo query (QARF-λ) hoặc theo trang (QPAF-λ) | Reranker text sai khi OCR rỗng hoặc khi nó không chắc; λ theo trang tránh được các trường hợp đó, nhất là trên ViMDoc (2.169 trang OCR rỗng) |
| F7 | `bge-reranker-v2-m3` → `Qwen3-Reranker` 0,6B / 4B, và trung bình bge + 4B | Reranker mạnh hơn phân biệt trang anh em tốt hơn, nên tăng ViDoSeek nhiều nhất |
| F8 | Reranker text → reranker ảnh `MonoQwen2-VL-v0.1`, và trung bình Qwen3-4B + MonoQwen2-VL | Reranker ảnh đọc được bảng, hình, trang OCR hỏng; bổ sung cho reranker text |

## 2. Thiết kế

| Mục | Giá trị |
| --- | --- |
| F6 gate | `λ = sigmoid(logit(λ0) + Δ(x))`, Δ tuyến tính khởi tạo bằng 0 nên epoch 0 trùng F5; λ0 là λ hằng fit trên các fold train; λ0 kẹp trong [0,05; 0,95] |
| F6 feature | QARF-λ, 6 feature/query: `fused_margin`, `rerank_max`, `rerank_margin`, `rerank_agrees_top1`, `rerank_std`, `log_query_words`. QPAF-λ thêm 7 feature/trang: `rerank_raw`, `rerank_norm`, `fused_norm`, `fused_rank`, `rerank_rank`, `ocr_empty`, `log_ocr_chars`. Chuẩn hoá bằng mean/std của fold train |
| F6 train | Recipe của lab (`qpaf.lab.train.RECIPE`: Adam 0,01, cosine, 40 epoch, trung bình tham số epoch 20–40, batch 16, clip 5), listwise loss trên các unit của top-20, 1 seed (20260820) |
| F7 model | `Qwen/Qwen3-Reranker-0.6B` @ `e61197ed`, `Qwen/Qwen3-Reranker-4B` @ `22e68366`, bf16, `max_length` 1024. Prompt và cách đọc log-odds "yes"/"no" theo model card; instruction: *Given a question, retrieve the document page that contains the answer* |
| F8 model | `lightonai/MonoQwen2-VL-v0.1` @ `7f91c3a5` (LoRA trên `Qwen/Qwen2-VL-2B-Instruct` @ `895c3a49`), bf16, `max_pixels` 1024·28·28, prompt và điểm `logit(True) − logit(False)` theo model card |
| F8 ảnh | ViMDoc: ảnh trang trong `ViMDoc_pages.tar.gz` (SHA-256 kiểm tra khi giải nén). ViDoSeek: render trang PDF ở 150 DPI bằng pypdfium2 (`<stem>_page_NNNN` là trang NNNN, đếm từ 1) |
| Trung bình model | Min-max điểm của từng model trong top-20 của mỗi query rồi lấy trung bình; λ fit như F5 |

Cả bốn model chỉ đọc query và trang, không thấy nhãn. Mọi biến thể và cách trung bình được chốt trước khi chấm;
không quét K, `max_length`, `max_pixels` hay prompt.

## 3. Chạy

```powershell
$env:MODAL_PROFILE='buiphat251399'; $env:QPAF_RERANKER='qwen3-4b'; modal run scripts/modal_lab_rerank.py --pairs <cache>/vidoseek_pairs.json --out <cache>/vidoseek_scores_qwen3-4b.json
.venv/Scripts/python.exe scripts/lab_rerank.py screen --dataset vidoseek --data <bundle> --pairs <cache>/vidoseek_pairs.json --scores <cache>/vidoseek_scores_qwen3-4b.json --name f7_qwen4b --against results/lab/vidoseek/vidoseek-f5_rerank.json
.venv/Scripts/python.exe scripts/lab_rerank.py gate --dataset vidoseek --data <bundle> --pairs <cache>/vidoseek_pairs.json --scores <cache>/vidoseek_scores_qwen3-4b.json --name f6_gate_qwen4b
modal run scripts/modal_lab_visual_rerank.py --pairs <cache>/vidoseek_pairs.json --stage prepare
modal run scripts/modal_lab_visual_rerank.py --pairs <cache>/vidoseek_pairs.json --stage score --out <cache>/vidoseek_scores_mono.json
```

Lặp `--scores` để trung bình nhiều model (ví dụ `f7_bge_qwen4b`, `f8_qwen4b_mono`). Workspace `buiphat251399`
chỉ cho 10 GPU cùng lúc; mỗi app dùng tối đa 4 container, nên chạy tối đa hai app GPU một lúc.

## 4. Kết quả sàng lọc (1–2/11/2026, 1 lần chấm, GPU A10/A10G)

nDCG@10 trung bình trên dev pool, 5 fold. Khoảng tin cậy là bootstrap ghép cặp 95%, kèm thắng/hòa/thua.

**ViDoSeek** (970 query; static 0,8655, QARF 0,8657, QPAF 0,8609, F5 0,8986)

| Biến thể | nDCG@10 | λ các fold | − static | − F5 |
| --- | ---: | --- | --- | --- |
| **F7 Qwen3-4B** | **0,9220** | 0,8 ×5 | **+0,0566 [+0,0452, +0,0679]** 175/751/44 | **+0,0234 [+0,0136, +0,0331]** 113/805/52 |
| F6 QARF-λ trên 4B | 0,9195 | λ0 0,8 | +0,0540 | so với 4B hằng: −0,0025 [−0,0073, +0,0023] |
| F6 QPAF-λ trên 4B | 0,9169 | λ0 0,8 | +0,0514 | so với 4B hằng: −0,0052 [−0,0106, +0,0001] |
| F7 Qwen3-4B, λ = 1 | 0,9148 | — | +0,0493 | — |
| F7 bge + 4B | 0,9113 | 0,7–0,9 | +0,0458 | +0,0127 [+0,0055, +0,0198] |
| F6 QARF-λ trên bge | 0,8972 | λ0 0,6 | +0,0317 | −0,0015 [−0,0057, +0,0026] |
| F6 QPAF-λ trên bge | 0,8963 | λ0 0,6 | +0,0308 | −0,0024 [−0,0075, +0,0025] |
| F8 4B + MonoQwen2-VL | 0,8869 | 0,6–0,8 | +0,0215 | −0,0117 [−0,0219, −0,0015]; so với 4B: **−0,0351** |
| F8 MonoQwen2-VL | 0,8774 | 0,4 ×5 | +0,0119 | −0,0213 [−0,0314, −0,0114]; so với 4B: **−0,0447** |
| F7 Qwen3-0.6B | 0,8759 | 0,5–0,6 | +0,0104 | −0,0228 [−0,0319, −0,0139] |
| F8 MonoQwen2-VL, λ = 1 | 0,8572 | — | −0,0083 | — |

**ViMDoc** (2000 query; static 0,9586, QARF 0,9611, QPAF 0,9613, F5 0,9628)

| Biến thể | nDCG@10 | λ các fold | − static | − F5 hoặc − λ hằng |
| --- | ---: | --- | --- | --- |
| **F6 QPAF-λ trên 4B** | **0,9733** | λ0 0,8 | **+0,0147 [+0,0101, +0,0196]** 97/1873/30 | so với 4B hằng: **+0,0027 [+0,0002, +0,0054]** 37/1936/27 |
| F6 QARF-λ trên 4B | 0,9728 | λ0 0,8 | +0,0142 | so với 4B hằng: +0,0022 [−0,0000, +0,0045] |
| **F7 Qwen3-4B** | **0,9706** | 0,8 ×5 | **+0,0120 [+0,0068, +0,0173]** 105/1843/52 | − F5: **+0,0077 [+0,0032, +0,0124]** 89/1861/50 |
| F6 QPAF-λ trên bge | 0,9701 | λ0 0,4–0,7 | +0,0116 | so với bge hằng: +0,0073 [+0,0040, +0,0109] |
| F6 QARF-λ trên bge | 0,9697 | λ0 0,4–0,7 | +0,0111 | so với bge hằng: +0,0069 [+0,0035, +0,0105] |
| F7 Qwen3-4B, λ = 1 | 0,9655 | — | +0,0069 | — |
| F7 bge + 4B | 0,9646 | 0,5–0,9 | +0,0060 | − F5: +0,0017 [−0,0010, +0,0046] |
| F7 Qwen3-0.6B | 0,9626 | 0,3–0,4 | +0,0040 | − F5: −0,0002 [−0,0036, +0,0032] |
| F8 (cả hai biến thể) | chưa chấm | | | |

So với baseline gate đã commit, F7 Qwen3-4B là +0,0563 (QARF) và +0,0612 (QPAF) trên ViDoSeek, +0,0094 và +0,0092
trên ViMDoc; F6 QPAF-λ trên 4B là +0,0122 và +0,0120 trên ViMDoc. Mọi khoảng tin cậy này đều nằm trên 0.

Thời gian chạy (wall clock, tối đa 4 container) cho 19.400 / 40.000 cặp: Qwen3-0.6B 3 / 14 phút, Qwen3-4B 8 / 29 phút, MonoQwen2-VL 108 phút
trên ViDoSeek với 4 A10. Lượt chấm F8 trên ViMDoc bị `timeout` 3 giờ ở phía client cắt khi đang chạy (cần khoảng
3,7 giờ), nên chưa có điểm. App mồ côi đã được dừng. Điểm của ViDoSeek đã được kiểm tra không lệch trang: dùng
một mình, MonoQwen2-VL vẫn đạt 0,8572 trong top-20.

## 5. Đọc kết quả

- **F7 Qwen3-4B (λ hằng):** đề xuất giữ. Thắng F5 có ý nghĩa trên cả hai dataset, λ = 0,8 ở mọi fold của cả hai.
  Đây cũng là biến thể tốt nhất trên ViDoSeek. Model 0,6B và cách trung bình bge + 4B đều kém 4B một mình.
- **F6:** chỉ giúp ViMDoc. Trên bge, λ học được thêm khoảng +0,007; trên 4B chỉ còn +0,002–0,003, ở sát biên
  ý nghĩa. Trên ViDoSeek F6 không bao giờ hơn λ hằng. Theo luật gộp ở README mục 6 (thắng ViDoSeek, không thua
  ViMDoc), F6 không đạt. Research Lead quyết định có dùng nó riêng cho ViMDoc hay không.
- **F8:** đề xuất bác bỏ. Trên ViDoSeek, reranker ảnh kém cả bge, và trung bình nó với Qwen3-4B làm 4B tệ đi rõ
  (−0,0351). Chưa có số trên ViMDoc; chạy lại tốn khoảng 15 GPU-giờ A10.

## 6. Lưu ý

- Khoảng 10 biến thể đã được chấm trên cùng CV của mỗi dataset, nên biến thể tốt nhất bị lạc quan do chọn lựa.
  Khoảng tin cậy của F7 − F5 nằm xa 0 trên cả hai dataset; của F6 trên 4B thì sát 0, nên dễ là do chọn lựa.
- Mỗi model chỉ chấm một lần, bf16 trên GPU trộn A10/A10G. F6 chỉ train một seed.
- Held-out chưa đụng tới. Cấu hình cuối chỉ được chạy trên held-out một lần, sau khi đã chốt.

## 7. Bước sau

1. Chốt F7 Qwen3-4B làm reranker, rồi chạy held-out một lần với cấu hình đã chốt.
2. Nếu vẫn cần F8 trên ViMDoc: thêm checkpoint theo chunk lên Volume và đặt `timeout` ≥ 5 giờ trước khi chạy lại.
3. QPAF bốn kênh (xem F5 mục 5): lần này với Qwen3-4B làm kênh thứ tư.

Reranker đặt sau gate QARF/QPAF đã train (thay vì sau static) được thử ở [F9](F9_gate_rerank.md).
