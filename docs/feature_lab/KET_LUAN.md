# Kết luận Feature Lab — cấu hình cuối F9

**Chốt ngày 04/11/2026 bởi Research Lead (Tấn Phát). Cấu hình cuối = gate QPAF + Qwen3-Reranker-4B trên top-20 trang của gate.**

Lab F1–F9 tìm thay đổi kiến trúc tốt nhất bằng CV 5-fold trên dev pool ([README](README.md)). Không thay đổi nào ở phía gate
(F1–F4) được giữ; thứ nâng kết quả là một tín hiệu thứ tư, reranker. Trên held-out (post-hoc, mở nhãn một lần), cấu hình cuối đạt
nDCG@10 **0,8980** (ViDoSeek TEST-172, 172 query) và **0,9708** (ViMDoc confirmation, 8.904 query, mức document), hơn QPAF một mình
+0,0725 và +0,0092. **Lưu ý trung thực:** phần lớn mức tăng đến từ reranker. Gate thêm so với "static + reranker" (F7)
+0,0029 (không có ý nghĩa) trên ViDoSeek và +0,0025 trên ViMDoc, mức rất nhỏ (mục 4).

## 1. Cấu hình cuối

| Thành phần | Giá trị |
| --- | --- |
| Ba kênh điểm | BM25, BGE-M3 (dense), ColQwen2.5 (visual); pool = hợp các top list của ba kênh, không phải toàn corpus |
| Tầng 1: gate | QPAF baseline của lab (`--variant baseline`): 13 feature, residual tuyến tính, listwise loss, seed 20260820, `RECIPE` của lab. Held-out: train trên cả dev pool (970 / 2.000 query) |
| Top-K | 20 trang theo điểm của gate |
| Reranker | `Qwen/Qwen3-Reranker-4B` @ `22e68366`, bf16, `max_length` 1024, đầu vào = query + OCR trang (OCR rỗng vẫn chấm), không train |
| Luật trộn | Trong top-20: `2 + (1−λ)·minmax(gate) + λ·minmax(rerank)`; ngoài top-20 giữ điểm gate |
| λ | Hằng, fit trên điểm OOF dev gộp, hòa lấy λ nhỏ: ViDoSeek **0,9**, ViMDoc **0,5** (CV tính λ riêng theo fold) |
| Đơn vị chấm | ViDoSeek: trang. ViMDoc: document, điểm document = điểm trang cao nhất |

## 2. Đường đi tới cấu hình này

Delta nDCG@10 CV (1 seed, bootstrap ghép cặp 95%). Nguồn: [README](README.md), [F5](F5_reranker.md), [F6–F8](F6_F8_reranker.md), [F9](F9_gate_rerank.md).

| Feature | Ý tưởng | Kết quả CV | Quyết định |
| --- | --- | --- | --- |
| [F1](F1_content_features.md) | Feature nội dung (OCR, query, độ phủ) cho gate | Mọi delta âm; ViMDoc `f1_content_mlp` QPAF −0,0046 [−0,0085, −0,0007] | Bác bỏ 31/10 |
| [F2](F2_score_calibration.md) | Hiệu chỉnh điểm học được thay min-max | Mọi delta ≈ 0, không cái nào có ý nghĩa | Bác bỏ 31/10 |
| [F3](F3_ranking_objective.md) | ApproxNDCG, top-k, gộp document mềm | Chỉ ViDoSeek: 4 delta đều n.s., tốt nhất QPAF +0,0022 [−0,0018, +0,0062]; ViMDoc chưa chạy | Đóng 04/11 |
| [F4](F4_query_embedding.md) | Embedding query vào gate | Chưa chạy | Đóng 04/11, không có số liệu |
| [F5](F5_reranker.md) | `bge-reranker-v2-m3` zero-shot trên top-20 của static | ViDoSeek 0,8986 (so với static +0,0331 [+0,0237, +0,0429]); ViMDoc 0,9628 (+0,0043 [+0,0002, +0,0083]) | Giữ ý tưởng |
| [F6](F6_F8_reranker.md) | λ học được theo query/trang | Trên 4B: ViDoSeek không hơn λ hằng (−0,0025 / −0,0052); ViMDoc QPAF-λ 0,9733, +0,0027 [+0,0002, +0,0054] | Không đạt luật README §6 |
| F7 | Qwen3-Reranker 0,6B / 4B, bge + 4B | **4B tốt nhất**: ViDoSeek 0,9220, ViMDoc 0,9706. 0,6B: 0,8759 / 0,9626. bge + 4B: 0,9113 / 0,9646 | Chọn 4B |
| F8 | Reranker ảnh MonoQwen2-VL | ViDoSeek: trung bình với 4B làm 4B tệ đi (0,8869; −0,0351 [−0,0448, −0,0255]). ViMDoc chưa chấm (timeout 3 giờ) | Bác bỏ trên ViDoSeek |
| [F9](F9_gate_rerank.md) | Reranker sau gate đã train thay vì static | QPAF + 4B: ViDoSeek 0,9190, ViMDoc 0,9716; so với F7 −0,0030 [−0,0067, +0,0005] và +0,0010 [−0,0027, +0,0047] | **Chốt** |

**Vì sao F1–F4 không thể giúp.** Chẩn đoán out-of-fold ([F5 §1](F5_reranker.md)): khi positive ở hạng 2–10 trên ViDoSeek, 570/573 trang
xếp trên nó thuộc cùng document; positive là trang tốt nhất trong document của nó theo BM25/dense/visual chỉ 26/32/7 lần trên 256 query chưa đúng
ở top-1. Ba kênh không phân biệt được các trang anh em, nên trộn lại cả ba (kể cả bằng gate) không thêm thông tin. Reranker đọc đồng thời câu hỏi
và nội dung trang nên là tín hiệu thứ tư thực sự mới. Chọn F9 thay vì F7 là quyết định giữ gate QPAF của đề tài, không phải một chiến thắng thống kê (mục 4).

## 3. Kết quả held-out (post-hoc, mở nhãn một lần cho F9)

Mỗi split được đăng ký trước, niêm phong dự đoán, rồi mới mở nhãn đúng một lần. Không lựa chọn nào trong F5–F9 dùng nhãn hai split này.

**ViDoSeek TEST-172** (172 query, mức trang; đăng ký `3d6f2e8`, niêm phong `436f69b`, cho phép `82101ba`, kết quả `b28d5bd`; [kế hoạch](F9_heldout_vidoseek.md))

| Hàng | nDCG@10 | R@1 (%) | R@3 (%) | CV dev nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| static | 0,8255 | 65,12 | 91,28 | 0,8655 |
| QARF | 0,8218 | 63,95 | 90,70 | 0,8657 |
| QPAF | 0,8255 | 66,28 | 89,53 | 0,8609 |
| static + 4B (F7) | 0,8951 | 80,23 | 93,02 | 0,9220 |
| **QPAF + 4B (F9)** | **0,8980** | **81,98** | 92,44 | 0,9190 |

| So sánh ghép cặp (đăng ký trước) | nDCG@10 (thắng/hòa/thua) | R@1 (điểm %) |
| --- | --- | --- |
| **F9 − QPAF (chính)** | **+0,0725 [+0,0418, +0,1056]** 38/121/13 | **+15,70 [+9,30, +22,67]** |
| F9 − static | +0,0725 [+0,0412, +0,1061] 41/118/13 | +16,86 [+9,88, +23,84] |
| F9 − QARF | +0,0762 [+0,0448, +0,1091] 42/118/12 | +18,02 [+11,05, +25,00] |
| F9 − F7 | +0,0029 [−0,0082, +0,0148] 5/160/7 | +1,74 [−1,16, +4,65] |

**ViMDoc confirmation** (8.904 query, mức document; đăng ký `075466b`, niêm phong `0618428`, cho phép `d4a0c10`, kết quả `1d1a2fd`; [kế hoạch](F9_heldout_vimdoc.md))

| Hàng | nDCG@10 | R@1 (%) | R@3 (%) | CV dev nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| static | 0,9589 | 92,13 | 97,26 | 0,9586 |
| QARF | 0,9615 | 92,57 | 97,57 | 0,9611 |
| QPAF | 0,9615 | 92,48 | 97,64 | 0,9613 |
| static + 4B (F7) | 0,9682 | 93,80 | 98,05 | 0,9706 |
| **QPAF + 4B (F9)** | **0,9708** | **94,09** | **98,42** | 0,9716 |

| So sánh ghép cặp (đăng ký trước) | nDCG@10 (thắng/hòa/thua) | R@1 (điểm %) |
| --- | --- | --- |
| **F9 − QPAF (chính)** | **+0,0092 [+0,0076, +0,0110]** 362/8.434/108 | **+1,62 [+1,25, +2,00]** |
| F9 − static | +0,0118 [+0,0099, +0,0138] 402/8.359/143 | +1,97 [+1,55, +2,38] |
| F9 − QARF | +0,0093 [+0,0075, +0,0111] 369/8.389/146 | +1,53 [+1,13, +1,91] |
| F9 − F7 | +0,0025 [+0,0009, +0,0042] 219/8.518/167 | +0,29 [−0,04, +0,63] |

5 trong 8.904 query ViMDoc không có document đúng trong pool (nDCG@10 = 0 ở mọi hàng); ViDoSeek không có query nào như vậy.

## 4. Phần tăng đến từ đâu

Delta nDCG@10, CV (dev, 970 / 2.000 query) và held-out cạnh nhau.

| Thành phần | ViDoSeek CV | ViDoSeek held-out | ViMDoc CV | ViMDoc held-out |
| --- | --- | --- | --- | --- |
| Gate một mình: QPAF − static | −0,0046 [−0,0081, −0,0010] | −0,0001\* | +0,0027 [−0,0002, +0,0058] | +0,0026\* |
| Reranker một mình: F7 − static | +0,0566 [+0,0452, +0,0679] | +0,0695\* | +0,0120 [+0,0068, +0,0173] | +0,0093\* |
| Gate trên reranker: F9 − F7 | −0,0030 [−0,0067, +0,0005] | +0,0029 [−0,0082, +0,0148] | +0,0010 [−0,0027, +0,0047] | **+0,0025 [+0,0009, +0,0042]** |
| Tổng: F9 − static | +0,0535 [+0,0418, +0,0655] | +0,0725 [+0,0412, +0,1061] | +0,0130 [+0,0090, +0,0173] | +0,0118 [+0,0099, +0,0138] |

\* Hiệu hai trung bình trong bảng mục 3, không nằm trong các so sánh đăng ký trước nên không có khoảng tin cậy.

- **Reranker mang gần như toàn bộ mức tăng**, trên cả hai dataset và cả CV lẫn held-out.
- **Gate đứng trước reranker:** ViDoSeek không có ý nghĩa ở cả CV và held-out. ViMDoc: CV +0,0010 không có ý nghĩa; held-out +0,0025 có ý nghĩa trên
  nDCG@10 nhưng không có ý nghĩa trên R@1 (+0,29 điểm [−0,04, +0,63]), và là một trong bốn so sánh không hiệu chỉnh đa so sánh. Kết luận an toàn:
  gate **có thể thêm một chút, rất nhỏ**; chưa đủ bằng chứng để khẳng định.
- **Lạc quan do chọn lựa:** không thấy rõ. Trên ViDoSeek mức tăng held-out lớn hơn CV (F9 − static +0,0725 so với +0,0535). Trên ViMDoc nhỏ hơn một chút
  (+0,0118 so với +0,0130; F9 − QPAF +0,0092 so với +0,0103), nằm trong khoảng tin cậy của CV. Số held-out ViDoSeek chỉ có 172 query nên khoảng tin cậy rộng.

## 5. So sánh với bài báo HEAVEN

Chỉ ViDoSeek. 1.142 query = 970 hàng OOF dev đã commit + 172 hàng test; Recall mức trang như bảng 2 của HEAVEN
([arXiv:2510.22215](https://arxiv.org/abs/2510.22215)), nguồn: [`all_1142`](../../results/lab/vidoseek/heldout/heldout_result.json).

| Hệ thống | R@1 (%) | R@3 (%) |
| --- | ---: | ---: |
| Chúng ta: static | 72,33 | 91,16 |
| Chúng ta: QPAF | 71,89 | 90,28 |
| Chúng ta: static + 4B (F7) | 83,63 | 94,66 |
| **Chúng ta: QPAF + 4B (F9)** | **83,27** | **94,57** |
| Bài báo: ColQwen2.5 (toàn corpus) | 75,57 | 91,94 |
| Bài báo: HEAVEN (toàn corpus) | 75,04 | 91,33 |

Giới hạn khi so sánh:

- Pool của chúng ta là hợp top list của ba kênh, không phải toàn corpus.
- 970 trong 1.142 điểm là OOF của dev, không phải held-out; chỉ 172 là held-out.
- Chỉ khi có reranker mới vượt bài báo (R@1 +7,70 điểm so với ColQwen2.5); static và QPAF đứng một mình đều thấp hơn ColQwen2.5 của bài báo.
- Hệ thống tốn tính toán hơn nhiều: ba kênh cộng Qwen3-4B trên 20 trang mỗi query.
- **ViMDoc không so sánh được với bài báo:** dự án dùng nhãn mức document, bài báo báo mức trang.

## 6. Giới hạn và câu hỏi giáo viên có thể đặt

- **Held-out có sạch không?** Không, kết quả là post-hoc. TEST-172 đã mở hai lần (R7 và F9); ViMDoc confirmation mở ba lần (A005 Stage 5, R1, F9).
  Không lựa chọn nào trong F5–F9 (model, K, λ, biến thể) dùng nhãn hai split này, và các hàng F9 được đăng ký trước khi chấm. Kế hoạch ViMDoc được viết sau khi đã xem kết quả
  ViDoSeek; cấu hình không đổi. Kết quả chính thức sạch vẫn là A005 §2 và M5.9 theo [README §7](README.md); tài liệu này không thay chúng.
- **Thiên lệch do chọn?** Nhiều cấu hình được chấm trên cùng CV: F5–F9 có 12 cấu hình trên ViDoSeek và 10 trên ViMDoc (F5 1, F6 4, F7 3, F8 2 chỉ ViDoSeek, F9 2;
  không tính các hàng λ = 1), chưa kể F1–F3. Vì thế dùng "hơn một chục", không dùng con số chính xác. Held-out không được dùng để chọn gì, và không cho thấy lạc quan rõ (mục 4).
- **QPAF tự nó đóng góp bao nhiêu?** Rất ít. Gate không hơn static có ý nghĩa ở CV (ViDoSeek còn kém −0,0046); sau khi có reranker, +0,0029 n.s. và +0,0025 (mục 4).
  Tính "theo trang" chưa được chứng minh bằng F1–F4.
- **Vì sao không dùng F6 (λ học được) cho ViMDoc?** CV ViMDoc của QPAF-λ trên 4B là 0,9733, cao hơn F9 0,9716, nhưng chỉ +0,0027 so với λ hằng (sát biên), một seed, không hơn trên ViDoSeek
  và không đạt luật README §6. Không có so sánh F6 − F9 nên không khẳng định hơn.
- **Seed và phần cứng.** Gate một seed (20260820); CV một seed; không có ba seed. Reranker chấm một lần, bf16 trên GPU trộn A10/A10G. ViMDoc held-out chấm 203.331 cặp: 88/204 chunk
  trên workspace Modal `buiphat251399`, 116 chunk còn lại trên `tranthanhzt123321` sau khi chép nguyên byte chunk đã xong; cùng image, revision và code.
- **Chưa kiểm tra:** F3 trên ViMDoc, F4 (chưa chạy), F8 trên ViMDoc (chưa có điểm).
- **Chi phí.** JSON ghi 352 GPU-giây cho 4.016 cặp (ViDoSeek test) và 26.840 GPU-giây (≈ 7,5 GPU-giờ) cho 203.331 cặp (ViMDoc confirmation).
  Mỗi query cần ba kênh cộng Qwen3-4B trên khoảng 20 trang, đắt hơn đáng kể so với gate một mình.

## 7. Không làm tiếp

- Cả hai held-out đã dùng hết. Ý tưởng mới (ví dụ F6 λ học được cho ViMDoc) chỉ được chọn trên CV, và mọi con số held-out thêm sẽ lại là post-hoc.
- Bước "combo, 3 seed" của [README §7](README.md) không chạy vì không feature F1–F4 nào được giữ. Bước kiểm chứng held-out đã làm trực tiếp cho F9.

## 8. Chạy phương pháp cuối

Mã nằm ở [`src/qpaf/f9`](../../src/qpaf/f9/) (gói riêng) và [`scripts/run_f9.py`](../../scripts/run_f9.py); gói gọi lại nguyên code lab trong `src/qpaf/lab`, không sửa nó,
nên bằng chứng held-out ở mục 3 vẫn gắn với đúng code đã được cho phép. Ví dụ ViDoSeek TEST-172 (ViMDoc thêm `--dataset vimdoc --data <A005 Stage 1 cache>`; `<cache>` nằm ngoài repo vì cặp chứa OCR):

```powershell
.venv/Scripts/python.exe scripts/run_f9.py prepare --page-text <qpaf-lab-share>/assets/vidoseek_page_text.jsonl --out <cache>
$env:MODAL_PROFILE='<profile>'; $env:QPAF_RERANKER='qwen3-4b'; modal run --detach scripts/modal_lab_rerank.py --pairs <cache>/f9_pairs.json
$env:MODAL_PROFILE='<profile>'; $env:QPAF_RERANKER='qwen3-4b'; modal run scripts/modal_lab_rerank.py --pairs <cache>/f9_pairs.json --stage collect --out <cache>/f9_scores_qwen3-4b.json
.venv/Scripts/python.exe scripts/run_f9.py rank --cache <cache> --out <cache>/f9_top10.jsonl.gz
.venv/Scripts/python.exe scripts/run_f9.py verify --lab-cache <cache lab_heldout> [--refit]
```

- Hai lệnh `modal run` do người dùng chạy (`--detach`, rồi `collect` sau khi chunk xong); `rank` kiểm điểm là Qwen3-Reranker-4B @ `22e68366` trên đúng file cặp, rồi ghi top-10 đơn vị mỗi query.
- `verify` không đọc nhãn: tính lại hàng `f9_qpaf_qwen4b` từ điểm gate và điểm Qwen3-4B của lần chạy held-out và so với file dự đoán đã niêm phong (ViDoSeek: từng điểm trang; ViMDoc: top-10 document và điểm).
  Kết quả phải trùng tuyệt đối, nên gói mới tính cùng số với code đã sinh ra mục 3; `--refit` còn train lại gate trên dev và đòi điểm tầng 1 giống hệt.

## 9. Nguồn

- Tài liệu: [README](README.md), [F5](F5_reranker.md), [F6–F8](F6_F8_reranker.md), [F9](F9_gate_rerank.md), [held-out ViDoSeek](F9_heldout_vidoseek.md), [held-out ViMDoc](F9_heldout_vimdoc.md).
- Held-out: [ViDoSeek](../../results/lab/vidoseek/heldout/heldout_result.json), [ViMDoc](../../results/lab/vimdoc/heldout/heldout_result.json).
- CV ViDoSeek: [baseline](../../results/lab/vidoseek/vidoseek-baseline.json), [F5](../../results/lab/vidoseek/vidoseek-f5_rerank.json),
  [F7 4B](../../results/lab/vidoseek/vidoseek-f7_qwen4b.json), [F9](../../results/lab/vidoseek/vidoseek-f9_stack_qwen4b.json).
- CV ViMDoc: [baseline](../../results/lab/vimdoc/vimdoc-baseline.json), [F5](../../results/lab/vimdoc/vimdoc-f5_rerank.json),
  [F7 4B](../../results/lab/vimdoc/vimdoc-f7_qwen4b.json), [F9](../../results/lab/vimdoc/vimdoc-f9_stack_qwen4b.json).
- Các số CV của F1–F4 lấy từ khối "Trạng thái (04/11/2026)" trong [README](README.md) (Research Lead xem lại branch của từng thành viên); JSON của chúng không nằm trên branch này.
