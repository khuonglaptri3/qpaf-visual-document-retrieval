"""Closed Boundary Guard for M1.3.

Ensures execution authorization remains strictly CLOSED prior to official G1 Gate review.
"""
from typing import Any, Dict


class ExecutionBoundary:
    """Manages execution state and prevents unauthorized runs."""

    def __init__(self, authorized: bool = False, rationale: str = "Awaiting official G1 Gate review"):
        self._authorized = authorized
        self._rationale = rationale

    @property
    def is_authorized(self) -> bool:
        return self._authorized

    def assert_authorized(self) -> None:
        if not self._authorized:
            raise PermissionError(
                f"Execution boundary is CLOSED. Training/inference unauthorized ({self._rationale}). "
                "Official G1 Gate decision must be recorded before opening execution."
            )

    def status(self) -> Dict[str, Any]:
        return {
            "execution_authorized": self._authorized,
            "boundary_state": "OPEN" if self._authorized else "CLOSED",
            "reason": self._rationale,
        }


# Global default instance (strictly closed)
_DEFAULT_BOUNDARY = ExecutionBoundary(authorized=False)


def is_execution_authorized() -> bool:
    """Check if execution is currently authorized."""
    return _DEFAULT_BOUNDARY.is_authorized


def assert_execution_authorized() -> None:
    """Raise PermissionError if execution boundary is closed."""
    _DEFAULT_BOUNDARY.assert_authorized()


def assert_stage_authorized(stage: str, source: Dict[str, Any], *, allow_fixture: bool = False) -> None:
    """Only local cached synthetic Oracle verification can bypass the research gate.

    No config switch grants research authorization. Remote workers never allow fixtures.
    """
    if allow_fixture and stage == 'oracle' and source.get('kind') == 'synthetic_software_test':
        return
    assert_execution_authorized()


def get_boundary_status() -> Dict[str, Any]:
    """Get boundary status metadata dictionary."""
    return _DEFAULT_BOUNDARY.status()
