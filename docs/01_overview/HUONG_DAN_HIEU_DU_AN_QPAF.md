# Hướng dẫn hiểu dự án QPAF và các giai đoạn thực nghiệm

> Ảnh chụp trạng thái: 2026-08-31, sau khi bundle P1-02R được import và kiểm tra integrity ở local.
>
> Mục tiêu của tài liệu này là giúp đọc **ý nghĩa** của từng giai đoạn, không chỉ liệt kê lệnh. Các thuật ngữ tiếng Anh được giữ lại vì chúng xuất hiện trong mã nguồn, cấu hình và artifact.

## 0. Nếu chỉ có 5 phút, hãy đọc phần này

Đề tài đang kiểm tra một câu hỏi hẹp:

> Khi tìm trang tài liệu cho một câu hỏi, việc thay đổi trọng số của BM25, dense retrieval và visual retrieval **cho từng cặp câu hỏi–trang** có tốt hơn việc dùng một bộ trọng số chung hay không?

Tên của phương pháp chi tiết nhất là **Query-Page-Adaptive Fusion (QPAF)**.

Ta chưa được phép mặc định rằng QPAF tốt hơn. Quy trình được thiết kế để bác bỏ ý tưởng này sớm nếu bằng chứng không đủ:

```text
Chuẩn bị dữ liệu và score đáng tin cậy
                 |
                 v
Đo oracle headroom rẻ, chưa train mô hình
                 |
       Có đủ lợi ích không?
          /             \
        Không            Có
         |                |
 Chọn cách đơn giản   Mới triển khai và train QPAF
                          |
                          v
                Kiểm tra nhiều seed, ablation,
                external validation và tái lập
```

Vị trí hiện tại:

- Phase 0 đã tạo nền tảng và score bundle hợp lệ.
- P1-01 đã làm cứng contract về score, normalization và metric.
- P1-02 bị `BLOCKED` vì candidate pool bỏ sót trang đúng của một query.
- P1-02R là protocol hậu kiểm riêng, đổi candidate pool thành **toàn bộ 5.385 trang cho mỗi query**.
- Bundle P1-02R đã được import và kiểm tra độc lập ở local: byte hash, logical-content hash, schema, row count, unique key, finite score, normalization, branch rank/tie-break, coverage và provenance đều `PASS`. Đây là **verified post-hoc recovery artifact**, chưa phải oracle/QPAF result.
- P1-03, Phase 1 gate và toàn bộ Phase 2 vẫn đang bị khóa.

Lần chạy Modal vừa rồi **không phải training**. Nó chỉ tính và lưu score cho 1.142 query × 5.385 trang = **6.149.670 cặp query–page**.

## 1. Bài toán từ đầu: Visual RAG đang làm gì?

Một hệ thống RAG thường có hai phần lớn:

1. **Retrieval:** tìm một số trang có khả năng chứa câu trả lời.
2. **Generation:** đưa các trang đó cho mô hình sinh câu trả lời.

Đề tài hiện tại tập trung vào phần **retrieval**, chưa đánh giá chất lượng câu trả lời cuối của LLM.

Với tài liệu giàu thông tin trực quan, một trang có thể liên quan vì nhiều lý do:

- chứa đúng từ khóa trong OCR;
- có nội dung ngữ nghĩa gần với câu hỏi dù không trùng từ;
- có bảng, biểu đồ, bố cục hoặc tín hiệu hình ảnh phù hợp.

Vì vậy, dự án dùng nhiều retriever thay vì tin tuyệt đối vào một retriever.

### 1.1 Ba kênh thực sự được QPAF dung hợp

| Kênh | Model/cách tính hiện tại | Hiểu đơn giản | Điểm mạnh thường gặp |
|---|---|---|---|
| `bm25_score` | BM25 | So khớp từ khóa | Từ chuyên môn, tên riêng, con số, chuỗi chính xác |
| `dense_score` | BGE-M3 | So khớp ngữ nghĩa văn bản | Diễn đạt khác từ nhưng gần ý |
| `visual_score` | ColQwen2.5 | So khớp query với ảnh trang | Bố cục, bảng, biểu đồ và nội dung trực quan |

QPAF tính một điểm cuối dạng:

$$
S(q,p)=w_B(q,p)\hat{s}_B(q,p)
      +w_D(q,p)\hat{s}_D(q,p)
      +w_V(q,p)\hat{s}_V(q,p),
$$

trong đó ba trọng số không âm và có tổng bằng 1.

### 1.2 DSE nằm ở đâu? Tại sao thấy bốn score nhưng lại nói ba kênh?

Các file extraction còn có `stage1_score`, được tạo bởi DSE. Trong protocol hiện tại:

- DSE là nhánh Stage 1/candidate-generation hỗ trợ chọn candidate;
- ba cột QPAF đưa vào phép fusion là `bm25_score`, `dense_score`, `visual_score`;
- `stage1_score` vẫn được giữ để audit provenance, thứ hạng nhánh và tương thích với phần HEAVEN.

Vì vậy:

> **Bốn score được lưu không có nghĩa QPAF đang học bốn trọng số. QPAF hiện tại vẫn fusion ba kênh.**

### 1.3 Tại sao phải cache score?

Chạy BGE-M3, DSE và đặc biệt ColQwen2.5 trên hàng triệu cặp query–page tốn GPU và thời gian. Nhưng thử các bộ trọng số fusion sau đó khá nhẹ.

Ta tách công việc thành hai lớp:

```text
LỚP ĐẮT, CHẠY ÍT LẦN TRÊN MODAL
query + corpus pages
       |
       +--> BM25 scores
       +--> BGE-M3 scores
       +--> DSE Stage-1 scores
       +--> ColQwen2.5 visual scores
                         |
                         v
                  versioned score cache

LỚP RẺ, CÓ THỂ PHÂN TÍCH TỪ CACHE
score cache
   |
   +--> normalization
   +--> Global/QARF/CARF/QPAF oracle
   +--> bootstrap và decision gate
   +--> sau này: train learned fusion trên Modal
```

Đây là lý do “Modal đang chạy lâu” không đồng nghĩa “QPAF đang train lâu”. Phần đắt hiện tại là **offline retriever score extraction**.

## 2. Fusion là gì và bốn mức Global–QARF–CARF–QPAF khác nhau ra sao?

Các retriever có thang điểm khác nhau, nên score được min–max normalize theo từng query và từng nhánh trước khi fusion. Sau đó ta chọn mức chi tiết của trọng số.

| Mức | Bộ trọng số | Ví dụ trực giác | Độ phức tạp |
|---|---|---|---|
| Global | Một bộ cho toàn dataset | Luôn dùng 20% BM25, 50% dense, 30% visual | Thấp nhất |
| QARF | Một bộ cho mỗi query | Query về số liệu ưu tiên BM25; query về biểu đồ ưu tiên visual | Thấp |
| CARF | Một bộ cho mỗi cụm candidate trong một query | Nhóm trang văn bản và nhóm trang biểu đồ nhận trọng số khác nhau | Trung gian |
| QPAF | Một bộ cho mỗi cặp query–page | Trong cùng query, mỗi trang có thể được fusion khác nhau | Cao nhất |

Các ký hiệu trong proposal:

- Global: $w_m$;
- QARF: $w_m(q)$;
- CARF: $w_m(q,c)$;
- QPAF: $w_m(q,p)$.

Nhiều quyền chọn hơn làm oracle QPAF về lý thuyết không thấp hơn QARF, và QARF không thấp hơn Global. Thứ tự này tự nó **không phải đóng góp nghiên cứu**. Điều cần đo là:

- mức tăng lớn bao nhiêu;
- có xuất hiện trên nhiều query hay chỉ vài ngoại lệ;
- confidence interval có loại được mức tăng bằng 0 hay không;
- learned model có học được lợi ích đó mà không nhìn qrels khi inference hay không.

## 3. Oracle không phải learned model

Đây là phân biệt quan trọng nhất của dự án.

### 3.1 Oracle study

Oracle được phép dùng qrels để nhìn lại và chọn bộ trọng số tốt nhất trong một lưới hữu hạn. Nó trả lời:

> “Nếu có một bộ chọn hoàn hảo trong phạm vi các trọng số đã đăng ký trước, mức thích ứng này có bao nhiêu headroom?”

Oracle là **trần trên chẩn đoán**, không thể triển khai vì lúc inference thật ta không biết trang nào đúng.

### 3.2 Learned fusion

Learned QARF/QPAF dùng train split để học cách dự đoán trọng số từ 13 đặc trưng không nhãn như score, rank, margin, top-1/top-2 gap và rank disagreement.

Khi validation/test hoặc inference:

- không được đưa qrels vào feature;
- không được đưa oracle profile vào model;
- không được chọn checkpoint dựa trên test;
- phải so sánh dưới cùng candidate pool, score cache, split và budget.

Chỉ kết quả learned model vượt baseline dưới protocol giống nhau mới có thể hỗ trợ tuyên bố “phương pháp QPAF hoạt động”.

### 3.3 W7 và W66 là gì?

Đây là hai lưới trọng số cho oracle:

- **W7:** 7 lựa chọn đơn giản — ba kênh đơn, ba cặp 50/50, và trung bình đều 1/3–1/3–1/3.
- **W66:** 66 bộ trọng số trên simplex với bước 0,1.

W7 là kiểm tra rẻ và dễ diễn giải. W66 là sensitivity check chi tiết hơn. Ta không mở rộng lưới tùy ý sau khi nhìn kết quả, vì như vậy dễ tạo post-hoc bias.

## 4. Từ điển các khái niệm cần nhớ

### Query, page và corpus

- **Query:** câu hỏi cần tìm tài liệu.
- **Page:** một trang ứng viên.
- **Corpus:** toàn bộ tập trang được phép tìm kiếm.

ViDoSeek hiện có 1.142 query và 5.385 trang trong corpus đã đóng băng.

### Qrels và relevance

**Qrels** là ground truth: query nào liên quan tới page/document nào, với relevance bao nhiêu.

Qrels được dùng cho:

- audit coverage sau khi candidate pool đã cố định;
- tính metric;
- tạo target trên train split;
- oracle analysis.

Qrels không được dùng cho:

- thêm trang đúng vào candidate pool;
- chọn candidate depth sau khi nhìn rank của trang đúng;
- normalization;
- feature/clustering đầu vào;
- inference của learned model.

### Candidate pool

Thay vì chấm mọi trang bằng mọi model đắt tiền, hệ thống thường lấy union top-$K$ từ vài nhánh rẻ hơn. Tập union đó là **candidate pool**.

Ví dụ protocol P1-02 ban đầu:

```text
DSE top 200  UNION  BM25 top 100  UNION  BGE-M3 top 100
```

Sau một lần mở rộng đã đóng băng:

```text
DSE top 300  UNION  BM25 top 200  UNION  BGE-M3 top 200
```

Union có thể nhỏ hơn tổng các depth vì cùng một trang xuất hiện ở nhiều nhánh.

### Coverage

Coverage trả lời:

> Trong các cặp relevant theo qrels, có bao nhiêu cặp nằm trong candidate pool?

Nếu trang đúng không nằm trong pool, fusion không thể “cứu” nó dù thuật toán fusion tốt đến đâu.

Dự án dùng cả hai điều kiện:

- overall relevant-pair coverage ít nhất 0,95;
- số query có **zero relevant candidate** phải bằng 0.

Điều kiện thứ hai đã làm P1-02 dừng dù overall coverage là 0,999124. Đây không phải mâu thuẫn: trung bình rất cao vẫn có thể che giấu một query hoàn toàn không có đáp án trong pool.

### nDCG@10

Metric chính đánh giá chất lượng thứ hạng trong top 10. Trang relevant đứng càng cao thì điểm càng tốt; relevance grade cao nhận gain lớn hơn.

Các metric phụ gồm Recall@1, Recall@3 và MRR@10.

### Bootstrap confidence interval

Ta resample query nhiều lần để ước lượng độ bất định của mean gain. Nếu cận dưới 95% CI vẫn lớn hơn 0, bằng chứng ổn định hơn việc chỉ nhìn mean dương.

### Seed

Seed cố định nguồn ngẫu nhiên. Phase 3 chạy ba seed 20260820–20260822 để tránh chọn một lần chạy may mắn.

### Protocol, frozen và post-hoc

- **Protocol:** luật thực nghiệm đã khai báo: dataset, model revision, candidate rule, metric, threshold, seed.
- **Frozen:** không được sửa im lặng sau khi nhìn kết quả.
- **Post-hoc:** thay đổi được đề xuất sau khi đã thấy vấn đề/kết quả; phải mang version và nhãn riêng.

P1-02R là post-hoc protocol. Nó không được viết lại lịch sử để biến P1-02 thành `PASS`.

### Manifest, SHA-256 và success marker

- **Manifest:** “phiếu kê khai” một run — code commit, config, model, GPU, file đầu ra, kích thước và hash.
- **SHA-256:** dấu vân tay của file; đổi một byte sẽ đổi hash.
- **`_EXTRACTION_SUCCESS.json`:** marker cho extraction hoàn chỉnh.
- **`_SUCCESS.json`:** marker của bundle/finalization ở những task dùng contract này.

Một file tồn tại chưa đủ để chứng minh run hợp lệ. Cần marker, manifest, hash, schema, row count và gate cùng khớp.

### PASS, BLOCKED và KILLED

- **PASS:** task tạo đúng output và mọi kiểm tra bắt buộc đều qua.
- **BLOCKED:** dependency hoặc đầu vào cần thiết không sẵn sàng/không đạt; trạng thái đã được báo cáo.
- **KILLED:** stop condition khoa học hoặc kỹ thuật đã kích hoạt; không được lách để tiếp tục cùng research path.

`status: complete` trong receipt của một Modal function chỉ có nghĩa function đã chạy tới cuối. Nó chưa tự động tương đương task `PASS`.

## 5. Vai trò của ba dataset

| Dataset | Vai trò | Granularity | Mục đích |
|---|---|---|---|
| ViDoSeek | Discovery | Page-level | Tìm nhanh xem ý tưởng có headroom hay không |
| ViMDoc | Confirmation | QPAF tính score theo page, nhưng loss/metric ở HEAVEN document-level | Xác nhận trên protocol lớn và gần mục tiêu hơn |
| ViDoRe V3 | Sealed external validation | Page-level | Kiểm tra generalization ngoài tập confirmation |

Trên ViMDoc, nhiều page thuộc cùng một document. QPAF vẫn cho điểm từng page, sau đó lấy page score lớn nhất làm document score với tie-break ổn định rồi mới tính metric trên document qrels.

ViDoRe V3 hiện là benchmark external tiếng Anh/Pháp. Nó **không chứng minh hiệu năng retrieval tiếng Việt**. Dataset tiếng Việt chỉ có thể thêm sau khi có retrieval corpus và qrels hợp lệ; hiện không phải dependency thực thi.

## 6. Tại sao có “Pha A–E” và lại có “Phase 0–3”?

Repository có hai cách trình bày:

1. `DE_XUAT_NGHIEN_CUU_QPAF.md` dùng **Pha A–E** để kể câu chuyện nghiên cứu ở mức cao.
2. `Tasks.md` dùng **Phase 0–3** và task ID cụ thể để kiểm soát thực thi.

Chúng gần tương ứng như sau:

| Proposal | Implementation DAG | Ý nghĩa |
|---|---|---|
| Pha A — dữ liệu và baseline | Phase 0 + P1-01 | Đóng băng môi trường, dữ liệu, score và metric contract |
| Pha B — complementarity và oracle | Phần chính của Phase 1 | Dùng W7/W66 để đo Global → QARF → QPAF headroom |
| Pha C — granularity | P1-03 và CARF trong P3-02 | Dùng W7/W66 trước, rồi kiểm tra query/cluster/page-level trong ablation |
| Pha D — learned fusion | Phase 2 | Implement và train learned QARF/QPAF với matched protocol |
| Pha E — xác nhận và báo cáo | Phase 3 | Nhiều seed, CARF/ablation, external validation, reproducibility package |

Khi quyết định “được phép làm gì tiếp theo”, hãy dùng `Tasks.md` làm task graph thực thi hiện tại.

## 7. Ý nghĩa chi tiết của từng implementation phase

### Phase 0 — Environment and Baseline Verification

#### Câu hỏi của phase

> Ta có chắc đang chạy đúng code, đúng dependency, đúng dataset, đúng model revision và tạo score bundle nguyên vẹn không?

#### Các task

- **P0-01:** đóng băng baseline source và hash từng file.
- **P0-02:** đóng băng local/Modal environment, GPU contract, dataset identity và model revision.
- **P0-03:** chạy lại baseline tests, import score extraction, kiểm tra hash/coverage và finalize QPAF bundle.

#### Vì sao phase này tồn tại?

Nếu baseline thay đổi, dataset revision trôi hoặc score bị hỏng, mọi so sánh phía sau không còn diễn giải được. Phase 0 không chứng minh QPAF tốt; nó chỉ chứng minh “thước đo và nguyên liệu đủ đáng tin để bắt đầu thí nghiệm”.

#### Trạng thái hiện tại

Phase 0 đã hoàn tất cho QPAF contract hiện hành và repository đã chuyển sang Phase 1. Điều này **không** có nghĩa official HEAVEN `full_score`, Stage-2 latency/FLOPs hay full-corpus Budget-Aware metrics đã tồn tại.

### Phase 1 — Minimal Viable Experiment / Cheapest Disproof

#### Câu hỏi của phase

> Trước khi implement và train QPAF, oracle có cho thấy page-level adaptation đáng để đầu tư không?

Đây là phase quan trọng nhất về tiết kiệm công sức. Nếu QPAF oracle gần như không hơn QARF, learned QPAF khó có lý do để tồn tại.

#### P1-01 — Harden contract

Kiểm tra rằng:

- ba channel có đúng nghĩa;
- normalization deterministic;
- metric reference khớp tính tay;
- qrels không lọt vào candidate generation;
- input sai bị từ chối rõ ràng.

Task này đã được ghi nhận ở commit `e5ec0e1`.

#### P1-02 — W7 oracle pilot theo protocol gốc

Mục tiêu dự kiến là chạy Global, QARF và QPAF oracle trên ViDoSeek. Tuy nhiên, pipeline dừng trước bước oracle:

- initial pool: coverage `0.9973730297723292`, ba query có zero relevant candidate;
- expanded pool: coverage `0.999124343257443`, còn một query có zero relevant candidate;
- query còn thiếu: `027dee01b7aced677eb5093c754ebad82a89015d_1`.

Vì gate yêu cầu zero-uncovered-query bằng 0, P1-02 được người dùng chấp nhận là `BLOCKED` ngày 2026-08-30.

Hệ quả:

- W7 oracle chưa chạy;
- chưa có QPAF gain;
- chưa có confidence interval hay subgroup result;
- P1-03 và Phase 2 không được mở khóa.

#### P1-02R — post-hoc all-corpus recovery protocol

P1-02R giữ nguyên dataset, preprocessing, retriever, model revision, score definition, metric và qrels boundary. Chỉ candidate membership đổi thành:

> Mỗi query nhận toàn bộ 5.385 page đã chuẩn bị, không phụ thuộc score và không dùng qrels.

Do đó:

- 1.142 query × 5.385 page = 6.149.670 candidate pair;
- CPU membership audit cho coverage 1,0 và zero uncovered query;
- L4 calibration trên 8 query × 512 page mất 588,160 giây, peak allocation 7,719 GiB;
- projection trước run là khoảng 2,183 L4-hours;
- một human-run invocation với query chunk 8, page chunk 512 và visual score batch 128 đã hoàn thành; invocation duy nhất này đã được tiêu thụ và execution guard hiện đóng.

P1-02R không tự động thay thế P1-02. Bundle hiện đã qua integrity review, nhưng vẫn cần một quyết định task-graph/protocol riêng nếu muốn dùng nó cho một oracle task sửa đổi.

#### P1-03 — W66 sensitivity và granularity decision

Task này chỉ được chạy sau P1-02 `PASS` theo DAG hiện tại. Nó so sánh W7 và W66, kiểm tra gain có ổn định và phân tán hay không, rồi trả một trong các quyết định:

- `proceed_qpaf`;
- `revise`;
- `stop`.

Một W66 **exploratory-24 subset** riêng đã hoàn tất và được independently verified: Global `0.8296782270669829`, QARF `0.8538451195715936`, QPAF `0.8859108127976215`; QPAF–QARF là `0.03206569322602797`, CI95 `[0.002888476746941956, 0.07116543024082586]`. Nó đạt các numeric continuation signal trên subset nhưng QPAF thấp hơn W7 `0.0179448565863913`; toàn bộ chênh lệch đến từ một trường hợp tied QARF profile làm đổi initialization theo thứ tự grid. Vì vậy, kết luận đúng là heuristic nhạy với tie/order, không phải W66 intrinsically kém hơn W7.

Phase 1 gate hiện yêu cầu trước ngày 2026-09-05:

- W7 và W66 dùng cùng data hash;
- mean QPAF–QARF $\Delta\mathrm{nDCG@10}\ge0.03$ ở cả hai grid;
- cận dưới bootstrap CI lớn hơn 0 ở cả hai grid;
- top 5% query không đóng góp từ 90% tổng gain trở lên;
- decision là `proceed_qpaf`.

Gate này **chưa được đánh giá**, không phải đã fail theo metric.

### Phase 2 — Full Method Implementation

Phase này hiện chưa được dependency-unblock.

#### P2-01 — 13-feature builder

Tạo 13 đặc trưng label-free cho mỗi candidate: normalized score, normalized rank, margin so với median, query-level top-1/top-2 gap và rank disagreement.

#### P2-02 — Linear gate và listwise loss

Implement QARF/QPAF gate, softmax weights, fusion scorer và masked listwise ranking loss. Linear gate chỉ có 42 tham số; độ nặng của dự án nằm ở score extraction và protocol, không nằm ở số tham số gate.

#### P2-03 — Learned QARF baseline

Train QARF trước dưới cùng data/features/loss/budget. Đây là baseline bắt buộc để biết page-level adaptation có hơn query-level adaptation hay không.

#### P2-04 — Learned QPAF confirmation

Train QPAF trên confirmation data. Với ViMDoc, QPAF tạo page score nhưng loss/metric được tính ở document level.

#### P2-05 — đã chuyển sang P3-02

CARF không còn là Phase 2 gate. Contract vẫn được giữ nguyên trong P3-02: cluster candidate bằng feature không nhãn, đóng băng cluster trước khi join qrels, chạy $K=3$ cùng sensitivity $K=2,4$, rồi báo QARF–CARF–QPAF như **oracle granularity ablation**, không phải deployable learned result.

#### Phase 2 gate

Để đi tiếp, tối thiểu cần:

- P2-01 đến P2-04 `PASS`;
- không NaN/Inf;
- measured peak CUDA allocation dưới 1,50 GiB cho learned fusion;
- learned QPAF validation nDCG@10 cao hơn strongest deployable baseline ít nhất 0,01;
- median added fusion latency không quá 10 ms/query.

### Phase 3 — Benchmark, Ablation and Reproducibility

#### P3-01 — Three-seed benchmark

Chạy các learned method với ba seed, báo mean/std và 10.000-resample query bootstrap. Không chọn seed tốt nhất.

#### P3-02 — Ablation

Thay từng yếu tố một: bỏ từng channel, giảm feature, đổi gate, đổi normalization, W7/W66 và candidate-depth sensitivity. P3-02 cũng chứa CARF diagnostic với label-free cluster assignment được đóng băng trước qrels và $K=2/3/4$ sensitivity. Mỗi learned run chỉ được đổi một factor để còn diễn giải được nguyên nhân; CARF phải được tách nhãn oracle khỏi QARF/QPAF learned results.

#### P3-03 — Sealed ViDoRe V3 external validation

Dùng checkpoint/hyperparameter đã đóng băng, không tuning theo external test. Kết quả này kiểm tra external generalization nhưng không chứng minh tiếng Việt.

#### P3-04 — Reproducibility package

Đóng gói config, manifest, prediction, command, hash và bảng kết quả. Ô chưa đo phải ghi `not run` cùng lý do, không điền estimate như kết quả.

Chỉ sau Phase 3 gate mới được báo cáo một learned QPAF result hoàn chỉnh.

## 8. Chính xác Modal P1-02R vừa làm gì?

Function: `extract-vidoseek-p1-02r-scores` trên NVIDIA L4.

### Trước khi tính score

Function kiểm tra:

- approval scope có đúng một human-run hay không;
- dataset ID/revision có trôi không;
- retriever contract hash có khớp không;
- CPU coverage audit và L4 calibration artifact có đúng hash không;
- GPU thật có phải L4 không;
- ba score cache BM25, BGE-M3 và DSE có đúng shape `[1142, 5385]`, finite và đọc được không.

### Trong lúc chạy

1. Tải ColQwen2.5 đã pin revision.
2. Encode query theo 143 chunk, tối đa 8 query/chunk.
3. Encode 5.385 page theo 11 chunk, tối đa 512 page/chunk.
4. Tính visual score cho mọi query với từng page chunk, batch score 128.
5. Ghi chunk embedding/score nguyên tử vào Modal Volume và `commit()` để có thể kiểm tra/resume cache.
6. Sau khi candidate membership đã cố định là all-corpus, mới đọc qrels để audit coverage và tạo relevance dùng cho evaluation.
7. Stream output Parquet theo chunk 8 query, tránh giữ DataFrame 6,1 triệu dòng trong RAM.
8. Ghi manifest, hash và `_EXTRACTION_SUCCESS.json`.

### Bốn payload artifact

`artifact_count: 4` trong receipt nói tới:

1. `candidate_raw_scores.parquet` — raw BM25/BGE/DSE/ColQwen scores, relevance và provenance;
2. `retrieval_scores.parquet` — score đã normalize và rank của từng branch;
3. `candidate_audit.parquet` — một hàng audit cho mỗi query;
4. `coverage_report.json` — coverage và qrels-use statement.

Ngoài bốn payload còn có `extraction_manifest.json` và `_EXTRACTION_SUCCESS.json`.

### Modal không làm gì trong run này?

- Không train QPAF/QARF/CARF.
- Không chạy W7 hoặc W66 oracle.
- Không thay model/retriever.
- Không dùng qrels để xây candidate pool.
- Không tạo HEAVEN `full_score`, `stage2_ms` hoặc `stage2_flops`.
- Không đổi P1-02 từ `BLOCKED` thành `PASS`.
- Không cho phép tự động chạy P1-03.

### Receipt hiện có nói gì?

Local file `artifacts/vidoseek_p1_02r_score_extraction_full.json` hiện ghi:

- function call `fc-01M19RE4SXMJ54M15049QSMXKA`;
- `status: complete`;
- total time `7818.803704091` giây, khoảng 2 giờ 10 phút 19 giây;
- 6.149.670 candidate pair;
- coverage 1,0;
- zero uncovered query;
- `full_score_produced: false`;
- remote output tại `/vol/score_extraction/vidoseek/vidoseek_p1_02r_all_corpus_v1/cfbfcb24ae477a93b3d6a65b40022d688b8172babb2e8080f82363f73fdd8be2/full/output`.

Receipt tự nó chỉ chứa pointer và summary. Sau đó local copy đã được đối chiếu với manifest trên Volume; toàn bộ bốn payload khớp byte hash, hai score table khớp logical-content hash, và data contract đã được kiểm tra theo từng Parquet row group.

## 9. Sau integrity review `PASS`, quy trình đúng là gì?

Các bước intake sau receipt đã hoàn thành:

1. Receipt gốc và remote output path được giữ nguyên.
2. Đúng output directory đã được import; extraction không bị chạy lại.
3. `extraction_manifest.json`, `_EXTRACTION_SUCCESS.json` và SHA-256 của cả bốn payload đều khớp.
4. Hai score table đều có 6.149.670 unique key, finite score, đúng schema và logical-content hash.
5. Mỗi query có đúng 5.385 page; normalization, bốn branch rank và page-ID tie-break đều đúng.
6. Coverage là 1,0; zero uncovered query; source commit, protocol hash, retriever contract, L4 và chunk limits đều khớp.
7. Kết quả được ghi tại `artifacts/vidoseek_p1_02r_integrity_review.json`; execution guard của invocation đã tiêu thụ được đóng.

Gate hiện tại là một **human task-graph/protocol decision**:

1. Dừng P1-02R ở verified recovery artifact; hoặc
2. Phê duyệt một oracle task sửa đổi, có tên và dependency riêng.

Không tự động chạy P1-03 vì DAG hiện vẫn phụ thuộc P1-02 đã bị `BLOCKED`.

Ba tầng trạng thái nên được đọc như sau:

```text
Modal function returned complete                 [done]
              |
              v
Remote bundle imported + all hashes/contracts verified [done]
              |
              v
Human-approved task-graph/protocol decision      [current gate]
              |
              v
Oracle analysis được phép chạy                   [not authorized]
```

Không được nhảy từ tầng đầu xuống tầng cuối.

## 10. Cách đọc log trong lúc chờ Modal

Khi thấy log như `query chunk`, `passage chunk`, `visual chunk`, hãy hiểu:

- **query embedding chunk:** encode một nhóm tối đa 8 query;
- **passage/page embedding chunk:** encode tối đa 512 ảnh trang;
- **visual score chunk:** so sánh embedding của toàn bộ query với page chunk đó;
- **validated cache:** chunk đã có, đúng shape và finite nên được reuse;
- **committed:** chunk đã được ghi vào persistent Volume;
- **output materialization:** đang ghép/stream score thành Parquet và tính hash;
- **success marker:** chỉ xuất hiện sau khi output/manifest đã được ghi.

Thời gian dài chủ yếu đến từ encode 5.385 ảnh bằng ColQwen2.5 và ghi output 6,1 triệu hàng, không phải do linear QPAF gate.

## 11. Lộ trình học lại kiến thức dự án

Không cần đọc toàn bộ code ngay. Nên học theo thứ tự sau:

### Buổi 1 — Nắm bài toán

Đọc tài liệu này đến hết phần 5, rồi tự trả lời:

- QPAF fusion ba score nào?
- DSE được dùng làm gì?
- Tại sao trang không có trong candidate pool thì fusion không thể cứu?
- Oracle khác learned model ra sao?

### Buổi 2 — Nắm protocol và trạng thái

Đọc:

- [`DE_XUAT_NGHIEN_CUU_QPAF.md`](../../DE_XUAT_NGHIEN_CUU_QPAF.md) — câu chuyện nghiên cứu;
- [`Tasks.md`](../../Tasks.md) — dependency, gate và stop condition;
- [`artifacts/pilot_w7/decision.md`](../../artifacts/pilot_w7/decision.md) — tại sao P1-02 bị block;
- [`configs/vidoseek_p1_02r.yaml`](../../configs/vidoseek_p1_02r.yaml) — chính xác P1-02R thay đổi và giữ nguyên gì.

### Buổi 3 — Nắm data flow của run hiện tại

Đọc theo thứ tự:

- [`modal_app.py`](../../modal_app.py), function `extract_vidoseek_p1_02r_scores`;
- [`scripts/extract_vidoseek_p1_02r.py`](../../scripts/extract_vidoseek_p1_02r.py), function `run_chunked_full_extraction`;
- cùng file trên, function `stream_all_corpus_outputs`.

Mục tiêu không phải nhớ từng dòng, mà chỉ cần theo được:

```text
frozen inputs -> validation -> embeddings -> scores -> audit -> Parquet -> manifest
```

### Buổi 4 — Nắm oracle

Đọc:

- [`src/oracle_study/profiles.py`](../../src/oracle_study/profiles.py) — W7/W66;
- [`src/oracle_study/qpaf.py`](../../src/oracle_study/qpaf.py) — Global, QARF, candidate-level QPAF oracle;
- [`src/oracle_study/metrics.py`](../../src/oracle_study/metrics.py) — nDCG/Recall/MRR và deterministic tie-break;
- [`src/oracle_study/bootstrap.py`](../../src/oracle_study/bootstrap.py) — confidence interval.

### Buổi 5 — Chỉ khi Phase 2 được mở

Học feature builder, softmax gate, listwise loss, train/validation/test và multi-seed evaluation. Hiện các task này còn là kế hoạch; không nên học bằng cách giả định đã có learned result.

## 12. Checklist để không bị lạc khi thấy một artifact mới

Mỗi khi có JSON/Parquet/checkpoint mới, hỏi lần lượt:

1. Artifact thuộc task và protocol nào?
2. Nó là preparation, calibration, full run, oracle hay learned result?
3. Dataset/revision/query/page count là gì?
4. Candidate membership được tạo mà không nhìn qrels chứ?
5. Score columns có nghĩa gì và đã normalize ở đâu?
6. Manifest/source commit/config hash có khớp không?
7. Success marker nào được yêu cầu?
8. Gate nào artifact này thực sự chứng minh?
9. Có điều gì artifact **không** chứng minh?
10. Dependency nào cần human approval trước bước tiếp theo?

## 13. FAQ ngắn

### “Coverage 1,0 có nghĩa QPAF tốt không?”

Không. Nó chỉ có nghĩa candidate pool không bỏ sót relevant pair đã biết. Chưa biết fusion xếp relevant page cao đến đâu.

### “Modal báo complete có nghĩa Phase 1 pass không?”

Không. Còn integrity review, protocol decision và oracle gate.

### “Tại sao không bỏ query gây lỗi?”

Vì đã nhìn qrels rồi mới bỏ query sẽ làm protocol thiên lệch và kết quả đẹp giả tạo.

### “Tại sao không thêm trực tiếp relevant page vào candidate pool?”

Vì inference thật không biết relevant page. Làm vậy là qrels leakage.

### “Tại sao all-corpus P1-02R hợp lệ hơn việc tăng top-K theo rank trang đúng?”

Rule all-corpus không phụ thuộc query relevance, score hay observed rank: mọi query nhận cùng toàn bộ corpus. Nó đắt nhưng tránh chọn depth sau khi nhìn đáp án. Dù vậy, nó vẫn là protocol post-hoc và phải được báo cáo riêng.

### “Tại sao giữ P1-02 BLOCKED nếu P1-02R thành công?”

Vì hai task dùng candidate protocol khác nhau. Giữ lịch sử giúp người đọc biết protocol gốc đã thất bại và protocol sửa đổi giải quyết vấn đề bằng cách nào.

### “`full_score_produced: false` có phải lỗi không?”

Không đối với QPAF extraction đã duyệt. `full_score` là trường official HEAVEN khác. Không được thay nó bằng 0 hoặc bằng một score khác.

### “Khi nào mới train QPAF?”

Chỉ sau khi Phase 1 chứng minh đủ oracle headroom và trả decision cho phép đi tiếp. Theo DAG hiện tại, điều đó chưa xảy ra.

### “Nếu QPAF không hơn QARF thì đề tài thất bại hoàn toàn?”

Không nhất thiết. Một kết luận có giá trị có thể là query-level QARF hoặc fixed fusion đủ tốt và page-level complexity không đáng dùng. Điều quan trọng là kết luận dựa trên protocol đáng tin cậy.

## 14. Bảng trạng thái hiện tại

| Mốc | Trạng thái đã được chứng minh | Chưa được phép suy ra |
|---|---|---|
| P0-01 | Baseline đã đóng băng | QPAF tốt hơn baseline |
| P0-02 | Environment/dataset/model revisions đã ghi nhận | Mọi future run tự động tái lập nếu hash trôi |
| P0-03 | QPAF score bundle và finalization hiện hành đã qua gate | Official HEAVEN/Budget-Aware output tồn tại |
| P1-01 | Three-channel và metric contracts đã được harden | Oracle/learned gain tồn tại |
| P1-02 | `BLOCKED` do một query không có relevant candidate | QPAF metric đã fail |
| P1-02R CPU audit | All-corpus membership có coverage 1,0 | Full score bundle đã được kiểm tra |
| P1-02R L4 calibration | Workload mẫu chạy được và có cost projection | Full run chắc chắn thành công |
| P1-02R full function | Receipt local báo `complete` | Bundle local tự động hợp lệ |
| P1-02R integrity review | Bundle local khớp hash/schema/row/key/normalization/rank/coverage/provenance; execution guard đã đóng | P1-02 thành `PASS`, P1-03 được mở, hoặc oracle/QPAF gain tồn tại |
| Exploratory-24 W7 | QPAF 0,903856; QPAF–QARF 0,050011, CI95 [0,008344; 0,101921] trên 24 query | Formal Phase 1 `PASS` hoặc learned/deployable performance |
| Exploratory-24 W66 | QPAF 0,885911; QPAF–QARF 0,032066, CI95 [0,002888; 0,071165] trên cùng 24 query; có tie/order sensitivity | W66 intrinsically tốt/xấu hơn W7 hoặc formal P1-03 decision |
| P1-03 | `BLOCKED` theo dependency hiện tại | Phase 1 gate đã được đánh giá |
| Phase 2 | Chưa dependency-unblock | Learned QPAF đã implement/train |
| Phase 3 | Chưa bắt đầu | Có kết quả multi-seed/external reportable |

## 15. Nguồn sự thật nên dùng

Theo thứ tự cho từng mục đích:

- Trạng thái/dependency/stop condition: [`Tasks.md`](../../Tasks.md).
- Giả thuyết, toán học, feature và evaluation contract: [`Context.md`](../../Context.md).
- Câu chuyện nghiên cứu dễ trình bày: [`DE_XUAT_NGHIEN_CUU_QPAF.md`](../../DE_XUAT_NGHIEN_CUU_QPAF.md).
- Protocol và trạng thái P1-02R hiện tại: [`configs/vidoseek_p1_02r.yaml`](../../configs/vidoseek_p1_02r.yaml).
- Bằng chứng P1-02 bị block: [`artifacts/pilot_w7/decision.md`](../../artifacts/pilot_w7/decision.md).
- CPU coverage audit: [`artifacts/vidoseek_p1_02r_coverage_audit.json`](../../artifacts/vidoseek_p1_02r_coverage_audit.json).
- L4 calibration: [`artifacts/vidoseek_p1_02r_l4_cost_calibration.json`](../../artifacts/vidoseek_p1_02r_l4_cost_calibration.json).
- Receipt full function: [`artifacts/vidoseek_p1_02r_score_extraction_full.json`](../../artifacts/vidoseek_p1_02r_score_extraction_full.json).
- Remote manifest đã import: [`artifacts/vidoseek_p1_02r_import/extraction_manifest.json`](../../artifacts/vidoseek_p1_02r_import/extraction_manifest.json).
- Success marker đã import: [`artifacts/vidoseek_p1_02r_import/_EXTRACTION_SUCCESS.json`](../../artifacts/vidoseek_p1_02r_import/_EXTRACTION_SUCCESS.json).
- Integrity review: [`artifacts/vidoseek_p1_02r_integrity_review.json`](../../artifacts/vidoseek_p1_02r_integrity_review.json).
- W66 exploratory-24 result: [`docs/05_oracle_experiments/w66/QPAF_W66_EXPLORATORY24_RESULTS.md`](../05_oracle_experiments/w66/QPAF_W66_EXPLORATORY24_RESULTS.md) và [`closeout_receipt.json`](../../artifacts/vidoseek_w66_exploratory24_optimized_review/closeout_receipt.json).
- Source thực thi: [`modal_app.py`](../../modal_app.py) và [`scripts/extract_vidoseek_p1_02r.py`](../../scripts/extract_vidoseek_p1_02r.py).

Khi các nguồn khác nhau về status, không chọn câu nghe tích cực nhất. Hãy phân biệt thời điểm và tầng bằng chứng: committed task plan, remote receipt, imported artifact, integrity review, rồi mới đến human-approved decision.
