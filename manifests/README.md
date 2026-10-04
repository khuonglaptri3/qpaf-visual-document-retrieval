# Research manifests

Lưu manifest nhỏ có nguồn gốc thật: dataset, document/page IDs, aliases,
splits, qrels, retrieval cache và SHA-256. Chưa có manifest nghiên cứu thật.

Schema chuẩn bị cho M1.6 nằm trong `evidence/M1_FINAL/03_collision_audit/`.
File chỉ có header là mẫu đầu vào, không phải kết quả audit có zero collision.
Không dùng hash toàn PDF thay cho hash nội dung từng trang khi so sánh trang.
