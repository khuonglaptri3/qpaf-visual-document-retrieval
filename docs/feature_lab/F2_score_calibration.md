# F2 — Hiệu chỉnh điểm học được (thay min-max cố định)

**Người chạy:** thành viên A · **Ưu tiên:** cao (rẻ nhất, không cần dữ liệu mới) · **Chi phí:** CPU

Đọc [README](README.md) trước để nắm protocol chung. File này chỉ mô tả phần riêng của F2.

## 1. Vấn đề và giả thuyết

Ba kênh được chuẩn hóa min-max theo từng query trên một union khoảng 470 trang (tối đa 600). Giá trị min nằm
sâu ở đuôi danh sách, nên các trang top bị dồn sát 1 và chênh lệch giữa chúng rất nhỏ. Mức dồn này lại khác
nhau giữa các kênh: BM25 có đuôi nặng, còn ColQwen2.5 (max-sim) có phần đầu dày. Khi đó tổ hợp tuyến tính
`Σ w_m ŝ_m` khó xếp đúng phần top, dù trọng số có thích ứng đến đâu. Gate QARF/QPAF hiện phải dùng trọng số
để bù cho việc thang đo bị méo.

**Giả thuyết H-F2:** một biến đổi đơn điệu học được cho từng kênh, đặt trước bước fusion, làm tăng cả static
lẫn QARF/QPAF. Nếu F2 làm QARF và QPAF tăng như nhau, phần lợi đến từ *hiệu chỉnh* chứ không phải *thích ứng*.
Kết luận đó vẫn có giá trị để báo cáo, và F2 vẫn được ghép vào hệ thống cuối.

## 2. Thay đổi kiến trúc

`S(q,p) = Σ_m w_m(q,p) · g_m(ŝ_m(q,p))`, trong đó `g_m: [0,1] → [0,1]` là hàm đơn điệu tăng, dùng chung cho mọi query.

**`f2_pwl`: piecewise-linear đơn điệu, K = 8 đoạn cho mỗi kênh (24 tham số).**

```
g_m(s) = Σ_k p_{m,k} · clamp(K·s − k, 0, 1),   p_m = softmax(logits_m),   k = 0..K−1
```

Hàm này luôn đơn điệu, `g(0) = 0`, `g(1) = 1`. Khi `logits = 0` thì `p = 1/K` và `g(s) = s` **chính xác**, nên ở
epoch 0 mô hình đúng bằng static anchor (harness yêu cầu điều này). Hàm có thể học dạng lõm (giãn vùng top),
dạng lồi, hoặc dạng chữ S.

**`f2_pwl_rrf`: thêm trộn với kênh rank kiểu RRF.**

```
g_m(s) = PWL_m(s) + c_m · (u_m − PWL_m(s)),   u_m = 61 / (60 + rank_m),   c_m khởi tạo 0
```

`u` là RRF-k60 được chuẩn hóa sao cho top-1 = 1. Thí nghiệm này hỏi: thông tin *thứ hạng*, vốn là lý do RRF
mạnh trên nhiều benchmark, có bổ sung gì cho *điểm* không? `c_m` không bị chặn và bắt đầu từ 0, nên epoch 0
vẫn bằng static.

## 3. Code cần viết

| Module | Nội dung |
| --- | --- |
| `src/qpaf/lab/variants/f2_pwl.py` | `MonotonePWL` làm `calibrator` |
| `src/qpaf/lab/variants/f2_pwl_rrf.py` | `PWLRankBlend` làm `calibrator` |

Hook `calibrator` nhận `scores [B, N, 3]` (min-max) và `mask [B, N]`, trả về `[B, N, 3]`. Tham số của calibrator
được train cùng gate và được lấy trung bình trọng số giống gate (harness tự xử lý). Phác thảo dưới đây đã chạy
thử với harness:

```python
"""F2: monotone piecewise-linear score calibration per channel (docs/feature_lab/F2)."""
import torch
from torch import nn

from . import Variant

BINS = 8


class MonotonePWL(nn.Module):
    """g(s) = Σ_k p_k · clamp(K·s − k, 0, 1), p = softmax(logits): monotone, g(0)=0, g(1)=1, identity at init."""
    def __init__(self, bins=BINS):
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(3, bins, dtype=torch.float64))
        self.register_buffer('offsets', torch.arange(bins, dtype=torch.float64))

    def forward(self, scores, mask):
        ramps = (scores[..., None]*len(self.offsets)-self.offsets).clamp(0, 1)
        return (ramps*torch.softmax(self.logits, dim=-1)).sum(-1)


def build(assets):
    return Variant('f2_pwl', calibrator=MonotonePWL)
```

```python
"""F2: PWL calibration blended with a normalized RRF-k60 channel (docs/feature_lab/F2)."""
import torch
from torch import nn

from . import Variant
from .f2_pwl import MonotonePWL


def rrf_channel(scores, mask, k=60):
    """61/(60+rank) per channel among the active pages; ties go to the smaller page index."""
    masked = torch.where(mask[..., None], scores, -torch.inf)
    order = torch.argsort(masked, dim=1, descending=True, stable=True)
    rank = torch.empty_like(order)
    rank.scatter_(1, order, torch.arange(1, scores.shape[1]+1).view(1, -1, 1).expand_as(order))
    return torch.where(mask[..., None], (k+1)/(k+rank.to(scores.dtype)), 0.)


class PWLRankBlend(MonotonePWL):
    def __init__(self):
        super().__init__()
        self.blend = nn.Parameter(torch.zeros(3, dtype=torch.float64))

    def forward(self, scores, mask):
        g = super().forward(scores, mask)
        return g+self.blend*(rrf_channel(scores, mask)-g)


def build(assets):
    return Variant('f2_pwl_rrf', calibrator=PWLRankBlend)
```

### Test bắt buộc (`tests/test_lab_f2.py`)

- Ở lúc khởi tạo, `MonotonePWL()(s, mask)` bằng `s` (sai khác tối đa 1e-12) với `s` ngẫu nhiên trong [0, 1].
- Đặt `logits` ngẫu nhiên: `g` đơn điệu không giảm theo `s`, `g(0) = 0`, `g(1) = 1`.
- `rrf_channel` cho top-1 bằng 1 và trang padding bằng 0, đúng thứ hạng trên một ví dụ tính tay.
- `run_experiment` 2 fold × 2 epoch chạy được với cả hai variant.

## 4. Lệnh chạy

```powershell
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc --data <vimdoc-cache> --variant f2_pwl
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --variant f2_pwl
```

Lặp lại cho `f2_pwl_rrf`. Không cần asset.

## 5. Đọc kết quả và phân tích thêm

- So `f2_pwl` với `baseline` theo verdict chung, riêng cho QARF và QPAF.
- In ra hình dạng `g_m` đã học (lấy từ model trung bình trọng số của fold 0, vẽ `g_m(s)` với `s` từ 0 đến 1).
  Đường lõm ở kênh visual nghĩa là vùng top cần được giãn ra. Hình này dễ giải thích khi giáo viên hỏi.
- Với `f2_pwl_rrf`, ghi lại `c_m` sau khi train. Giá trị gần 0 nghĩa là thứ hạng không thêm được gì so với điểm.

Muốn lấy model đã train để vẽ, gọi trực tiếp `qpaf.lab.train.train_model(...)` cho một fold trong một notebook
hoặc script nhỏ. Không cần sửa harness.

## 6. Rủi ro

- **Static cũng tăng nhờ calibration.** Hàng `static` trong JSON là anchor *không* hiệu chỉnh, nên có thể không
  công bằng nếu nói "QPAF + F2 hơn static". Khi viết báo cáo, so với `baseline` QARF/QPAF là chính. Nếu muốn có
  hàng "static + F2", chạy thêm một variant có calibrator nhưng khóa gate (có thể làm bằng cách đặt
  `learning_rate` của gate bằng 0); việc này không bắt buộc.
- **K quá lớn dễ overfit.** Chỉ thử K = 8. Không quét K trên kết quả CV, vì quét như vậy chính là chọn trên tập đang báo cáo.
