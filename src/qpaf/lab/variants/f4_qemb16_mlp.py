"""F4 with one tanh hidden layer (16 units): question type → channel weights may be non-linear."""
from . import Variant
from .f4_qemb16 import query_features


def build(assets):
    return Variant('f4_qemb16_mlp', page_features=query_features(assets['query_embeddings']), hidden=16)
