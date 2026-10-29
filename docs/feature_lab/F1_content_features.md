# F1 — Feature nội dung cho gate (OCR, query, tương tác query–trang)

**Người chạy:** thành viên A · **Ưu tiên:** cao nhất · **Chi phí:** CPU, cần tải OCR text một lần

Đọc [README](README.md) trước để nắm protocol chung. File này chỉ mô tả phần riêng của F1.

## 1. Vấn đề và giả thuyết

Gate hiện tại có 13 input. 12 input là hàm của chính ba điểm đang được trộn (điểm min-max, reciprocal rank,
gap, disagreement), input còn lại là độ dài query. Vì vậy gate theo trang không biết những điều quyết định
kênh nào đáng tin cho trang đó:

- trang có OCR rỗng hoặc rất ngắn (ViMDoc có 2.169 trang rỗng): BM25 và BGE-M3 gần như vô nghĩa, chỉ visual có giá trị;
- trang dày số liệu hoặc bảng: thường visual đọc tốt hơn OCR, nhưng query hỏi đúng con số thì BM25 lại khớp mạnh;
- query có tên riêng hoặc con số hiếm: BM25 đáng tin hơn;
- query dài, mang tính khái niệm: dense hoặc visual đáng tin hơn.

**Giả thuyết H-F1:** thêm tín hiệu nội dung làm QPAF tăng nhiều hơn QARF, tức khoảng cách QPAF − QARF lớn hơn so
với `baseline`. Đây là thí nghiệm trực tiếp nhất cho đóng góp "theo trang" của đề tài: oracle ViDoSeek cho
QPAF hơn QARF +0,05, nhưng gate hiện tại không có tín hiệu để khai thác phần chênh này.

## 2. Thay đổi kiến trúc

Giữ nguyên `w(q,p) = softmax(log(w̄+ε) + Δθ(x))`, chỉ mở rộng input `x` từ 13 lên 26 chiều.

| Nhóm | Tên | Định nghĩa (token = `re.findall(r'\w+', text.lower())`, giống BM25) |
| --- | --- | --- |
| Trang | `p_log_tokens` | log(1 + số token OCR) |
| | `p_empty` | 1 nếu số token OCR < 5 |
| | `p_numeric_ratio` | tỷ lệ token chứa chữ số |
| | `p_log_lines` | log(1 + số dòng không rỗng); nhiều dòng ngắn thường là bảng hoặc danh sách |
| Query | `q_has_number` | query có chữ số |
| | `q_numeric_intent` | query chứa cụm hỏi số liệu (`how many`, `how much`, `percentage`, `ratio`, `total`, `bao nhiêu`, `tỷ lệ`…) |
| | `q_max_idf`, `q_mean_idf` | IDF lớn nhất và trung bình của token query trên corpus OCR |
| | `q_oov_ratio` | tỷ lệ token query không có trong corpus OCR |
| Tương tác | `i_coverage` | tỷ lệ token query (unique) xuất hiện trong trang |
| | `i_idf_coverage` | giống trên nhưng có trọng số IDF |
| | `i_number_match` | 1 nếu có ít nhất một con số trong query xuất hiện trong trang |
| | `i_bigram_coverage` | tỷ lệ bigram của query xuất hiện trong trang |

Mọi feature đều không dùng nhãn. IDF và vocab tính trên **toàn bộ OCR corpus** (không dùng nhãn) nên được phép
dùng. Harness tự chuẩn hóa z-score các feature thêm vào bằng thống kê của fold train.

## 3. Chuẩn bị asset (một lần, khoảng 1 giờ)

Asset `page_text`: file JSONL, mỗi dòng là `{"page_id": "...", "text": "..."}` cho **mọi trang** của corpus.

| Dataset | Nguồn OCR | Số trang |
| --- | --- | ---: |
| ViMDoc | Modal volume `qpaf-artifacts`, workspace `tranthanhzt123321`, đường dẫn `a005/s1/<RUN>/ocr/shard_00..15/ocr.jsonl` (mỗi dòng đã có `page_id`, `text`). Xem `a005_stage1_modal.py` (`OUT`, `ocr_shard`) | 76.347 |
| ViDoSeek | Modal volume `qpaf-m26-full-ocr` (M2.6). Xem `results/m2.6/RUN-QPAF-M2_6-FULL-OCR-001-*/execution.json` và `output/materialization.json` | 5.385 |

Các bước:

1. `modal volume get` từng shard về một thư mục **ngoài repo**. Lần trước tải file lớn từng bị hỏng block,
   nên phải đối chiếu `ocr_jsonl_sha256` trong marker của từng shard.
2. Gộp các shard thành `vimdoc_page_text.jsonl` / `vidoseek_page_text.jsonl`, chỉ giữ `page_id` và `text`.
3. Kiểm tra: số dòng bằng số trang, `page_id` không trùng, và mọi `page_id` của `candidate_scores.parquet`
   (hoặc `raw_scores.parquet`) đều có trong file.
4. Không commit file text, chỉ ghi SHA-256 vào kết quả (harness tự ghi vào `assets_sha256`).

## 4. Code cần viết

Tạo ba module, mỗi module là một variant:

| Module | Nội dung |
| --- | --- |
| `src/qpaf/lab/variants/f1_content.py` | 13 feature ở mục 2, gate tuyến tính |
| `src/qpaf/lab/variants/f1_content_mlp.py` | Cùng feature, `hidden=16` (một lớp tanh, lớp ra khởi tạo 0) |
| `src/qpaf/lab/variants/f1_page_only.py` | Chỉ 4 feature nhóm Trang; chỉ chạy khi `f1_content` thắng, để biết phần lợi đến từ đâu |

Phác thảo bên dưới đã chạy thử với harness trên OCR giả lập, chưa chạy trên OCR thật. Phác thảo đã tính đến bộ
nhớ: 76k trang được lưu dưới dạng mảng int, không dùng set Python.

```python
"""F1: label-free content features from OCR text, the query and their overlap (docs/feature_lab/F1)."""
import json
import math
import re

import numpy as np

from . import Variant

TOKEN, NUMBER = re.compile(r'\w+'), re.compile(r'\d+(?:[.,]\d+)*')
NUMERIC_INTENT = ('how many', 'how much', 'percentage', 'percent', 'ratio', 'total', 'average',
                  'bao nhiêu', 'tỷ lệ', 'phần trăm', 'tổng')


def tokens(text):
    return TOKEN.findall(text.lower())


class Corpus:
    """Token-ID arrays, bigram IDs, numbers and page-side features for every OCR page."""
    def __init__(self, path):
        self.vocab, self.pages = {}, {}
        for line in open(path, encoding='utf-8'):
            row = json.loads(line)
            toks = tokens(row['text'])
            ids = np.array([self.vocab.setdefault(t, len(self.vocab)) for t in toks], dtype=np.int64)
            lines = sum(1 for part in row['text'].splitlines() if part.strip())
            self.pages[row['page_id']] = {
                'ids': np.unique(ids), 'bigrams': np.unique(ids[:-1]*(1 << 32)+ids[1:]) if len(ids) > 1 else ids[:0],
                'numbers': set(NUMBER.findall(row['text'])),
                'side': [math.log1p(len(toks)), float(len(toks) < 5),
                         sum(any(c.isdigit() for c in t) for t in toks)/max(len(toks), 1), math.log1p(lines)]}
        df = np.zeros(len(self.vocab))
        for page in self.pages.values():
            df[page['ids']] += 1
        self.idf = np.log((len(self.pages)-df+0.5)/(df+0.5)+1)  # BM25-style IDF, label-free


def build(assets):
    corpus = Corpus(assets['page_text'])

    def page_features(query_id, text, page_ids, raw):
        toks = tokens(text)
        known = np.array(sorted({corpus.vocab[t] for t in toks if t in corpus.vocab}), dtype=np.int64)
        idf = corpus.idf[known] if known.size else np.zeros(1)
        q_ids = [corpus.vocab.get(t, -1) for t in toks]
        q_bigrams = np.array([a*(1 << 32)+b for a, b in zip(q_ids, q_ids[1:]) if a >= 0 and b >= 0], dtype=np.int64)
        numbers, lowered = set(NUMBER.findall(text)), text.lower()
        query_side = [float(bool(numbers)), float(any(k in lowered for k in NUMERIC_INTENT)),
                      float(idf.max()), float(idf.mean()), 1-known.size/max(len(set(toks)), 1)]
        rows = []
        for page_id in page_ids:
            page = corpus.pages[page_id]
            hit = np.isin(known, page['ids'], assume_unique=True)
            rows.append(page['side']+query_side+[
                hit.mean() if known.size else 0., (idf*hit).sum()/idf.sum() if known.size else 0.,
                float(bool(numbers & page['numbers'])),
                np.isin(q_bigrams, page['bigrams']).mean() if q_bigrams.size else 0.])
        return np.asarray(rows)
    return Variant('f1_content', page_features=page_features)
```

`f1_content_mlp.py` dùng lại hàm trên và chỉ đổi dòng cuối thành `Variant('f1_content_mlp', page_features=..., hidden=16)`.
Hãy tách `page_features` ra một hàm dùng chung để hai module không lặp code.

### Test bắt buộc (`tests/test_lab_f1.py`, dữ liệu giả lập)

- File `page_text` gồm 3 trang tự tạo: kiểm tra từng feature cho ra đúng giá trị tính tay (OCR rỗng, có số, bigram trùng).
- `page_features` trả về `[pages, 13]`, toàn giá trị hữu hạn, và không thay đổi khi đảo thứ tự gọi các query.
- `run_experiment` chạy được 2 fold × 2 epoch trên dữ liệu giả lập (xem `tests/test_lab.py::synthetic`).

## 5. Lệnh chạy

```powershell
# smoke (vài giây): 200 query, 4 epoch
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc --data <vimdoc-cache> --variant f1_content --asset page_text=<dir>/vimdoc_page_text.jsonl --limit 200 --epochs 4 --folds 2
# chạy thật, 1 seed: baseline mất khoảng 8 phút (ViMDoc) và 4–5 phút (ViDoSeek); F1 cộng thêm vài phút nạp OCR
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc --data <vimdoc-cache> --variant f1_content --asset page_text=<dir>/vimdoc_page_text.jsonl
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --variant f1_content --asset page_text=<dir>/vidoseek_page_text.jsonl
```

Lặp lại cho `f1_content_mlp`. Chỉ chạy `f1_page_only` nếu `f1_content` được KEEP.

## 6. Đọc kết quả

Ngoài verdict chung, F1 trả lời thêm một câu hỏi riêng: **khoảng QPAF − QARF có rộng ra không?** Cột
`QPAF − QARF` của dòng `f1_content` cần lớn hơn rõ so với dòng `baseline` trên cả hai dataset. Nếu F1 chỉ
nâng QARF và QPAF như nhau, feature vẫn có ích cho hệ thống, nhưng không phải bằng chứng cho tính "theo trang".

## 7. Rủi ro

- **OCR tiếng Anh** (`tesseract -l eng`): ViMDoc và ViDoSeek đều là query tiếng Anh nên không sao. Nếu có trang
  tiếng Việt thì tokenizer vẫn tách theo âm tiết, không cần đổi.
- **Bộ nhớ khi nạp ViMDoc:** khoảng 1–2 GB với cách lưu mảng int ở trên. Nếu vẫn quá nặng, chỉ nạp các trang
  có trong `candidate_scores.parquet` của dev pool.
- **Tốc độ:** `np.isin` cho khoảng 950k cặp query–trang mất vài chục giây. Harness chỉ gọi `page_features` một
  lần cho mỗi query, nên không ảnh hưởng thời gian train.
