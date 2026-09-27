# Dataset and Split Policy — Frozen v1

> **Trạng thái:** `FROZEN_M1_5_V1_SPLIT_ARTIFACTS_PENDING`  
> **Protocol:** `QPAF-M1.5-v1`  
> **Execution:** Closed

## 1. Dataset roles

| Dataset | Immutable identity | Vai trò | Quy tắc sử dụng |
|---|---|---|---|
| ViDoSeek | `Qiuchen-Wang/ViDoSeek` @ `e91a92ba5f38690696c7e66be5c5474b54c6e791` | Discovery và bounded diagnostic | Không dùng làm learned confirmation; không mở broad oracle sweep mới |
| ViMDoc | `kaistdata/ViMDoc` @ `25657f1fe0358f49147148ca89e231291ba42788` | Primary learned development và untouched confirmation | Page-level fusion, document-level evaluation theo HEAVEN mapping |
| ViDoRe V3 Finance EN | `vidore/vidore_v3_finance_en` @ `7f432c176d82e27546501ad8064a713ac3071809` | Optional sealed external validation | Không mở labels để chọn architecture/config/baseline/checkpoint |

ViDoSeek oracle results chỉ là upper-bound discovery evidence. ViMDoc là dataset duy
nhất được dùng để support core learned-method claim. ViDoRe V3 chỉ support external
generalization nếu sealed protocol được giữ nguyên.

## 2. ViMDoc identity và evaluation unit

- Tổng query đã ghi nhận: `10,904`.
- Page asset lịch sử: `76,347`; unique extension-stripped page IDs: `70,080`.
- HEAVEN document IDs: `1,247`.
- Archive SHA-256 lịch sử:
  `de569c8d4d499b8fac84d4d03a0ddb59054e30351dcb7b1e6da3d1945d2d2c71`.
- Query parquet SHA-256:
  `7ccac6c8715cc338c041e9276583b9dbd79a818131a9b13a5abf4b9ced73bcc0`.
- Binary document-qrels SHA-256:
  `3643e70c02b777b45a88a8f1489d88db1d53255ef9dea5caf3796b64218a70a0`.
- Map page → document bằng cách bỏ đúng segment cuối sau dấu `_`.
- Document score là max fused page score; page ties theo ascending page ID.
- Document qrels lưu riêng, không lặp label xuống page.

Historical receipts là identity evidence, không phải fresh live-readiness evidence.

## 3. Development universe

Development universe là exact 2.000 query IDs đã được chọn label-free từ toàn bộ
10.904 IDs bằng:

1. chỉ đọc query ID;
2. tính `SHA256(UTF8("20260820:<query_id>"))`;
3. sort theo digest bytes, tie-break theo query ID;
4. lấy 2.000 ID đầu.

Không được đọc query text, `doc_ids`, qrels, relevance count, document length hoặc
retrieval score trong bước chọn này. Historical selected-ID hash là
`0fc5a2f0de3eb1afa0b14e82e9f143dd57743864ac9468b5a112defb96a3482a`.

## 4. Frozen train/validation split

Từ đúng 2.000 development IDs ở trên:

1. namespace cố định: `vimdoc_m3_local_v1:dev_split:20260820`;
2. với mỗi ID `q`, tính
   `SHA256(UTF8("vimdoc_m3_local_v1:dev_split:20260820:<q>"))`;
3. sort theo `(digest bytes, query_id)`;
4. 1.600 ID đầu là `train`;
5. 400 ID còn lại là `validation`.

Hash cho mỗi ID list phải là SHA-256 của UTF-8 text gồm IDs theo frozen order, mỗi ID
một dòng và có newline cuối. Cùng split được dùng cho mọi method và seed.

Exact train/validation files và hashes hiện chưa tồn tại trong protocol package.
Algorithm, namespace, counts và serialization rule ở trên đã frozen; việc materialize
ID files là downstream activation evidence, không được thay đổi semantics đã khóa.

`split_id` và `split_sha256` trong M1.7 registry giữ `PENDING` cho đến khi exact
train/validation/confirmation manifests được tạo, kiểm tra và freeze. Không được điền
hash của source parquet thay cho hash của split assignment.

## 5. Untouched confirmation split

`confirmation` gồm đúng 8.904 ViMDoc query IDs còn lại sau khi loại toàn bộ 2.000
development IDs. Confirmation phải:

- query-disjoint với train và validation;
- không được dùng để chọn architecture, features, normalization, candidates,
  hyperparameters, baseline roster hoặc checkpoint;
- chỉ được mở sau khi method, checkpoint-selection rule và strongest-baseline rule đã
  freeze;
- được đánh giá một lần cho claim-bearing protocol; invalid technical run phải có
  independent invalidation record trước bất kỳ fresh attempt nào.

Query-disjoint không đồng nghĩa document-disjoint. Phải đo và báo cáo document overlap
giữa train/validation/confirmation; overlap không tự động đổi split nhưng là limitation
bắt buộc.

## 6. Sealed external split

ViDoRe V3 Finance EN giữ nguyên official test split và graded page qrels. Không được
fit/tune bằng external labels. Nếu external score cache chưa có hoặc schedule không
cho phép, ghi `NOT_RUN` với lý do; không thay thế bằng một dataset khác.

## 7. Leakage và integrity checks bắt buộc

- Exact set sizes: 1.600 / 400 / 8.904; union = 10.904 unique IDs.
- Pairwise overlap của ba split bằng 0.
- Development-universe hash khớp historical 2.000-ID hash.
- Confirmation đúng bằng full ID set trừ development set.
- Split generation không import/read qrels, document IDs, scores hoặc query text.
- Mọi split file có SHA-256, source dataset revision, creation command và verifier.
- Candidate/cache rows map đúng split; không có orphan hoặc duplicate query ID.
- Mọi result-bearing registry event ghi exact `split_id` và `split_sha256`; historical
  evidence chưa recover được dùng `UNKNOWN` kèm issue, không đoán giá trị.

## 8. Activation blockers after freeze

| Blocker | Điều kiện đóng |
|---|---|
| Train ID hash đang `null` trong prepared configs | Tạo exact `train_ids` artifact và hash; independent replay khớp |
| Validation ID hash đang `null` | Tạo exact `validation_ids` artifact và hash; independent replay khớp |
| Confirmation ID hash chưa có | Tạo exact `confirmation_ids` artifact và hash |
| Chưa có leakage/document-overlap report | Zero query overlap; document overlap được định lượng |
| M1.4 inventory chưa có | Cross-check dataset paths, revisions và hashes với M1.4 trước G1 |

Protocol đã frozen ở lớp policy. Không optimizer step nào được phép trước khi các
activation blocker này được đóng, exact artifacts được hash và một execution package
riêng được authorization.
