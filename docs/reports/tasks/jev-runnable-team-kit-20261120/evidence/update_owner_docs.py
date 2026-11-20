"""Controller-only: update an existing owner brief after merging reviewed code."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COMMON = "jev-runnable-team-kit-20261120"
OWNERS = {
    "khuong": ("Khương", "jev-khuong-model-20261120", "research/jev-khuong-model", [
        "Nhận pairs/split/page-level train labels đã khóa từ Phát; kiểm tra ví dụ query–OCR.",
        "Chạy Kev-4B frozen trên cùng pairs với BGE/Qwen4B; lưu score/token/time/VRAM thực tế.",
        "Smoke GPU forward/backward và save/reload; fine-tune LoRA/head từ Kev và cùng kiến trúc từ Qwen3.5-4B-Base với cùng data/loss/budget.",
        "Chọn checkpoint bằng train/validation, gửi scores cho Thanh; viết ablation frozen/adapted và base/Kev.",
    ]),
    "phat": ("Phát", "jev-phat-data-infra-20261120", "research/jev-phat-data-infra", [
        "Khôi phục OCR/query/page/document mapping và raw channel/reranker cache riêng; lập inventory có/còn thiếu.",
        "Cùng nhóm khóa split/group/cohort/top-20 và input policy; tạo pairs/score manifests cùng hash, kiểm tra coverage.",
        "Chuẩn bị môi trường và Volume riêng cho job đồng thời; ghi GPU/token/time/cost, điều phối frozen và training pilot.",
        "Tích hợp outputs chung của Thanh/Khương; giữ raw pairs, revisions và log để tái lập.",
    ]),
    "thanh": ("Thanh", "jev-thanh-baselines-20261120", "research/jev-thanh-baselines", [
        "Nhận pool/split/protocol đã khóa từ Phát; kiểm tra raw-score reuse theo pairs hash và coverage.",
        "Replay lịch sử bằng F9 full-ranking khi đủ cache; chạy baseline không rerank, BGE và Qwen4B trên protocol mới.",
        "Chấm mọi model bằng evaluator chung; lưu per-query nDCG/MRR/Recall, paired delta/CI/W–T–L và chi phí.",
        "Phân tích lỗi/headroom và ablation cùng Khương; không kết luận Jev thắng từ demo hoặc mean khác protocol.",
    ]),
}


def write(path: Path, text: str):
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True, choices=OWNERS)
    parser.add_argument("--shared-commit", required=True)
    args = parser.parse_args()
    name, task, branch, research = OWNERS[args.owner]
    actual = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if actual != branch:
        raise SystemExit(f"Expected {branch}; found {actual}")
    subprocess.run(["git", "merge-base", "--is-ancestor", args.shared_commit, "HEAD"], cwd=ROOT, check=True)
    bundle = ROOT / "docs/reports/tasks" / task
    evidence = bundle / "evidence"
    for relative in ("README.md", "superpowers/spec.md", "superpowers/plan.md", "evidence/workflow.md", "evidence/validation.json", "evidence/hashes.json"):
        source = bundle / relative
        archive = evidence / (source.stem + "-bootstrap-before-runtime-20261120" + source.suffix)
        if not archive.exists():
            archive.write_bytes(source.read_bytes())
    old_spec = (bundle / "superpowers/spec.md").read_text(encoding="utf-8")
    old_spec = old_spec.replace("Status: nghiên cứu/implementation chưa thực hiện.", "Status: đã có code runnable; nghiên cứu model/dữ liệu thật còn chờ thực hiện.")
    old_spec = old_spec.replace(
        "Code hiện có là F9 tại base; branch bootstrap chỉ thêm tài liệu. Chưa có runner Jev, model training, baseline replay mới, environment installation hoặc model-quality verification.",
        f"Đã tích hợp toolkit chung từ commit `{args.shared_commit}`. Xem [spec triển khai](../../{COMMON}/superpowers/spec.md) và [kết quả kiểm chứng](../../{COMMON}/README.md). Có CLI dữ liệu/evaluation, BGE/Qwen/Kev adapters, train-only export, trainer chính thức và local/Modal worker. Tiny CPU integration đã chạy; benchmark 4B trên dữ liệu đồ án và GPU chưa chạy."
    )
    # The spec is one level deeper than the report; sibling-task links use ../../.
    write(bundle / "superpowers/spec.md", old_spec)
    write(bundle / "superpowers/plan.md", f"""# Kế hoạch tiếp tục của {name}

Spec: [spec.md](spec.md). Branch: `{branch}`.

## Code đã bàn giao

- [x] Giữ F9 base và brief; tích hợp shared implementation `{args.shared_commit}` với lịch sử review còn truy cập được.
- [x] Cung cấp `scripts/run_jev_{args.owner}.py`, cấu hình owner và hướng dẫn chung; demo mặc định dùng stdlib/offline.
- [x] Có hợp đồng dữ liệu/cache/split, evaluator chung, model adapters và đường export/train/dry-run thực tế.
- [x] Kiểm chứng shared toolkit và tiny CPU train/reload; đây là kiểm chứng plumbing, chưa phải kết quả 4B/dữ liệu đồ án.

## Nghiên cứu tiếp trên dữ liệu thật

""" + "\n".join(f"- [ ] {item}" for item in research) + f"""

Lệnh chính xác và prerequisites: [runbook chung](../../{COMMON}/README.md). Không sửa core/receipts lịch sử. Không dùng document labels làm page labels; không dùng outer-eval để train/tune. Budget training của hai initialization phải giống nhau; tránh đúng mười effective optimizer steps do giới hạn scheduler upstream đã ghi trong runbook.
""")
    write(bundle / "README.md", f"""# {name}: branch nghiên cứu Jev đã có code

**Đã có toolkit runnable và lệnh khởi động.** Branch `{branch}` tích hợp shared implementation `{args.shared_commit}`. Kết quả mô hình 4B trên dữ liệu đồ án còn chờ chạy.

```bash
git clone --branch {branch} --single-branch https://github.com/khuonglaptri3/qpaf-visual-document-retrieval.git
cd qpaf-visual-document-retrieval
python scripts/run_jev_{args.owner}.py
```

Python >=3.11 chạy demo offline, không cần thư viện model. Output mặc định ở common task `evidence/runs/{args.owner}/`, có nhãn synthetic. Đây là kiểm tra setup; số demo không dùng kết luận chất lượng Jev.

[Hướng dẫn dùng dữ liệu thật, model và GPU](../{COMMON}/README.md) có lệnh prepare/score/evaluate/compare/export-train/train, pin môi trường và ví dụ local/Modal. Dùng input riêng và môi trường model riêng theo runbook; `--execute` mới chạy training/cloud.

## Phần việc tiếp theo của {name}

""" + "\n".join(f"- {item}" for item in research) + f"""

Đọc [spec](superpowers/spec.md), [plan](superpowers/plan.md), [workflow](evidence/workflow.md), [kiểm chứng](evidence/validation.json) và [hash](evidence/hashes.json). Bootstrap ban đầu được lưu trong evidence; trạng thái cũ không mô tả bản code hiện tại. Source F9, kết quả/receipts đã đóng băng giữ nguyên. [Bằng chứng shared implementation](../{COMMON}/README.md).
""")
    workflow = (evidence / "workflow.md").read_text(encoding="utf-8")
    write(evidence / "workflow.md", workflow + f"""

## Runnable implementation delivery, 2026-11-20

User explicitly requested real clone-and-run code on all three owner branches. Shared task spec/plan preceded implementation; Superpowers 7.0.1 SDD/TDD/task review/final review and Modal 1.5.5 provenance are in the [shared workflow](../../{COMMON}/evidence/workflow.md). Merged the reviewed shared ancestry `{args.shared_commit}` into this existing branch; no main/develop merge, force push or paid job. Archived the initial brief/spec/plan/workflow/validation/hashes before replacing current status. Common kit tests and tiny random CPU training demonstrate execution plumbing, not project model quality. Full private-data/GPU research remains unchecked above. The controller records fresh-clone and remote-ref verification separately from the initial documentation bootstrap.
""")
    index = ROOT / "docs/README.md"
    write(index, index.read_text(encoding="utf-8").replace(
        "branch/brief đã tạo; implementation và thí nghiệm chưa chạy.",
        "đã có code và lệnh demo offline; benchmark 4B/dữ liệu đồ án còn chờ chạy."
    ))
    paths = sorted(p for p in bundle.rglob("*") if p.is_file() and p != evidence / "hashes.json")
    validation = {
        "owner": name, "branch": branch, "shared_commit": args.shared_commit,
        "bundle_layout": sorted(p.name for p in bundle.iterdir()) == ["README.md", "evidence", "superpowers"],
        "planning_layout": sorted(p.name for p in (bundle / "superpowers").iterdir()) == ["plan.md", "spec.md"],
        "wrapper_present": (ROOT / f"scripts/run_jev_{args.owner}.py").is_file(),
        "model_quality_verified": False,
        "fresh_clone_and_remote_proof": "controller delivery registry; not initial bootstrap validation",
    }
    if not all(validation[k] for k in ("bundle_layout", "planning_layout", "wrapper_present")):
        raise SystemExit(json.dumps(validation))
    write(evidence / "validation.json", json.dumps(validation, ensure_ascii=False, indent=2))
    paths.append(ROOT / "docs/README.md")
    write(evidence / "hashes.json", json.dumps({"algorithm": "SHA-256", "excludes": "this manifest itself", "files": [
        {"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(paths))
    ]}, ensure_ascii=False, indent=2))
    print(json.dumps(validation, ensure_ascii=True))


if __name__ == "__main__":
    main()
