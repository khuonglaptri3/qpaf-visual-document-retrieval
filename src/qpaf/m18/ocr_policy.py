"""OCR quality metrics and extraction routing policy for M1.8."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityMetrics:
    char_count: int
    printable_ratio: float
    estimated_confidence: float


@dataclass
class ExtractionDecision:
    route: str  # "NATIVE_TEXT_QUALIFIED", "OCR_FALLBACK_TRIGGERED", "EXTRACTION_FAILED"
    metrics: QualityMetrics
    reason: str


def evaluate_page_text(
    text: str,
    confidence: Optional[float] = None,
    min_chars: int = 50,
    min_printable_ratio: float = 0.85,
    min_confidence: float = 60.0,
) -> ExtractionDecision:
    """Evaluate extracted page text and decide routing between Native-Text and OCR Fallback.

    Note: The default thresholds (min_chars=50, min_printable_ratio=0.85, min_confidence=60.0)
    are PROVISIONAL heuristic baselines, subject to formal calibration freeze in M2.3.
    """
    char_count = len(text)
    conf_val = confidence if confidence is not None else 100.0

    if char_count == 0:
        metrics = QualityMetrics(char_count=0, printable_ratio=0.0, estimated_confidence=conf_val)
        if confidence is not None and confidence < min_confidence:
            return ExtractionDecision(
                route="EXTRACTION_FAILED",
                metrics=metrics,
                reason="empty_text_and_low_ocr_confidence",
            )
        return ExtractionDecision(
            route="EXTRACTION_FAILED",
            metrics=metrics,
            reason="empty_page_text",
        )

    # Count printable characters excluding common control codes
    control_codes = set(range(0, 9)).union({11, 14, 15, 127})
    printable_count = sum(
        1 for c in text if c.isprintable() and ord(c) not in control_codes
    )
    printable_ratio = printable_count / char_count
    metrics = QualityMetrics(
        char_count=char_count,
        printable_ratio=printable_ratio,
        estimated_confidence=conf_val,
    )

    if printable_ratio < min_printable_ratio:
        return ExtractionDecision(
            route="OCR_FALLBACK_TRIGGERED",
            metrics=metrics,
            reason="corrupted_encoding_low_printable_ratio",
        )

    if char_count < min_chars:
        return ExtractionDecision(
            route="OCR_FALLBACK_TRIGGERED",
            metrics=metrics,
            reason="insufficient_character_count",
        )

    return ExtractionDecision(
        route="NATIVE_TEXT_QUALIFIED",
        metrics=metrics,
        reason="native_quality_meets_provisional_threshold",
    )
