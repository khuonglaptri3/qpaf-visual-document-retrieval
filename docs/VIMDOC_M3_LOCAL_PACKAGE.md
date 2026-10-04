# ViMDoc M3 — package chuẩn bị local v1

Ngày: 2026-09-10. Phạm vi được người dùng đồng ý: chỉ chuẩn bị local cho ViMDoc score extraction và matched QARF/QPAF M3; không Modal/GPU, không training.

## Kết luận của package

Package này đóng băng **các byte để review**, không tuyên bố mọi quyết định khoa học đã được thông qua. Trạng thái: `PREPARED_FOR_LOCAL_REVIEW_NOT_EXECUTION`. M3 chưa đạt execution readiness. Không có trainer, remote launcher, score cache thật mới hoặc kết quả learned QPAF trong package này. Không sửa hay mở lại các phê duyệt ViDoSeek/P1-02/P1-03 trước đây.

Các file chính:

- `configs/vimdoc_m3_local_v1.json`: dữ liệu/model pins, hợp đồng score, matched config, đề xuất split/hyperparameter và toàn bộ execution flags đóng.
- `scripts/prepare_vimdoc_m3.py`: preflight chỉ đọc; kiểm tra manifest/hash, sample và xuất hai resolved config dùng chung mọi trường ngoài `gate_granularity`. Có reference helpers cho candidate union, normalization và document layout trên dữ liệu được cung cấp; không gọi retriever.
- `tests/test_vimdoc_m3_preparation.py`: test synthetic và metadata local; không có optimizer step.
- `artifacts/vimdoc_m3_local_v1/package_manifest.json`: inventory/hash chính xác, bao gồm method core hiện tại và dependency contracts. Đây là checksum snapshot, không phải chữ ký hay quyền chạy.
- `artifacts/vimdoc_m3_local_v1/local_verification.json`: kết quả kiểm tra thực tế của lần chuẩn bị này; không phải scientific run manifest.

## Phần đã có bằng chứng và phần chưa có

Receipt local của lần materialization cũ ghi nhận ViMDoc revision `25657f1fe0358f49147148ca89e231291ba42788`, 10.904 query, 76.347 image assets, 70.080 page stems và 1.247 HEAVEN documents. Sample 2.000 query đã được chọn chỉ bằng query ID, với hash `0fc5a2f0de3eb1afa0b14e82e9f143dd57743864ac9468b5a112defb96a3482a`. Preflight kiểm tra lại byte receipt và hash danh sách này, **không** đọc lại archive/Parquet trên Modal. Trạng thái remote hiện tại chưa được kiểm tra.

Ba vấn đề dữ liệu không được giải quyết bằng suy đoán:

1. OCR/page-identity semantics đã được đóng băng trong `configs/vimdoc_ocr_page_identity_v1.json` và giải thích tại `docs/VIMDOC_OCR_PAGE_IDENTITY_SPEC.md`. Dùng HEAVEN-aligned Tesseract plain text chung cho BM25/BGE-M3, không gọi là Markdown; engine/options/version/schema/hash/failure policy đã rõ. Chưa build runtime hoặc tạo text payload.
2. Có 6.267 asset dư so với số page stem duy nhất. Policy đã chốt: cùng `page_id` và cùng content hash thì collapse thành aliases với canonical UTF-8-smallest path; khác content thì `BLOCK`, không ưu tiên extension/rename/drop. Live archive chưa được content-hash audit nên chưa biết collision thuộc loại nào.
3. Sample 2.000 query chưa có train/validation split riêng. Package đề xuất 1.600/400, sắp xếp SHA-256 của `vimdoc_m3_local_v1:dev_split:20260820:<query_id>` rồi query ID. Exact IDs tái tạo được bằng lệnh ở dưới. Split này **chưa được áp dụng để train**, không đọc nhãn, không đổi theo seed hoặc method.

## Hợp đồng score extraction cho adapter tương lai

Adapter phải chấm toàn bộ corpus đủ để lấy top-200 theo từng kênh BM25, BGE-M3 và ColQwen2.5. Hợp ba danh sách, tối đa 600 trang/query; tie theo page ID tăng dần. Sau đó có đủ cả ba raw scores cho mọi trang trong union, không dùng số 0 để lấp score thiếu. Candidate top lists và union phải được lưu/hash **trước** khi mở qrels để kiểm tra coverage. Không thay ColQwen candidate bằng DSE như runner lịch sử, không đổi depth thành `(200,100,100)`.

Normalize từng kênh trên chính union của query: `(s-min)/(max-min)` nếu range > `1e-15`, ngược lại 0. Raw/cache scores float64 hữu hạn; cast model inputs float32 có kiểm tra sai số. Hợp đồng page-score row: `(dataset, query_id, page_id, document_id, bm25, dense, visual)`; key duy nhất `(dataset, query_id, page_id)`, provenance gắn qua manifest chứ không suy ra từ tên file. Rows không chứa relevance. Raw scores, normalized scores và candidate audit là các artifact riêng có hash/count/schema.

Qrels là bảng nhị phân document riêng `(query_id, document_id, relevance=1)`. Bỏ duy nhất đoạn cuối sau `_` khi ánh xạ page/raw ground-truth ID thành document. QPAF vẫn fusion ở trang; **sau fusion** lấy max theo document. Sắp trang tăng dần trước khi gọi method core để gradient tại tie đi về đúng trang. Không lặp document labels lên pages. Khi tính nDCG, IDCG phải dùng đầy đủ relevant documents của query, kể cả document ngoài candidate union.

Coverage audit sau candidate freeze: báo per-query relevant-document recall và macro mean; macro recall >= 0.95, không query nào thiếu mọi positive candidate. Không drop query để làm đẹp coverage. Mỗi training query có ít nhất 2 candidate pages; padding phải dùng score/features/relevance bằng 0, mask bool, group index int64 hợp lệ. Kiểm tra duplicate, missing/extra query IDs, NaN/Inf và sai mapping phải fail, không sửa tự động.

Future extraction bundle phải có: canonical asset/text/query manifests; three channel top lists; candidate audit; raw/normalized score tables; separate document qrels; coverage report; resolved config; model/runtime/source hashes; attempt/failure marker; final manifest và success marker chỉ xuất sau semantic/hash/coverage verification. Cần hash raw archive và Parquet thật ở runtime, không coi hash trong receipt là thay thế cho kiểm tra payload.

## Matched QARF/QPAF và các đề xuất chưa được thông qua

Hai resolved config chỉ khác `gate_granularity`: QARF lấy masked-mean features theo query; QPAF lấy features từng page. Candidate/cache/split/features/loss/budget/seed đều phải giống nhau. Cùng linear 13→3, 42 tham số, zero initialization, tau=1, batch32, AdamW và gradient clip1.0 theo method contract hiện tại.

Để có bản review cụ thể, package **đề xuất**, chưa chọn bằng kết quả: LR `1e-3`, weight decay `0.01`, betas `(0.9,0.999)`, eps `1e-8`, tối đa50 epochs, patience5, min-delta0, không scheduler, best validation nDCG@10, tie chọn epoch sớm nhất. Đây là một cấu hình đơn giản chung cho cả hai method, không phải hyperparameter tối ưu đã được chứng minh. Không có search/tuning được chạy. Ba seed giữ nguyên `20260820/21/22`; cùng query order theo seed và cùng trần compute, không chọn seed tốt nhất.

Primary proposal dùng float32 và tắt autocast. Local method tests dùng PyTorch CPU khác phiên bản remote2.7.1 nên không chứng minh CUDA parity. Trainer/collator tương lai phải enforce dtype, finite padding, integer groups, stable page order và fp32 softmax/loss; method core riêng lẻ không tự bảo đảm hết các điều kiện này. Chưa có performance/calibration evidence cho ViMDoc. L4 là đề xuất learned GPU theo environment contract; GPU/batch OCR và extraction, image hash, timeout, cost cap chưa chốt. Các giá trị đó để null; không mượn phê duyệt/timing ViDoSeek.

## Đánh giá để quyết định tiếp tục hay đổi hướng

Validation dùng chọn checkpoint chỉ cho **tín hiệu development**, không tự trở thành untouched confirmation. Package đề xuất giữ phần còn lại 8.904 query ViMDoc ngoài toàn bộ 2.000 development IDs làm confirmation query-disjoint sau khi đóng băng protocol; danh sách/hash phần còn lại chưa có tại local và đề xuất chưa được thông qua. Query-disjoint không chứng minh document-disjoint. Báo cáo toàn bộ ViMDoc nếu có bao gồm query đã train phải ghi riêng, không gọi là held-out. ViDoRe V3 vẫn sealed external validation, không mở nhãn để thiết kế M3.

Trước execution cần chốt baseline roster: tối thiểu ba single channels, uniform fusion và matched learned QARF; đề xuất thêm deployable Global/RRF với lựa chọn tham số chỉ trên training partition. Relevance-informed oracle không được đưa vào nhóm deployable. Không chọn baseline hay rule sau khi thấy confirmation scores.

Giữ gate hiện tại: mean QPAF−QARF nDCG@10 >=0.01 qua ba seed, query-bootstrap10.000 lần có CI95 lower >0; đồng thời vượt strongest deployable baseline trong protocol. Ghép cặp cùng query/seed, lấy seed-average delta mỗi query trước bootstrap; không coi các seed của cùng query là mẫu độc lập. M4 còn yêu cầu validation gain >=0.01 so với strongest deployable baseline. Threshold không được hạ sau khi thấy kết quả; frozen oracle threshold0.02 trong `preregistered.yaml` là protocol khác và không bị sửa.

Gate vận hành: không NaN/Inf, fusion CUDA peak <1.50 GiB, median added fusion latency <=10ms/query, checkpoint reload tái hiện fused scores trong absolute tolerance1e-7. Cần định nghĩa benchmark trước chạy: 20 warm-up, ít nhất1.000 measured queries, synchronized CUDA timing, báo riêng feature-preprocessing và gate/aggregation, không trộn retrieval extraction. Với validation400, không được gọi 400 mẫu là đạt yêu cầu1.000; phải chốt workload latency label-free riêng trước execution.

Checkpoint/ledger/telemetry mới là **hợp đồng cần triển khai**: unique fresh run ID, source commit cùng dirty-diff/source hashes, resolved config, cache/split hashes, seed, runtime image, actual GPU, Modal run ID, peak/latency samples, per-query predictions, history và reload comparison. Attempt tạo một lần, failure giữ nguyên, không overwrite/retry tự động. Resume/retry cần contract và approval riêng; package này không có command hay quota để chạy.

## Lệnh local an toàn

```powershell
C:\Python313\python.exe scripts/prepare_vimdoc_m3.py
C:\Python313\python.exe scripts/prepare_vimdoc_m3.py --include-proposed-ids
$env:PYTHONPATH = 'src'
C:\Python313\python.exe -m pytest tests/test_vimdoc_m3_preparation.py tests/test_features.py tests/test_models.py tests/test_losses.py tests/test_gradients.py -q
```

Preflight exit0 nghĩa là **local package integrity PASS**, luôn kèm `ready_for_execution=false` và `m3_execution_readiness=BLOCKED`. Source/config drift làm exit2. Không có cờ `--train`, `--extract`, `--modal`, `--gpu` hay `--approve`. Test fixtures chỉ dùng synthetic data/temp directories; script preflight không ghi file. Đổi file nằm trong manifest cần version/review snapshot mới, không refresh checksum để che drift.

Bước OCR/page-identity specification và local preparation của content-audit package đã hoàn tất; xem `docs/VIMDOC_ARCHIVE_CONTENT_AUDIT_EXECUTION_REVIEW.md`. Content-hash audit archive thật vẫn chưa chạy và cần approval riêng. Sau audit PASS mới chuẩn bị OCR runtime/resource contract. Song song trong phạm vi local có thể review split/baseline và hoàn thiện adapter/runner contract tests. Hoàn tất bản chuẩn bị hiện tại không phải lý do kết luận QPAF đã cải thiện.
