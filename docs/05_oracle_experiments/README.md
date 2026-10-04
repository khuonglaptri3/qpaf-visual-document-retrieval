# Thí nghiệm oracle và báo cáo kết quả

Đọc theo study để đối chiếu proposal → execution review → trạng thái chạy → result → integrity review. Oracle là upper bound, không phải kết quả learned.

| Study | Phạm vi |
|---|---|
| [Oracle trên Modal: M1.1](modal_oracle/README.md) | Hướng dẫn triển khai và kiểm chứng oracle. |
| [Calibration CPU ban đầu](calibration/README.md) | Đo thử thời gian và tài nguyên trước oracle. |
| [Exploratory-12: W7 và recovery](exploratory12/README.md) | Oracle W7 trên 12 query và xử lý gián đoạn. |
| [Exploratory-24: tính khả thi W7](exploratory24/README.md) | Oracle W7 trên 24 query cố định. |
| [Fixed-profile discovery audit](fixed_profile/README.md) | Audit profile cố định và headroom toàn discovery. |
| [W66: sensitivity và tài nguyên](w66/README.md) | W66 trên 24 query, calibration, tối ưu và recovery. |

## Danh mục đầy đủ

Các nhận xét về tiến độ trong tài liệu là snapshot theo thời điểm và phạm vi ghi trong từng file.

- [QPAF: prepared CPU calibration handoff](calibration/QPAF_CALIBRATION_HANDOFF.md)
- [QPAF calibration review and proposed next experiment](calibration/QPAF_CALIBRATION_REVIEW_AND_NEXT_STEP.md)
- [First QPAF oracle comparison: prepared execution review](exploratory12/QPAF_EXPLORATORY12_EXECUTION_REVIEW.md)
- [Exploratory-12 interruption handoff](exploratory12/QPAF_EXPLORATORY12_INTERRUPTION_HANDOFF.md)
- [Exploratory-12 recovery execution review](exploratory12/QPAF_EXPLORATORY12_RECOVERY_EXECUTION_REVIEW.md)
- [ViDoSeek exploratory-12: verified Global / QARF / QPAF comparison](exploratory12/QPAF_EXPLORATORY12_RESULTS.md)
- [Exploratory-24 page-level QPAF feasibility: execution review](exploratory24/QPAF_EXPLORATORY24_EXECUTION_REVIEW.md)
- [ViDoSeek exploratory-24: verified Global / QARF / QPAF comparison](exploratory24/QPAF_EXPLORATORY24_RESULTS.md)
- [ViDoSeek fixed-profile discovery audit: verified result](fixed_profile/QPAF_FIXED_PROFILE_AUDIT_RESULTS.md)
- [ViDoSeek exploratory-24 W66: verified Global / QARF / QPAF sensitivity](w66/QPAF_W66_EXPLORATORY24_RESULTS.md)
- [W66 synthetic resource calibration interruption review](w66/QPAF_W66_RESOURCE_CALIBRATION_INTERRUPTION_REVIEW.md)
- [W66 resource-calibration recovery result review](w66/QPAF_W66_RESOURCE_CALIBRATION_RECOVERY_RESULT_REVIEW.md)
- [Exploratory-12 recovery run](exploratory12/QPAF_EXPLORATORY12_RECOVERY_RUN_STATUS.md)
- [Exploratory-12 live run](exploratory12/QPAF_EXPLORATORY12_RUN_STATUS.md)
- [Fixed-profile discovery audit: execution review](fixed_profile/QPAF_FIXED_PROFILE_AUDIT_EXECUTION_REVIEW.md)
- [Query 797: what the saved QPAF weights corrected](exploratory12/QPAF_QUERY797_CASE_STUDY.md)
- [Exploratory-24 W66 sensitivity: preparation and execution review](w66/QPAF_W66_EXPLORATORY24_EXECUTION_REVIEW.md)
- [Optimized exploratory-24 W66: resource and execution review](w66/QPAF_W66_EXPLORATORY24_OPTIMIZED_EXECUTION_REVIEW.md)
- [QPAF_W66_RESOURCE_BUDGET_REVIEW.json](w66/QPAF_W66_RESOURCE_BUDGET_REVIEW.json)
- [W66 resource-budget review](w66/QPAF_W66_RESOURCE_BUDGET_REVIEW.md)
- [W66 synthetic resource calibration: preparation and execution review](w66/QPAF_W66_RESOURCE_CALIBRATION_EXECUTION_REVIEW.md)
- [W66 synthetic resource calibration recovery: preparation and execution review](w66/QPAF_W66_RESOURCE_CALIBRATION_RECOVERY_EXECUTION_REVIEW.md)
- [M1.1 — chạy Oracle có thể tái lập trên Modal](modal_oracle/m1.1-modal-oracle.md)
- [vidoseek_w66_exploratory24_optimized_proposal.json](w66/vidoseek_w66_exploratory24_optimized_proposal.json)
- [vidoseek_w66_exploratory24_proposal.json](w66/vidoseek_w66_exploratory24_proposal.json)
- [vidoseek_w66_resource_calibration_proposal.json](w66/vidoseek_w66_resource_calibration_proposal.json)
- [vidoseek_w66_resource_calibration_recovery_proposal.json](w66/vidoseek_w66_resource_calibration_recovery_proposal.json)
- [vidoseek_w7_exploratory12_proposal.json](exploratory12/vidoseek_w7_exploratory12_proposal.json)
- [vidoseek_w7_exploratory24_proposal.json](exploratory24/vidoseek_w7_exploratory24_proposal.json)
