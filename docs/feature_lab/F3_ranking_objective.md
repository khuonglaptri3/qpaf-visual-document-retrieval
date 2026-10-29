# F3 — Objective theo xếp hạng và cách gộp document

**Người chạy:** thành viên B · **Ưu tiên:** trung bình–cao · **Chi phí:** CPU, không cần dữ liệu mới

Đọc [README](README.md) trước để nắm protocol chung. File này chỉ mô tả phần riêng của F3.

## 1. Vấn đề và giả thuyết

Loss hiện tại là listwise softmax cross-entropy: đẩy *mọi* đơn vị liên quan lên trên *mọi* đơn vị không liên
quan, kể cả ở những query đã xếp đúng top-1. Trên ViMDoc, 95% query đã hòa giữa static và QPAF, tức nằm sẵn ở
trần, nhưng vẫn chiếm phần lớn gradient. Metric lại chỉ quan tâm top-10, và chỉ đổi giá trị ở số ít query khó.

**Giả thuyết H-F3:** loss bám sát nDCG@10, hoặc tập trung vào vùng top và các query khó, chuyển "ngân sách học"
sang đúng chỗ metric thay đổi. Kỳ vọng tăng cả QARF và QPAF, rõ hơn trên ViDoSeek (còn nhiều chỗ để tăng).

Riêng ViMDoc (nhãn ở mức document): điểm document hiện là **max** điểm các trang. Max không phân biệt một
document có một trang khớp ngẫu nhiên với một document có nhiều trang cùng khớp.

## 2. Ba variant

| Module | Hook | Thay đổi |
| --- | --- | --- |
| `f3_approxndcg` | `loss` | ApproxNDCG@10: hạng xấp xỉ bằng sigmoid, cắt mềm ở hạng 10, loss = 1 − nDCG xấp xỉ |
| `f3_topk_hard` | `loss` | Listwise CE chỉ trên top-50 đơn vị theo static anchor; query mà anchor chưa đặt positive ở top-1 nhân trọng số 3 |
| `f3_lse_pool` | `aggregate` | ViMDoc: điểm document = τ·logsumexp(điểm trang/τ) với τ = 0,02 thay cho max. Trên ViDoSeek đơn vị là trang, nên variant này **chỉ chạy ViMDoc** |

`f3_approxndcg` và `f3_topk_hard` giữ đúng điều kiện "epoch 0 = static", vì chỉ đổi loss. `f3_lse_pool` đổi
cách tính điểm document nên epoch 0 không bằng static. So nó với `baseline` QARF/QPAF, không so với hàng `static`.

Siêu tham số chốt sẵn, không quét trên CV: α = 0,01 (ApproxNDCG), k = 50 và trọng số khó = 3 (top-k), τ = 0,02
(LSE). Nếu dư thời gian, chỉ thử thêm **một** giá trị cho mỗi tham số và báo cáo cả hai, không chọn giá trị tốt hơn rồi bỏ giá trị kia.

## 3. Code cần viết

Hook `loss(unit_scores, unit_mask, positive, log_tau, anchor_scores)` nhận tensor `[B, U]` và trả về
`(loss, số query hợp lệ)`. Hook `aggregate(page_scores [B, N], units [B, N], unit_count)` trả về `[B, unit_count]`.
Các phác thảo dưới đây đã chạy thử với harness:

```python
"""F3: ApproxNDCG@10 loss (Qin, Liu & Li 2010) on units (docs/feature_lab/F3)."""
import torch

from . import Variant

ALPHA, CUTOFF = 0.01, 10


def approx_ndcg_loss(unit_scores, unit_mask, positive, log_tau, anchor_scores, alpha=ALPHA, width=0.5):
    positive = positive & unit_mask
    valid = positive.any(1) & (unit_mask & ~positive).any(1)
    if not valid.any():
        return unit_scores.new_zeros(()), 0
    s, m, p = unit_scores[valid], unit_mask[valid], positive[valid].to(unit_scores.dtype)
    s = torch.where(m, s, s.detach().min()-1)  # padding far below every real unit
    beats = torch.sigmoid((s[:, None, :]-s[:, :, None])/alpha)*m[:, None, :]  # [b, i, j]: j above i
    rank = 0.5+beats.sum(-1)  # 1 + Σ_{j≠i}; the self term contributes 0.5
    gain = p*torch.sigmoid((CUTOFF+0.5-rank)/width)/torch.log2(1+rank)  # soft cut at rank 10
    ideal = (1/torch.log2(torch.arange(2, CUTOFF+2, dtype=s.dtype))).cumsum(0)
    count = p.sum(1).clamp(max=CUTOFF).long()
    return (1-gain.sum(1)/ideal[count-1]).mean(), int(valid.sum())


def build(assets):
    return Variant('f3_approxndcg', loss=approx_ndcg_loss)
```

```python
"""F3: listwise loss on the anchor's top-k units with extra weight on queries the anchor gets wrong."""
import math

import torch

from . import Variant

TOP_K, HARD_WEIGHT = 50, 3.


def topk_hard_loss(unit_scores, unit_mask, positive, log_tau, anchor_scores, k=TOP_K, hard=HARD_WEIGHT):
    ranked = torch.argsort(torch.where(unit_mask, anchor_scores, -math.inf), dim=1, descending=True, stable=True)
    keep = torch.zeros_like(unit_mask).scatter_(1, ranked[:, :k], True) & unit_mask
    positive = positive & keep
    valid = positive.any(1) & (keep & ~positive).any(1)
    if not valid.any():
        return unit_scores.new_zeros(()), 0
    logits = torch.where(keep, unit_scores, 0.)[valid]/torch.exp(log_tau)
    log_z = torch.logsumexp(logits.masked_fill(~keep[valid], -math.inf), 1)
    log_pos = torch.logsumexp(logits.masked_fill(~positive[valid], -math.inf), 1)
    wrong_top1 = ~positive[valid].gather(1, ranked[valid][:, :1]).squeeze(1)
    weight = torch.where(wrong_top1, hard, 1.).to(logits.dtype)
    return ((log_z-log_pos)*weight).sum()/weight.sum(), int(valid.sum())


def build(assets):
    return Variant('f3_topk_hard', loss=topk_hard_loss)
```

```python
"""F3: smooth-max (log-sum-exp) page→document pooling for ViMDoc."""
import torch

from . import Variant
from ..model import max_pool

TAU = 0.02


def lse_pool(page_scores, units, unit_count, tau=TAU):
    peak = max_pool(page_scores, units, unit_count)
    spread = torch.exp((page_scores-peak.gather(1, units))/tau)
    total = page_scores.new_zeros(peak.shape).scatter_add(1, units, spread)
    return peak+tau*torch.log(total.clamp_min(1.))  # clamp: empty padding units, exact for real units (total ≥ 1)


def build(assets):
    return Variant('f3_lse_pool', aggregate=lse_pool)
```

### Test bắt buộc (`tests/test_lab_f3.py`)

- `approx_ndcg_loss`: với α = 1e-4, `width` = 0,02 và điểm khác nhau rõ, `1 − loss` khớp với `unit_ndcg` của
  `qpaf.lab.model` (sai khác < 1e-3). Với `width` = 0,5 mặc định, sai khác khoảng 4e-3 do phần cắt mềm ở hạng
  10; đây là thiết kế, không phải lỗi. Gradient phải hữu hạn khi có padding.
- `topk_hard_loss`: với `k` ≥ số đơn vị và mọi query đều "dễ", loss bằng `listwise_loss` của harness.
- `lse_pool`: với τ → 0 (1e-6) kết quả bằng `max_pool`; document có hai trang bằng nhau nhận thêm τ·log 2.
- `run_experiment` 2 fold × 2 epoch chạy được cho cả ba variant.

## 4. Lệnh chạy

```powershell
.venv/Scripts/python.exe scripts/run_lab.py --dataset vimdoc --data <vimdoc-cache> --variant f3_approxndcg
.venv/Scripts/python.exe scripts/run_lab.py --dataset vidoseek --data results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle --variant f3_approxndcg
```

Lặp lại cho `f3_topk_hard`. `f3_lse_pool` chỉ chạy `--dataset vimdoc`.

ApproxNDCG tạo tensor `[B, U, U]`. Với ViDoSeek (U tối đa khoảng 570 trang), mỗi batch khoảng 40 MB, nên chậm
hơn baseline khoảng 2–3 lần. Vẫn chạy được trên CPU.

## 5. Đọc kết quả

- Chủ yếu nhìn số **W/L** chứ không chỉ delta trung bình: F3 nhắm vào query khó, nên kỳ vọng số thắng tăng mà
  số thua không tăng.
- Nếu `f3_topk_hard` thắng mà `f3_approxndcg` không, phần lợi đến từ việc *chọn query và đơn vị để học* chứ
  không phải từ *dạng loss*. Ghi kết luận này vào báo cáo.

## 6. Rủi ro

- ApproxNDCG nhạy với α vì điểm các đơn vị top chỉ cách nhau khoảng 1e-3. Nếu loss gần như không giảm sau 10
  epoch (xem log), thử α = 0,003 và báo cáo cả hai lần chạy.
- `f3_topk_hard` dùng nhãn train để đánh dấu query khó. Việc này hợp lệ vì chỉ xảy ra trong loss, trên fold
  train; lúc chấm điểm không có gì dùng nhãn.
