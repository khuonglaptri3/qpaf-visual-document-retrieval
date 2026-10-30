"""F1 ablation: only the four page-side OCR features; run only when f1_content is kept (docs/feature_lab/F1)."""
from . import Variant
from .f1_content import PAGE_SIDE, content_features


def build(assets):
    return Variant('f1_page_only', page_features=content_features(assets['page_text'], columns=PAGE_SIDE))
