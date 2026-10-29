# Báo cáo kết quả A005 (QPAF-SA-v2 trên ViMDoc)

Tài liệu cho nhóm project môn học. Mọi con số lấy nguyên từ các bản ghi JSON trong `evidence/revisions/`
(`a005-s3-001/baselines.json`, `a005-s4-001/runs/*/result.json`, `a005-s5-001/confirmation.json`,
`a005-s6-001/aggregate.json`). Các số trong bảng được làm tròn đến 6 chữ số thập phân, không đổi dấu và
không đổi kết luận của CI.

## 1. Phương pháp trong một đoạn

Mỗi query có một danh sách trang ứng viên, mỗi trang có điểm từ ba nguồn: BM25, BGE-M3 (dense) và ColQwen2.5
(visual). Baseline mạnh nhất là `train_fitted_static`: trộn ba điểm bằng một bộ trọng số cố định
w̄ = [0,1; 0,2; 0,7] (BM25, dense, visual), chọn trên tập train. **QPAF-SA-v2** giữ w̄ làm *neo tĩnh* và học thêm
một *phần dư theo từng trang*: trọng số của trang là `softmax((log(w̄ + ε) + Δθ(x)) / T)`, trong đó x là 13 đặc
trưng của trang (điểm, hạng nghịch đảo, khoảng cách điểm, bất đồng giữa các nguồn, độ dài query) và Δθ là một
phép tuyến tính 13→3 **khởi tạo bằng 0**. Vì vậy ở epoch 0 mô hình đúng bằng baseline tĩnh, và nó chỉ lệch khỏi
baseline khi dữ liệu train cho thấy có lợi. Hàm loss là listwise ở **mức document** (ViMDoc chỉ có nhãn
document, không gán nhãn xuống trang), với nhiệt độ τ được học. Checkpoint được chọn trong các epoch 0–20 theo
nDCG@10 trên validation (epoch 0 chính là baseline tĩnh nên không bao giờ tệ hơn baseline trên validation).
**QARF-SA-v2** là đối chứng khớp cặp, khác duy nhất ở chỗ cổng đọc đặc trưng *trung bình theo query* (một bộ trọng
số cho cả query) thay vì theo từng trang. Chạy 3 seed: 20260820, 20260821, 20260822.

## 2. Kết quả trên tập confirmation (mở một lần)

8.904 query, đơn vị document, nDCG@10.

| Phương pháp | nDCG@10 confirmation |
| --- | ---: |
| `train_fitted_static` | 0,958940 |
| `colqwen25` | 0,948576 |
| `uniform_combsum` | 0,944090 |
| `rrf_k60` | 0,937071 |
| `bm25` | 0,873752 |
| `bge_m3` | 0,869504 |
| QARF-SA-v2 (trung bình 3 seed) | 0,960990 |
| QPAF-SA-v2 (trung bình 3 seed) | 0,960760 |

Từng seed: QARF-SA-v2 0,961051 / 0,961068 / 0,960850; QPAF-SA-v2 0,960615 / 0,960325 / 0,961340.

### So sánh cặp theo query (QPAF-SA-v2 trừ đối tượng so sánh)

Cặp theo query, trung bình theo seed, bootstrap 10.000 lần theo query (seed 20260820), CI 95%.

| Đối tượng | Delta trung bình | CI95 | Thắng / Hòa / Thua |
| --- | ---: | --- | --- |
| `train_fitted_static` (baseline co-strongest) | +0,001820 | [+0,000541, +0,003173] | 224 / 8.482 / 198 |
| QARF-SA-v2 | −0,000230 | [−0,001358, +0,000928] | 208 / 8.478 / 218 |

### Verdict

**`QPAF_SA_BEATS_BASELINE`.** Quy tắc của A005 §6: với mọi baseline co-strongest (ở đây chỉ có
`train_fitted_static`), delta trung bình phải dương và cận dưới CI95 phải dương. Cả hai điều kiện đều đạt
(+0,001820; cận dưới +0,000541).

Cần nói rõ khi trình bày, vì verdict này hẹp hơn vẻ ngoài của nó:

- Mức tăng chỉ **+0,0018 nDCG@10** (khoảng 0,2 điểm phần trăm) và cận dưới CI chỉ +0,0005. Khoảng 95,3% query hòa;
  chỉ 224 query thắng so với 198 query thua.
- QPAF-SA-v2 **không khác biệt có ý nghĩa** so với QARF-SA-v2: delta −0,000230, CI chứa 0. QARF-SA-v2 còn cao hơn
  nhẹ về trung bình (0,960990 so với 0,960760). QARF-SA-v2 cũng hơn baseline tĩnh +0,002049. Vậy phần lớn lợi ích
  đến từ *neo tĩnh + phần dư học được*, **không** có bằng chứng rằng cổng theo từng trang tốt hơn cổng theo query.

Số query confirmation **không có positive trong pool ứng viên: 5** (trên 8.904). Chúng được giữ lại và tính nDCG@10
bằng 0 cho mọi phương pháp, nên không làm lệch so sánh giữa các phương pháp.

## 3. Số liệu validation (Stage 3–4) để đối chiếu

Validation: 400 query. Hai query (`8768`, `9437`) không có positive trong pool, được giữ và tính 0.

| Phương pháp | nDCG@10 validation |
| --- | ---: |
| `train_fitted_static` | 0,956878 |
| `colqwen25` | 0,950613 |
| `uniform_combsum` | 0,937525 |
| `rrf_k60` | 0,923119 |
| `bm25` | 0,876931 |
| `bge_m3` | 0,867827 |
| QARF-SA-v2 (3 seed: 0,960965 / 0,960446 / 0,960414; trung bình 0,960609) | tăng +0,003731 so với static |
| QPAF-SA-v2 (3 seed: 0,962421 / 0,961939 / 0,962267; trung bình 0,962209) | tăng +0,005331 so với static |

Epoch được chọn: QARF-SA-v2 là 16 / 13 / 15; QPAF-SA-v2 là 19 / 16 / 17. Mọi run nạp lại checkpoint trong tiến
trình mới cho sai khác tuyệt đối 0.

**Đối chiếu:** trên validation, QPAF-SA-v2 hơn QARF-SA-v2 khoảng +0,0016 và hơn static khoảng +0,0053. Trên
confirmation, lợi thế so với static co lại còn +0,0018 và lợi thế so với QARF-SA-v2 biến mất (−0,0002). Đây là
dấu hiệu điển hình của việc chọn checkpoint trên một tập validation nhỏ: một phần mức tăng validation là do
chọn epoch tốt nhất trên 400 query chứ không tổng quát hóa hoàn toàn.

## 4. Đã thử những gì

Trích từ `docs/06_handover/a005-exploration-log.md`:

- **Stage 1 (đầu vào).** Dựng pool ứng viên trên ViMDoc: OCR 76.347 trang, điểm ColQwen2.5 và BGE-M3, BM25 (phải
  chạy lại ở workspace Modal khác vì tải file 6,6 GB bị hỏng; ma trận chạy lại trùng từng byte). Kiểm coverage thì
  phát hiện 2 query validation không có positive trong pool. Quyết định: giữ lại, tính nDCG 0 cho mọi phương pháp,
  không mở rộng pool.
- **Stage 2 (cổng căn chỉnh trên train).** Với 1.600 query train và lưới 66 bộ trọng số tĩnh, loss listwise tương
  quan âm mạnh với nDCG@10 (Spearman −0,997); điểm loss thấp nhất là [0,1; 0,2; 0,7] và cũng là điểm nDCG tốt nhất
  của lưới (0,9612). Gate PASS, nên loss này đáng dùng để học.
- **Stage 3 (baseline validation).** 6 baseline; `train_fitted_static` mạnh nhất (0,9569), vượt cả ColQwen2.5 đơn
  lẻ (0,9506). Nó trở thành neo w̄ và là baseline co-strongest duy nhất. QARF-v1 (A001) không chạy vì cần nhãn
  trang mà ViMDoc không có.
- **Stage 4 (huấn luyện).** 6 run (QARF-SA-v2 ×3 rồi QPAF-SA-v2 ×3), mỗi run có authorization riêng, checkpoint
  2,7 KB đưa vào repo. QPAF-SA-v2 cải thiện validation +0,0051 đến +0,0055 so với static; quy tắc dừng sớm cho
  PROCEED.
- **Stage 5–6 (confirmation).** Mở nhãn confirmation đúng một lần sau khi kiểm hash file sealed, rồi tính thống kê
  cặp. Kết quả ở mục 2.

Không chạy biến thể nào khác của method sau khi mở confirmation, và không đổi seed hay checkpoint.

## 5. Hạn chế (cần nêu thật khi trả lời giáo viên)

- **Checkpoint chọn trên 400 query validation.** Tập này nhỏ, nên epoch tốt nhất có thể cao hơn thực tế do may mắn
  chọn lọc. Sự co lại của lợi thế từ validation sang confirmation (mục 3) phù hợp với điều này.
- **Baseline đã gần trần.** `train_fitted_static` đạt 0,9589 nDCG@10 và có 95% query hòa, nên không gian để cải
  thiện rất nhỏ; mức tăng +0,0018 đáng tin về mặt thống kê nhưng nhỏ về mặt thực tế.
- **Confirmation không tách rời về tài liệu với dev.** Cả hai dùng chung kho 1.247 document; chúng chỉ tách rời
  *theo query*, không tách rời *theo document*. Mô hình có thể đã được hưởng lợi gián tiếp từ việc thấy cùng tập
  document trong lúc train, nên kết quả không đại diện cho kho document hoàn toàn mới.
- **Một dataset duy nhất.** Chỉ có ViMDoc ở bước confirmation; không có bằng chứng về tổng quát hóa sang dataset
  khác (ViDoSeek chỉ dùng cho cổng Stage 0 trên train, test không được truy cập).
- **Không có bằng chứng cho phần "theo từng trang".** Điểm mới của QPAF so với QARF (cổng theo trang) không cho
  lợi thế đo được trên confirmation; nếu phải bảo vệ đóng góp, hãy nhấn mạnh neo tĩnh + phần dư khởi tạo bằng 0
  (an toàn, không tệ hơn baseline ở epoch 0), không nhấn mạnh tính theo trang.
- **Review độc lập được miễn** (`WAIVED_BY_A006`) vì đây là project môn học.
