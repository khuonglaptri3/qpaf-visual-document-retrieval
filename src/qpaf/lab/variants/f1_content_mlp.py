"""F1 with one tanh hidden layer (16 units): the content features may act non-linearly on the weights."""
from . import Variant
from .f1_content import content_features


def build(assets):
    return Variant('f1_content_mlp', page_features=content_features(assets['page_text']), hidden=16)
