"""Tests for M1.3 Closed Boundary Guard."""
import unittest

from qpaf.m13.boundary import (
    ExecutionBoundary,
    is_execution_authorized,
    assert_execution_authorized,
    get_boundary_status,
)


class TestM13Boundary(unittest.TestCase):
    def test_default_boundary_is_closed(self):
        self.assertFalse(is_execution_authorized())
        boundary = ExecutionBoundary()
        self.assertFalse(boundary.is_authorized)

    def test_assert_execution_authorized_raises_permission_error(self):
        with self.assertRaises(PermissionError) as ctx:
            assert_execution_authorized()
        self.assertIn("CLOSED", str(ctx.exception))
        self.assertIn("G1", str(ctx.exception))

    def test_boundary_status_metadata(self):
        status = get_boundary_status()
        self.assertIsInstance(status, dict)
        self.assertEqual(status["execution_authorized"], False)
        self.assertEqual(status["boundary_state"], "CLOSED")
        self.assertIn("reason", status)


if __name__ == "__main__":
    unittest.main()
