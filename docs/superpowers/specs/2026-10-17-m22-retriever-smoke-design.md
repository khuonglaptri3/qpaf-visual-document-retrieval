# M2.2 — Đặc tả chạy thử BM25, BGE-M3 và ColQwen2.5

**Ngày:** 2026-10-17

**Trạng thái:** IMPLEMENTED / VERIFIED — run mẫu thật PASS với visual float32.

**Owner theo milestone:** Khương.

## 1. Mục tiêu và phạm vi

Xây dựng pipeline chạy thử có kiểm soát trên mẫu dữ liệu thật, xác nhận cả ba
retriever hoạt động đúng và đo tài nguyên trước khi chuẩn bị chạy toàn bộ dữ liệu.
Đầu ra milestone gốc là: pinned 3-retriever smoke test, parity checks và resource caps.

Nguồn đối chiếu:

- Bảng milestone: `docs/GUILDLINE_OVERVIEWS_PROPOSAL/POAI_Milestone_Group01_Hoan_Chinh.xlsx`, mục M2.2.
- [Bản M2.1 được chọn](../../../evidence/revisions/m2.1-002/README.md).
- [Quyết định G1](../../../evidence/M1_FINAL/06_G1/G1_final_decision.md).
- [Các hàm truy xuất hiện có](../../../src/qpaf/m11/retrieval.py).

Hiệu chuẩn ngưỡng OCR thuộc M2.3; cache toàn corpus thuộc M2.8; huấn luyện
QARF/QPAF thuộc M3. Thành công trên mẫu không chứng minh chất lượng toàn corpus.

## 2. Quyết định và trạng thái môi trường

| Hạng mục | Trạng thái đã biết | Việc còn cần làm |
|---|---|---|
| Visual model | ColQwen2.5 đã ghim base/adapter/processor/tokenizer ở mục 9 | Đã chạy thật PASS với float32 |
| Code visual | `retrieval.py` hỗ trợ ColQwen2.5; mặc định M1.1 giữ ColQwen2 | Regression và smoke đã kiểm chứng |
| Dense model | BGE-M3 đã ghim model/tokenizer và inference config | Đã chạy thật PASS |
| BM25 | Scorer được tái sử dụng, khóa tokenizer/k1/b | Tham chiếu độc lập PASS |
| Modal | SDK 1.5.5; workspace `tlcn-group1`; NVIDIA A10/CUDA 12.6 đã chạy thật | Các app đã dừng; dữ liệu giữ trong Volume |
| PyTorch local | Import thất bại với `WinError 126`, liên quan `torch/lib/shm.dll` | Chẩn đoán nếu cần chạy local; nguyên nhân chưa xác định |

Lệnh `modal app list --json` trả `[]`, exit code 0. Đây là bằng chứng kết nối và
xác thực API thành công, chưa xác nhận khả năng chạy container/GPU hoặc load model.
Việc người dùng chọn ColQwen2.5 được ghi nhận tại đây; đây không phải chữ ký thay
Phát hoặc bản thông qua toàn bộ giao thức learned training.

## 3. Hợp đồng cấu hình

Cấu hình riêng đặt tại `configs/m2.2/retriever_smoke.toml`. Trước khi chạy phải khóa:

- Model/base/adapter, tokenizer/processor và các revision cần thiết.
- Seed; batch size; max text length; query/page prefix; dtype; device.
- Kích thước ảnh, DPI và chính sách native text/OCR hiện hành, ghi rõ phần còn tạm thời.
- Python và dependency; loại GPU; số container; CPU/RAM; timeout và chính sách retry.
- Kích thước mẫu; giới hạn VRAM/artifact; dung sai parity và cách đo.

Không kế thừa ngầm tham số từ M1.1: mọi giá trị hiệu lực cần xuất vào resolved config.
Các giá trị số chưa thống nhất phải để trạng thái pending, không trình bày là đã khóa.

## 4. Mẫu dữ liệu và đầu vào chung

Đọc và xác minh manifest M2.1 đã khóa. Lấy mẫu xác định từ train/validation với
mục đích và số lượng từng split được ghi rõ; giữ test cho đánh giá sau.
Lưu thuật toán chọn mẫu, seed, query IDs, page IDs và hash các nguồn.

Danh sách trang được chọn độc lập với qrels. Không đưa câu trả lời/nhãn liên quan
vào đầu vào scorer. Chuẩn bị text/ảnh cho cùng danh sách trang và giữ nguyên thứ tự
trên cả ba kênh. Ghi nhận lỗi extraction và hash text/ảnh, tránh âm thầm bỏ trang.

## 5. Runner và kiểm tra tính đúng

Tái sử dụng các hàm phù hợp trong `retrieval.py`; model giữ nguyên trọng số.
Mỗi kênh xuất ma trận query × page, metadata, cache và embedding khi áp dụng.

Các kiểm tra bắt buộc:

- IDs không thiếu, trùng hoặc lệch thứ tự; ma trận có đúng shape, chỉ gồm giá trị hữu hạn.
- Cache lưu/đọc giữ nguyên IDs, điểm số và kết quả xếp hạng theo quy tắc tie đã ghi.
- BM25: đối chiếu scorer tham chiếu độc lập trên cùng thống kê corpus mẫu.
- BGE-M3: so sánh batch với từng phần tử; đối chiếu điểm từ embedding đã lưu.
- ColQwen2.5: so sánh batch với cấu hình tham chiếu nhỏ; đối chiếu MaxSim từ embedding đã lưu.
- Khóa dung sai trước run, ghi max absolute/relative error và kết quả từng phép kiểm tra.

## 6. Đo và giới hạn tài nguyên

Đo riêng tải/download model, load model, encoding và scoring; phân biệt cold start
với xử lý sau khi đã load. Đồng bộ CUDA tại điểm đo GPU. Ghi peak RAM/VRAM,
kích thước embedding/cache và tổng thời gian.

Cần phân biệt tài nguyên cấp phát, timeout thực thi và ngưỡng kiểm tra sau đo.
Giới hạn mẫu phải được kiểm tra trước khi khởi chạy. Lỗi/OOM/timeout phải giữ log,
trạng thái kênh và cấu hình; lần chạy lại dùng run ID mới và liên kết run trước.

## 7. Bằng chứng và tiêu chí hoàn thành

Mỗi run lưu resolved config, source commit và hash cả code chưa commit nếu có,
lệnh chạy, môi trường, phần cứng, input IDs/hashes, outputs, resource metrics,
parity checks, lỗi và summary tại `results/m2.2/<run-id>/`.

M2.2 chỉ ghi PASS khi có run thật của đủ ba kênh trên cùng mẫu, dùng đúng các
revision đã khóa, đạt kiểm tra tính đúng/parity và giới hạn tài nguyên đã đặt.
Kênh chưa chạy ghi `NOT_RUN`; run lỗi ghi `FAIL` cùng nguyên nhân. Trước khi đủ
bằng chứng, trạng thái milestone là chưa hoàn thành.

## 8. Quyết định triển khai ngày 2026-10-17 — Trang không phát hiện chữ

Run thật có một trang ảnh chụp, native text rỗng và OCR hoàn thành nhưng không
trả về từ nào. M2.2 giữ trang trong danh sách chung, lưu text rỗng với trạng thái
`NO_TEXT_DETECTED`, `M23_REVIEW_PENDING`. Đây là kiểm tra đường đi của đầu vào
không có chữ; không khẳng định OCR đã nhận diện đầy đủ nội dung.
Ngưỡng OCR vẫn giữ nguyên. OCR exception/timeout hoặc OCR có từ nhưng không đạt
chất lượng vẫn ghi lỗi và làm prepare FAIL. Báo cáo phải nêu số trang no-text;
nghiệm thu chất lượng OCR thuộc M2.3.

## 9. Cấu hình smoke đã chọn

Nguồn cấu hình hiệu lực: [retriever_smoke.toml](../../../configs/m2.2/retriever_smoke.toml).

| Hạng mục | Giá trị |
|---|---|
| Visual adapter và processor/tokenizer | `vidore/colqwen2.5-v0.2@dcbe8d9cede518bce830488364ba0e40c873645b` |
| Visual base | `vidore/colqwen2.5-base@92908120384b7a2110c5beda3ab29cbdb2c08e49` |
| Dense và tokenizer | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181` |
| Mẫu | 4 validation queries, 16 pages, seed 2026, hash order, không chọn theo qrels |
| BM25 | Unicode word/lowercase, k1=1.5, b=0.75 |
| Dense | float32, normalized embeddings, max length 8192, batch 2 |
| Visual | float32 sau lượt hiệu chỉnh bfloat16, SDPA, batch 2, query batch 2, scoring batch 4 |
| Visual preprocessing | 150 DPI; max 200704 pixels = 256 visual tokens; min 3136 pixels |
| Query visual | `Query: ` + query + 10 augmentation tokens, tối đa 256 tokens |
| Môi trường | Python 3.11, PyTorch 2.7.1, transformers 4.53.3, colpali-engine 0.3.12; toàn bộ pins trong lock |
| Modal | Một A10G mỗi GPU stage, 4 CPU, 32768 MiB RAM, retries=0 |
| Giới hạn | 1800 s/stage; peak process RSS ≤32768 MiB, reserved VRAM ≤22528 MiB; artifacts ≤512 MiB |
| Parity | BM25 atol 1e-12; dense atol/rtol 1e-5; visual score atol 0.25/rtol 0.005; visual embedding atol 0.02/rtol 0.05 |

Các dung sai trên được đặt trước lượt chạy bfloat16 đầu tiên và giữ nguyên khi chuyển float32. Không thay ngưỡng để
chuyển một kết quả parity thất bại thành PASS. Batch-reference chạy toàn bộ mẫu
với batch 1 trên cùng model đã load; MaxSim được tính thêm bằng tham chiếu float32 độc lập.

Tham khảo triển khai: [model card ColQwen2.5](https://huggingface.co/vidore/colqwen2.5-v0.2),
[colpali-engine 0.3.12](https://pypi.org/project/colpali-engine/0.3.12/),
[Modal GPU](https://modal.com/docs/guide/gpu), [Modal timeout](https://modal.com/docs/guide/timeouts).
Model/base/tokenizer/processor được pin bằng full commit và hash file tải thật;
không dùng nhãn `main` trong run.

Quyết định precision: run bfloat16 `20261017T041005Z-A01` đạt score parity nhưng
không đạt token-embedding parity; thử float32 với cùng mẫu, model revision và caps.
Kết quả từng lựa chọn phải được giữ trong nhật ký/báo cáo; không tuyên bố bfloat16
đã đạt kiểm chứng theo tiêu chí M2.2.

[Kế hoạch](../plans/2026-10-17-m22-retriever-smoke.md) ·
[Nhật ký](../progress/2026-10-17-m22-retriever-smoke.md) ·
[Báo cáo](../reports/2026-10-17-m22-retriever-smoke.md)
