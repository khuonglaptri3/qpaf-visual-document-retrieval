"""Reference row: 13 base features, linear residual, listwise loss, max-page pooling."""
from . import Variant


def build(assets):
    if assets:
        raise ValueError('baseline takes no assets')
    return Variant('baseline')
