# Hướng dẫn chạy Feature Lab

Code của bốn feature và dữ liệu đã chuẩn bị sẵn. Mỗi người chỉ cần chạy lệnh rồi nộp kết quả.

| Người | Feature | Branch |
| --- | --- | --- |
| Thanh | F1 feature nội dung | `feature/lab-f1-content` |
| Thanh | F2 hiệu chỉnh điểm | `feature/lab-f2-calibration` |
| Khương | F3 objective xếp hạng | `feature/lab-f3-objective` |
| Khương | F4 embedding query | `feature/lab-f4-qemb` |

## Làm một lần

1. Nhận `qpaf-lab-share.zip` từ Tấn Phát và giải nén **ngoài repo**, ví dụ `D:\qpaf-lab-share`. Trong thư mục phải có
   `MANIFEST.json`. Không commit và không chia sẻ tiếp thư mục này.
2. `git fetch origin`
3. Dùng `.venv` của dự án như các task trước. Nếu chưa có thì tạo bằng `py -m venv .venv`, rồi chạy
   `.venv/Scripts/pip install -r requirements-lock.txt` và `.venv/Scripts/pip install -e .`.

## Với mỗi feature (ví dụ F1)

```powershell
git checkout feature/lab-f1-content
.venv/Scripts/python.exe scripts/run_lab_feature.py --feature f1 --share D:\qpaf-lab-share --smoke
.venv/Scripts/python.exe scripts/run_lab_feature.py --feature f1 --share D:\qpaf-lab-share
```

- Lệnh `--smoke` chạy thử vài phút để biết máy chạy được. Lệnh thứ hai chạy thật.
- Lần chạy thật đầu tiên trên mỗi máy sẽ chạy lại `baseline` (khoảng 13 phút) để kiểm tra môi trường khớp bản gốc.
- Thời gian mỗi variant là 8–25 phút cho mỗi dataset (F3 `f3_approxndcg` trên ViDoSeek chậm nhất).
- Bị ngắt giữa chừng thì chạy lại đúng lệnh đó. Phần đã xong sẽ được bỏ qua.
- Khi xong, script in sẵn ba lệnh `git add` / `commit` / `push`. Chạy ba lệnh đó, rồi gửi Tấn Phát file
  `results/lab/SUMMARY_<feature>.md` kèm 3–5 dòng nhận xét theo mục "Đọc kết quả" trong plan của feature.

Đổi `f1` / branch cho F2, F3, F4. F1: chỉ chạy thêm `--with-optional` (variant `f1_page_only`) khi Research Lead
báo `f1_content` được KEEP.

## Khi gặp `[DỪNG]`

Dòng `[DỪNG]` nói rõ cần làm gì: sai branch, có file chưa commit, file share hỏng, hoặc baseline không khớp. Nếu
**baseline không khớp** thì dừng lại và báo Tấn Phát, đừng chạy tiếp.

Không sửa `src/qpaf/lab/{data,model,train,compare}.py`. Nếu thấy cần sửa, báo Research Lead.
