"""Feature-lab variants. Each module here exposes `build(assets) -> Variant` and is selected by name.

A member adds one module per feature (f1_content.py, f2_calibration.py, ...), so no shared file
changes and branches merge without conflicts. `baseline` adds nothing and reproduces the
QARF-SA-R1 / QPAF-SA-R1 recipe on the lab folds.
"""
from dataclasses import dataclass
import importlib
import re


@dataclass(frozen=True)
class Variant:
    """Every hook is optional; leaving one as None keeps the baseline behaviour.

    page_features(query_id, text, page_ids, raw) -> float array [pages, k]
        Extra gate inputs per page, appended to the 13 base features and standardized on the
        training folds. Receives no labels. A query-level feature repeats one row on every page.
    calibrator() -> torch.nn.Module
        Called once per model; forward(scores [B, N, 3], mask [B, N]) returns transformed scores
        [B, N, 3]. It must be the identity at initialization so epoch 0 equals the static anchor.
    loss(unit_scores, unit_mask, positive, log_tau, anchor_scores) -> (loss, valid_queries)
        Replaces the listwise loss. All tensors are [B, U]; anchor_scores are the static-anchor unit
        scores of the same batch (no gradient), useful for truncation or hard-query weights.
    aggregate(page_scores [B, N], units [B, N], unit_count) -> unit scores [B, unit_count]
        Replaces max-page pooling. Used in training and evaluation alike; padded pages score 0 and
        carry unit index unit_count-1, a dummy column that unit_mask excludes.
    hidden: 0 keeps the linear residual; > 0 adds one tanh layer whose output layer is zero-initialized.
    """
    name: str
    page_features: object = None
    calibrator: object = None
    loss: object = None
    aggregate: object = None
    hidden: int = 0


def load_variant(name, assets=None):
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name or ''):
        raise ValueError(f'variant name must be a lowercase module name: {name!r}')
    variant = importlib.import_module(f'{__name__}.{name}').build(dict(assets or {}))
    if not isinstance(variant, Variant) or variant.name != name:
        raise ValueError(f'{name}.build must return Variant(name={name!r}, ...)')
    if type(variant.hidden) is not int or variant.hidden < 0:
        raise ValueError('hidden must be a non-negative integer')
    return variant
