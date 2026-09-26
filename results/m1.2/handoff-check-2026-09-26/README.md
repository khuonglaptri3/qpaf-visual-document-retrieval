# M1.2 — kiểm chứng bàn giao ngày 26/09/2026

**PASS — synthetic_software_verification.**

Lệnh từ thư mục gốc repo, sau khi cập nhật liên kết và trạng thái trong đặc tả:

```powershell
.venv/Scripts/python.exe scripts/verify_m12.py --config configs/m1.2/core.toml --output results/m1.2/handoff-check-2026-09-26
```

[Báo cáo](verification/20260926T022045-0ec475f4/verification.md),
[summary](verification/20260926T022045-0ec475f4/summary.json) và
[completion receipt](verification/complete.json) ghi kết quả 23 kiểm tra
core/config không skip, cùng kiểm tra học trên fixture của cả QARF/QPAF.
Hai test CLI integration được bao phủ trong full suite 69 test chạy cùng đợt
(68 đạt, một skip quyền symlink Windows).

Provenance và hashes trong attempt liên kết source/config/đặc tả hiện tại.
Git commit trong provenance là revision nền trước commit bàn giao; working
tree có thay đổi được ghi nhận, source được liên kết bằng hash. Không sửa
receipt để thay commit sau khi chạy. Evidence trước đó được giữ nguyên.

Đây là kiểm chứng cục bộ của phần mềm, không phải kết quả corpus thật hoặc
xác nhận độc lập của thành viên nhóm.
