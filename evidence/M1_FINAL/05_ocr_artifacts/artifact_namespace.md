# Artifact namespace

**Status: DRAFT — pending alignment with Phát's protocol and Thanh's registry.**

## Cấu trúc đề xuất

```text
artifacts/<experiment_id>/<run_id>/
    metadata.json
    config.json
    command.txt
    environment.txt
    logs/
    outputs/
    failures.csv
    hashes.csv
```

`experiment_id` và `run_id` phải theo registry của Thanh; không tự coi quy tắc
đặt tên trong draft là naming đã freeze. Payload nằm ngoài Git; manifest và
liên kết tới storage được version trong repo.

## Create-once và provenance

- Tạo run directory bằng thao tác từ chối nếu namespace đã tồn tại.
- Retry/chỉnh config dùng ID mới và ghi `supersedes` hoặc `retry_of`.
- Metadata cần experiment/run ID, owner, task, actual UTC start/end, Git commit,
  trạng thái working tree, config hash, data/split manifest hash, seed nếu áp
  dụng, engine/version, command và trạng thái thành công/thất bại.
- Output manifest ghi relative path, byte size và SHA-256; mỗi trang/run lỗi
  có failure record. Không ghi token, key hoặc thông tin đăng nhập trong log.
- Chuỗi review: Run → Config → Commit → Data → Hash → Output.
- Commit nguồn cần tồn tại trước lần chạy; không tự dùng commit chứa chính
  kết quả như thể nó là commit đã chạy thí nghiệm.

## Snapshot M1.4

Snapshot đầu nằm ở `evidence/M1_FINAL/01_repository_audit/`. Bản tiếp theo dùng
`evidence/revisions/<snapshot_id>/`; công cụ từ chối ghi đè đường dẫn cũ.
File `audit_metadata.json` ghi scope và các loại trừ. Hash manifest chỉ kiểm
byte integrity; scientific acceptance vẫn cần người review.
