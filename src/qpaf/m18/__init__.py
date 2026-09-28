"""QPAF M1.8 OCR Quality Policy & Artifact Namespace Subsystem."""
from qpaf.m18.namespace import (
    create_run_namespace,
    format_canonical_run_id,
    parse_canonical_run_id,
)
from qpaf.m18.ocr_policy import (
    ExtractionDecision,
    QualityMetrics,
    evaluate_page_text,
)

__all__ = [
    "ExtractionDecision",
    "QualityMetrics",
    "create_run_namespace",
    "evaluate_page_text",
    "format_canonical_run_id",
    "parse_canonical_run_id",
]
