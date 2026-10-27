# M5.5 — Khương

Ngày cập nhật: 27/10/2026. PR #45, nhánh `feature/m5-5-diagnostics`.

**R5-01/02/03/04 đã hoàn thành kỹ thuật; nghiệm thu độc lập của Thanh còn PENDING.**

Báo cáo hiện hành duy nhất của task, gồm kết quả CPU, latency/CUDA mới,
protocol 171 ID / 1.026 lượt đo, code, hash, kiểm thử và phần cần review:

- [Báo cáo M5.5](../docs/reports/milestones/M5.5/README.md).
- [Spec](../docs/reports/milestones/M5.5/superpowers/spec.md) và [plan](../docs/reports/milestones/M5.5/superpowers/plan.md).
- [Workflow/bằng chứng](../docs/reports/milestones/M5.5/evidence/workflow.md).
- [Báo cáo CPU-only ban đầu, giữ nguyên bytes](../docs/reports/milestones/M5.5/evidence/archive-M5_5_Khuong-cpu.txt).

QARF median online 2.569362ms/query; QPAF 2.4263995ms/query. Peak CUDA allocated
lần lượt 0.032428265 và 0.032439709GiB, đạt ngưỡng trong protocol đã ghi.
Không đổi QPAF-v1, không train lại, không mở test qrels hoặc ViMDoc.