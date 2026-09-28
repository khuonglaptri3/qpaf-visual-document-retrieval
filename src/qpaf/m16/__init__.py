"""QPAF M1.6 Primary-Corpus Collision Audit Subsystem."""
from qpaf.m16.manifest import (
    AliasRecord,
    PageRecord,
    build_page_manifest,
    resolve_aliases,
)
from qpaf.m16.detector import (
    DuplicateRecord,
    detect_content_duplicates,
    detect_split_leakage,
    verify_qrel_consistency,
)
from qpaf.m16.report import (
    export_alias_csv,
    export_duplicate_csv,
    export_manifest_csv,
    generate_collision_markdown_report,
)

__all__ = [
    "AliasRecord",
    "DuplicateRecord",
    "PageRecord",
    "build_page_manifest",
    "detect_content_duplicates",
    "detect_split_leakage",
    "export_alias_csv",
    "export_duplicate_csv",
    "export_manifest_csv",
    "generate_collision_markdown_report",
    "resolve_aliases",
    "verify_qrel_consistency",
]
