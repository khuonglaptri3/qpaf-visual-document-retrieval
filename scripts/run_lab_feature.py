"""Member entry point: run every variant of one feature end to end (docs/feature_lab/HUONG_DAN_CHAY.md).

    .venv/Scripts/python.exe scripts/run_lab_feature.py --feature f1 --share D:/qpaf-lab-share

Steps: check the share folder against its MANIFEST, check the code is committed, run the unit tests,
reproduce the committed baseline once per machine, run each variant on its datasets, then write
results/lab/SUMMARY_<feature>.md. Finished runs are skipped while src/ and scripts/ are unchanged, so
re-running after an interruption resumes. --smoke runs the whole chain on a small slice in a few minutes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VIDOSEEK = ROOT/'results/m2.8/RUN-QPAF-M2_8-EXPANSION-001-20261021T042029Z-A01/bundle'
DATASETS = ('vimdoc', 'vidoseek')
FEATURES = {
    'f1': {'branch': 'feature/lab-f1-content', 'variants': ('f1_content', 'f1_content_mlp'),
           'optional': ('f1_page_only',), 'asset': ('page_text', '{}_page_text.jsonl')},
    'f2': {'branch': 'feature/lab-f2-calibration', 'variants': ('f2_pwl', 'f2_pwl_rrf')},
    'f3': {'branch': 'feature/lab-f3-objective', 'variants': ('f3_approxndcg', 'f3_topk_hard', 'f3_lse_pool')},
    'f4': {'branch': 'feature/lab-f4-qemb', 'variants': ('f4_qemb16', 'f4_qemb16_mlp'),
           'asset': ('query_embeddings', '{}_qemb.npz')},
}
VIMDOC_ONLY = {'f3_lse_pool'}  # ViDoSeek units are pages, so document pooling does not apply
SMOKE = ['--limit', '120', '--epochs', '2', '--folds', '2']
TOLERANCE = 5e-5  # baseline means must agree to 4 decimals


def stop(message):
    sys.exit(f'\n[DỪNG] {message}')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def check_share(share, names):
    manifest_path = share/'MANIFEST.json'
    if not manifest_path.is_file():
        stop(f'Không thấy {manifest_path}. --share phải là thư mục đã giải nén từ qpaf-lab-share.zip.')
    files = json.loads(manifest_path.read_text(encoding='utf-8'))['files']
    for name in names:
        if not (share/name).is_file():
            stop(f'Thiếu {share/name} trong thư mục share.')
        if sha256(share/name) != files[name]['sha256']:
            stop(f'{name} sai SHA-256 so với MANIFEST (file hỏng khi tải?). Tải lại qpaf-lab-share.zip.')
    print(f'Share folder OK ({len(names)} file khớp MANIFEST).')


def code_unchanged(commit):
    """True when src/ and scripts/ at HEAD equal those of the commit that produced a result."""
    try:
        return subprocess.run(['git', 'diff', '--quiet', commit, 'HEAD', '--', 'src', 'scripts'], cwd=ROOT).returncode == 0
    except OSError:
        return False


def finished(path):
    if not path.is_file():
        return False
    record = json.loads(path.read_text(encoding='utf-8'))
    return not record.get('tracked_changes') and code_unchanged(record['source_commit'])


def run_lab(dataset, data, variant, output=None, assets=(), extra=()):
    command = [sys.executable, str(ROOT/'scripts/run_lab.py'), '--dataset', dataset, '--data', str(data),
               '--variant', variant, *[a for asset in assets for a in ('--asset', asset)], *extra]
    if output:
        command += ['--output', str(output)]
    print(f'\n=== {variant} / {dataset} ===', flush=True)
    if subprocess.run(command, cwd=ROOT).returncode:
        stop(f'run_lab.py lỗi ở {variant}/{dataset}; xem log ngay phía trên.')


def check_baseline(data):
    """Reproduce the committed baseline once per machine; a mismatch means different data or environment."""
    for dataset in DATASETS:
        reference = json.loads((ROOT/f'results/lab/{dataset}/{dataset}-baseline.json').read_text(encoding='utf-8'))
        mine_path = ROOT/f'results/lab/_smoke/baseline_check/{dataset}-baseline.json'
        if not mine_path.is_file():
            run_lab(dataset, data[dataset], 'baseline', mine_path)
        mine = json.loads(mine_path.read_text(encoding='utf-8'))
        if mine['inputs_sha256'] != reference['inputs_sha256']:
            stop(f'Dữ liệu {dataset} khác bản gốc (SHA-256 input khác). Kiểm tra lại thư mục share.')
        gaps = {m: abs(mine['mean'][m]-reference['mean'][m]) for m in reference['mean']}
        if max(gaps.values()) > TOLERANCE:
            mine_path.unlink()
            stop(f'Baseline {dataset} không khớp bản gốc: {gaps}. Môi trường khác (.venv/requirements-lock.txt); '
                 'báo Research Lead trước khi chạy tiếp.')
        print(f'Baseline {dataset} khớp bản gốc: ' + ', '.join(f"{m} {mine['mean'][m]:.4f}" for m in mine['mean']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--feature', required=True, choices=sorted(FEATURES))
    parser.add_argument('--share', required=True, type=Path, help='thư mục đã giải nén qpaf-lab-share.zip')
    parser.add_argument('--smoke', action='store_true', help='chạy thử nhanh trên 120 query, 2 epoch, 2 fold')
    parser.add_argument('--with-optional', action='store_true', help='F1: chạy thêm f1_page_only (khi f1_content KEEP)')
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    feature = FEATURES[args.feature]
    share = args.share.resolve()
    data = {'vimdoc': share/'vimdoc', 'vidoseek': VIDOSEEK}
    variants = feature['variants']+(feature.get('optional', ()) if args.with_optional else ())

    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    if branch != feature['branch']:
        stop(f"Đang ở branch {branch}. Chạy: git checkout {feature['branch']}")
    if git('status', '--porcelain', '--untracked-files=no'):
        stop('Có thay đổi chưa commit trong file đã track. Commit (hoặc git stash) trước khi chạy để kết quả ghi đúng commit.')
    asset = feature.get('asset')
    needed = [f'vimdoc/{n}' for n in ('candidate_scores.parquet', 'queries.jsonl', 'dev_qrels.json')]
    needed += [f'assets/{asset[1].format(d)}' for d in DATASETS] if asset else []
    check_share(share, needed)

    tests = ['tests.test_lab', f'tests.test_lab_{args.feature}']
    if subprocess.run([sys.executable, '-m', 'unittest', *tests], cwd=ROOT).returncode:
        stop('Unit test lỗi; kiểm tra môi trường .venv (README mục 3).')

    if not args.smoke:
        check_baseline(data)
    for variant in variants:
        for dataset in DATASETS:
            if variant in VIMDOC_ONLY and dataset != 'vimdoc':
                continue
            assets = [f'{asset[0]}={share/"assets"/asset[1].format(dataset)}'] if asset else []
            if args.smoke:
                run_lab(dataset, data[dataset], variant, assets=assets, extra=SMOKE)
            elif finished(ROOT/f'results/lab/{dataset}/{dataset}-{variant}.json'):
                print(f'\n=== {variant} / {dataset}: đã có kết quả với code hiện tại, bỏ qua ===')
            else:
                run_lab(dataset, data[dataset], variant, assets=assets)
    if args.smoke:
        print('\nSmoke test OK. Chạy thật: bỏ --smoke.')
        return

    summary = ROOT/f'results/lab/SUMMARY_{args.feature}.md'
    subprocess.run([sys.executable, str(ROOT/'scripts/compare_lab.py'), '--output', str(summary)], cwd=ROOT, check=True)
    results = ' '.join(f'results/lab/*/*-{v}.json' for v in variants)
    print(f'\nXONG. Bảng so sánh: {summary.relative_to(ROOT).as_posix()}\nNộp kết quả:\n'
          f'  git add {results} results/lab/SUMMARY_{args.feature}.md\n'
          f'  git commit -m "results(lab): {args.feature} 5-fold CV"\n'
          f"  git push -u origin {feature['branch']}\n"
          'Rồi gửi Research Lead file SUMMARY kèm 3–5 dòng nhận xét (mục "Đọc kết quả" trong plan).')


if __name__ == '__main__':
    main()
