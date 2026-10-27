"""Create the standalone M5.5 report figure from the frozen CPU result."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
LABELS = {'bm25': 'BM25', 'bge_m3': 'BGE-M3', 'colqwen25': 'ColQwen2.5',
          'uniform_combsum': 'Uniform min-max', 'without_bm25': 'Without BM25',
          'without_bge_m3': 'Without BGE-M3', 'without_colqwen25': 'Without ColQwen2.5',
          'uniform_zscore': 'Uniform z-score'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    targets = [args.output_dir/('diagnostics.'+suffix) for suffix in ('png', 'svg')]
    if any(path.exists() for path in targets):
        raise SystemExit('Refusing to overwrite an existing supporting figure; use a new --output-dir')
    auth = json.loads((ROOT/'evidence/revisions/m5.5-001/authorization.json').read_text(encoding='utf-8'))
    data = json.loads((ROOT/'results/m5.5'/auth['run_id']/'diagnostics.json').read_text(encoding='utf-8'))
    baseline = json.loads((ROOT/'results/m4.4/RUN-QPAF-M4_4-MTH-001-20261023T172102Z-A01/baseline_table.json').read_text())
    static = next(row['ndcg_at_10'] for row in baseline['deployable'] if row['method'] == 'train_fitted_static')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.hashsalt': 'm55-cpu-20261027'})
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.8, 5.7), gridspec_kw={'width_ratios': [1.5, 1]})
    rows = data['metrics']
    for index, row in enumerate(rows):
        value = row['ndcg_at_10']
        color = '#16718b' if row['method'].startswith('without') else '#27394d'
        left.scatter(value, index, s=55, color=color, zorder=3)
        left.annotate(f'{value:.6f}', (value, index), xytext=(7, 0), textcoords='offset points', va='center', fontsize=9)
    left.set_yticks(range(len(rows)), [LABELS[row['method']] for row in rows])
    left.invert_yaxis()
    left.axvline(static, color='#ae5540', linestyle='--', linewidth=1.3, label=f'Frozen static: {static:.6f}')
    left.set_xlim(.70, .905)
    left.set_xlabel('Validation nDCG@10')
    left.set_title('A  Fixed diagnostic rows', loc='left', fontweight='bold')
    left.legend(loc='lower left', frameon=False, fontsize=9)
    wanted = ('without_bm25', 'without_bge_m3', 'without_colqwen25', 'uniform_zscore')
    contrasts = {row['method']: row for row in data['contrasts']}
    values = [contrasts[method]['mean_ndcg_delta'] for method in wanted]
    right.barh(range(4), values, height=.55, color=['#16718b' if v >= 0 else '#c97b44' for v in values])
    right.set_yticks(range(4), [LABELS[method] for method in wanted])
    right.invert_yaxis()
    right.axvline(0., color='#485465', linewidth=1)
    for index, value in enumerate(values):
        right.annotate(f'{value:+.6f}', (value, index), xytext=(5, 0),
                       textcoords='offset points', va='center', ha='left', fontsize=9)
    right.set_xlim(-.073, .041)
    right.set_xlabel('Mean paired delta vs uniform min-max')
    right.set_title('B  Registered contrasts', loc='left', fontweight='bold')
    for ax in (left, right):
        ax.grid(axis='x', alpha=.18)
        ax.set_axisbelow(True)
        for edge in ('top', 'right'):
            ax.spines[edge].set_visible(False)
    fig.suptitle('M5.5: validation diagnostics on 171 queries and a fixed candidate pool', fontweight='bold', fontsize=13)
    fig.text(.5, .025, 'Exploratory validation; no refit or test-label access. GPU resource measurements: NOT RUN.',
             ha='center', fontsize=9, color='#485465')
    fig.tight_layout(rect=(0, .06, 1, .93), w_pad=3)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(targets[0], dpi=240, facecolor='white')
    fig.savefig(targets[1], metadata={'Date': None}, facecolor='white')
    plt.close(fig)
    print('\n'.join(str(path) for path in targets))


if __name__ == '__main__':
    main()
