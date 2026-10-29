# F4 — Embedding ngữ nghĩa của query làm input cho gate (kiểu mFAR/DAT)

**Người chạy:** thành viên B · **Ưu tiên:** trung bình · **Chi phí:** encode khoảng 3.000 query một lần (CPU vài phút)

Đọc [README](README.md) trước để nắm protocol chung. File này chỉ mô tả phần riêng của F4.

## 1. Vấn đề và giả thuyết

QARF trong đề xuất (mục 2, dựa trên mFAR [3] và DAT [4]) chọn trọng số theo *nội dung câu hỏi*. Bản đang có
lại chỉ đọc **trung bình 13 feature điểm số** của các trang ứng viên, nên không phân biệt được "câu hỏi số liệu
tài chính" với "câu hỏi mô tả sơ đồ". Hai loại câu hỏi này cần trọng số kênh khác nhau. Trên ViDoSeek, QARF-v1
(không neo) chỉ đạt 0,7426 trên TEST-172, và QARF-SA chỉ ngang static.

**Giả thuyết H-F4:** đưa biểu diễn ngữ nghĩa của query (BGE-M3, giảm chiều bằng PCA) vào gate giúp QARF học được
"loại câu hỏi → trọng số kênh". F4 chủ yếu nâng **QARF**. Nếu QARF + F4 vượt mọi biến thể QPAF, kết luận hợp lý
là: thích ứng theo câu hỏi với input tốt là đủ. Kết luận này vẫn đúng tinh thần cổng H3 của đề xuất ("nếu QPAF
không vượt QARF … chọn QARF đơn giản hơn").

## 2. Thay đổi kiến trúc

`x(q,p) = [13 feature cũ ; PCA_16(e_q)]`, trong đó `e_q` là embedding dense BGE-M3 (1024 chiều, đã chuẩn hóa) của
câu query, và `PCA_16` là 16 thành phần chính. Mọi trang của một query nhận cùng 16 giá trị này. Với QARF (cổng
theo query), trung bình của chúng chính là `PCA_16(e_q)`.

| Module | Nội dung |
| --- | --- |
| `f4_qemb16` | 16 chiều PCA, gate tuyến tính (29 → 3) |
| `f4_qemb16_mlp` | Cùng input, `hidden=16`. Quan hệ "loại câu hỏi → trọng số" có thể phi tuyến |

PCA được fit trên embedding của **toàn bộ dev pool** (train + validation). Việc này không dùng nhãn nên hợp lệ,
dù có tính transductive. Nếu giáo viên hỏi, câu trả lời là: phép chiếu không thấy nhãn, và kết quả sẽ y hệt nếu
fit trên một tập query không nhãn bất kỳ cùng phân phối. Không encode query của ViMDoc confirmation hay ViDoSeek
test, vì không cần.

## 3. Chuẩn bị asset (một lần, khoảng 30 phút gồm cả tải model)

Asset `query_embeddings`: file `.npz` với `ids` (mảng chuỗi query ID) và `vectors` (`float32 [Q, 1024]`).

Encoder phải giống kênh dense của dự án: `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`,
`query_prefix` rỗng, `normalize_embeddings=True` (xem `configs/m2.8/cache.json` và `src/qpaf/m28/worker.py::_dense`).
`.venv` chưa có `sentence-transformers`, nên hãy tạo một venv riêng cho bước encode để không làm bẩn môi trường
đã khóa (`requirements-lock.txt`).

Viết `scripts/encode_lab_queries.py`:

```python
"""Encode development-pool query texts with the project's BGE-M3 dense encoder (feature lab F4 asset)."""
import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

REVISION = '5617a9f61b028005a4858fdac845db406aefb181'


def dev_queries(dataset, data, root):
    """(ids, texts) for train+validation only."""
    if dataset == 'vimdoc':
        ids = [i for role in ('train', 'validation')
               for i in (root/'evidence/revisions/m4.1-001'/f'{role}_ids.txt').read_text(encoding='utf-8').split()]
        texts = {}
        for line in (data/'queries.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            texts[row['query_id']] = row['text']
    else:
        ids = [i for name in ('train_ids.txt', 'val_ids.txt')
               for i in (data/'splits'/name).read_text(encoding='utf-8').split()]
        texts = json.loads((data/'queries.json').read_text(encoding='utf-8'))
    return ids, [texts[i] for i in ids]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=('vimdoc', 'vidoseek'))
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    ids, texts = dev_queries(args.dataset, args.data, Path(__file__).resolve().parents[1])
    model = SentenceTransformer('BAAI/bge-m3', revision=REVISION, device='cpu')
    vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True,
                           show_progress_bar=True).astype(np.float32)
    np.savez(args.output, ids=np.array(ids), vectors=vectors)


if __name__ == '__main__':
    main()
```

Kiểm tra sau khi encode: số dòng bằng 2.000 (ViMDoc) hoặc 970 (ViDoSeek), không có NaN, và norm mỗi vector ≈ 1.
Không commit `.npz`; harness tự ghi SHA-256 vào kết quả. Riêng ViDoSeek đã có sẵn `query_embeddings.npy` trên
volume `qpaf-m28-score-cache` (M2.8). Có thể dùng file đó thay vì encode lại, miễn là thứ tự ID được ghép đúng
theo `queries.json` của run.

## 4. Code variant

```python
"""F4: 16-d PCA of the BGE-M3 query embedding as a query-level gate input (docs/feature_lab/F4)."""
import numpy as np

from . import Variant

DIMS = 16


def query_table(path, dims=DIMS):
    """Label-free PCA over every query in the file; returns {query_id: [dims]}."""
    data = np.load(path)
    vectors = data['vectors'].astype(np.float64)
    centered = vectors-vectors.mean(axis=0)
    _, _, components = np.linalg.svd(centered, full_matrices=False)
    return dict(zip(data['ids'].tolist(), centered@components[:dims].T))


def build(assets):
    table = query_table(assets['query_embeddings'])

    def page_features(query_id, text, page_ids, raw):
        return np.repeat(table[query_id][None], len(page_ids), axis=0)
    return Variant('f4_qemb16', page_features=page_features)
```

`f4_qemb16_mlp.py`: import `query_table` từ `f4_qemb16`, rồi trả về `Variant('f4_qemb16_mlp', page_features=..., hidden=16)`.

### Test bắt buộc (`tests/test_lab_f4.py`)

- Tạo một file `.npz` giả (20 query, vector ngẫu nhiên): `query_table` cho đúng 16 chiều, và thành phần đầu tiên
  có phương sai lớn nhất.
- `page_features` trả về cùng một hàng cho mọi trang của query; báo lỗi `KeyError` rõ ràng nếu thiếu query ID.
- `run_experiment` 2 fold × 2 epoch chạy được trên dữ liệu giả lập của `tests/test_lab.py`.

## 5. Lệnh chạy

```powershell
# venv riêng cho bước encode
py -m venv .venv-encode; .venv-encode/Scripts/pip install sentence-transformers numpy
.venv-encode/Scripts/python.exe scripts/encode_lab_queries.py --dataset vimdoc --data <vimdoc-cache> --output <dir>/vimdoc_qemb.npz
.venv-encode/Scripts/python.exe scripts/encode_lab_queries.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --output <dir>/vidoseek_qemb.npz

# chạy lab bằng .venv của dự án
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc --data <vimdoc-cache> --variant f4_qemb16 --asset query_embeddings=<dir>/vimdoc_qemb.npz
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --variant f4_qemb16 --asset query_embeddings=<dir>/vidoseek_qemb.npz
```

Lặp lại cho `f4_qemb16_mlp`.

## 6. Đọc kết quả

- Câu hỏi chính: **QARF + F4 có vượt `baseline` QARF không?** QPAF + F4 là phụ.
- Nếu F4 thắng: lấy fold 0, nhóm query theo k-means (k = 6) trên `PCA_16`, rồi in trọng số trung bình mà gate
  QARF gán cho từng nhóm, kèm 3 câu query mẫu mỗi nhóm. Bảng "loại câu hỏi → trọng số BM25/dense/visual" này là
  phần giải thích rất dễ trình bày.

## 7. Rủi ro

- **Overfit:** 16 chiều × 3 đầu ra là ít tham số, nhưng ViDoSeek chỉ có khoảng 780 query train mỗi fold. Bản
  `_mlp` dễ overfit hơn, nên đừng ngạc nhiên nếu nó thua bản tuyến tính.
- **Chuẩn hóa:** harness đã z-score feature thêm vào theo fold train, nên không cần whitening PCA.
