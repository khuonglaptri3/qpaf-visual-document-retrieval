# M2.5 — Freeze và software verification

Owner: Thanh. Đặc tả: [`m2.5-baselines-statistics-leakage.md`](../../../docs/03_method/m2.5-baselines-statistics-leakage.md).

`verification.json` ghi: hash của `configs/m2.5/freeze.json`; kiểm byte/hash và
zero query overlap của split M2.1 (799/171/172); kiểm cache fixture label-free;
sáu baseline tính trên fixture và đường paired 10.000-bootstrap với W/T/L.
`learned_qarf` và mọi kết quả thực còn `NOT_RUN`; independent review `PENDING`.
Các số synthetic chỉ xác nhận phần mềm, không phải retrieval result.

Chạy kiểm thử bằng `python -m unittest tests.test_m25_freeze -v`. Lệnh tạo
`verification.json` nằm trong đặc tả; file là create-once.
