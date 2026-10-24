"""Remaining experiment roster after G2A and the rules that bind it.

M4.7 fixes what runs, who owns it, which data it may read and which items are
protected. M5.1 orders drops only inside the optional tier.
"""

DATA = ('none', 'no_labels', 'train', 'validation', 'test', 'r7_outputs', 'workbook')
TIERS = {'core': ('R1', 'R2', 'R3', 'R4', 'R7', 'R8'), 'optional': ('R5', 'R6'), 'deferred': ('R9', 'R10')}


def _entry(id, task, title, owner, tier, allowed_data, authorization, depends_on, output):
    return {'id': id, 'task': task, 'title': title, 'owner': owner, 'tier': tier,
            'allowed_data': allowed_data, 'authorization': authorization,
            'depends_on': depends_on, 'output': output}


ROSTER = (
    _entry('R1', 'M5.1', 'Preregister the three-seed matrix, ablation order and drop-first rules within the '
           'optional tier', 'Thanh', 'core', ('none',), 'not_required', (), 'Preregistration record'),
    _entry('R2', 'M5.2', 'Seed cache-parity receipt; external labels stay sealed', 'Khương', 'core',
           ('no_labels',), 'not_required', (), 'Cache-identity receipt'),
    _entry('R3', 'M5.3', 'Matched QARF/QPAF seed 20260821, with fresh-process reload (<= 1e-7) and finite-output '
           'checks', 'Tấn Phát', 'core', ('train', 'validation'), 'required', ('R1', 'R2'),
           'Seed-2 checkpoints, predictions, telemetry and independent reviews'),
    _entry('R4', 'M5.4', 'Matched QARF/QPAF seed 20260822, with fresh-process reload (<= 1e-7) and finite-output '
           'checks', 'Tấn Phát', 'core', ('train', 'validation'), 'required', ('R1', 'R2'),
           'Seed-3 checkpoints, predictions, telemetry and independent reviews'),
    _entry('R5', 'M5.5', 'Retriever/normalization one-factor checks; latency and memory on the frozen checkpoints',
           'Khương', 'optional', ('validation',), 'required', ('R1',), 'One-factor checks and efficiency report'),
    _entry('R6', 'M5.6', 'Feature and query-vs-page conditioning ablations', 'Tấn Phát', 'optional',
           ('validation',), 'required', ('R1',), 'One-factor ablation table'),
    _entry('R7', 'TEST-172', 'One sealed evaluation of the 7 baselines, QARF x3, QPAF x3 and the W7/W66 oracle '
           'context rows', 'Tấn Phát runs, Thanh verifies', 'core', ('test',), 'required', ('R3', 'R4'),
           'Test predictions, metrics and paired statistics for M5.7'),
    _entry('R8', 'M5.7', 'Three-seed aggregation: seed-averaged paired CI, W/T/L, stability, subgroups, errors',
           'Thanh', 'core', ('r7_outputs',), 'not_required', ('R7',), 'Robustness evidence for G3'),
    _entry('R9', 'M5.8', 'Sealed external benchmark', 'Thanh', 'deferred', ('workbook',), 'required', ('R8',),
           'Frozen external result or explicit not-run record'),
    _entry('R10', 'ViMDoc', 'ViMDoc confirmation 8,904 (NOT_RUN_DEFERRED: no verified ViMDoc score cache)', '—',
           'deferred', ('none',), 'not_applicable', (), 'None; the claim is bounded to ViDoSeek'),
)

RULES = (
    'Core items cannot be dropped. M5.1 orders drops only within the optional tier.',
    'R3 and R4 each include a fresh-process reload check (<= 1e-7) and a finite output check before their '
    'checkpoints may enter R7.',
    'R7 runs once, after R3 and R4 have independent reviews. No seed, checkpoint, baseline or method choice is '
    'made after it. Oracle rows are label-using upper bounds, never selectable.',
    'Only R7 may read test labels. R5 and R6 use validation only, and their results cannot change the frozen '
    'method, config or checkpoints.',
)


class RosterError(ValueError):
    """The roster breaks a G2A rule."""


def require(ok, message):
    if not ok:
        raise RosterError(message)


def validate_roster(roster):
    ids = [entry['id'] for entry in roster]
    require(ids == [f'R{i}' for i in range(1, 11)], f'roster IDs must be R1..R10 in order, got {ids}')
    for tier, members in TIERS.items():
        for entry in roster:
            require((entry['tier'] == tier) == (entry['id'] in members),
                    f"{entry['id']}: tier {entry['tier']} breaks the protected {tier} set")
    for entry in roster:
        unknown = [value for value in entry['allowed_data'] if value not in DATA]
        require(not unknown, f"{entry['id']}: unknown data value {unknown}")
        require(('test' in entry['allowed_data']) == (entry['id'] == 'R7'),
                f"{entry['id']}: only R7 may read test data, and R7 must")
        if entry['id'] in ('R5', 'R6'):
            require(tuple(entry['allowed_data']) == ('validation',), f"{entry['id']}: must use validation only")
    r7 = roster[6]
    require({'R3', 'R4'} <= set(r7['depends_on']), 'R7: must wait for R3 and R4')
