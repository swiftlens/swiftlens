#!/usr/bin/env python3
"""
Shared helper functions for Swift Context MCP test suite.

This module provides common utilities for test validation and error handling,
particularly for managing LSP environment issues vs genuine tool failures.
"""

import logging
from typing import Any

import pytest

# Add src directory to path for model imports
from swiftlens.model.models import ErrorType

# Set up logging for test helpers
log = logging.getLogger(__name__)


def handle_tool_result(result: dict[str, Any]) -> None:
    """
    Validates a Swift tool's result and handles failures by failing tests.

    This function implements a consistent strategy for distinguishing between:
    1. LSP environment issues (now fail)
    2. Ambiguous errors that might mask bugs (now fail)
    3. Genuine tool failures (fail)

    Args:
        result: The dictionary result returned by a Swift tool

    Raises:
        pytest.fail: For any unexpected errors or malformed responses
    """
    # Validate basic response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    if "success" not in result:
        pytest.fail("Result dict is missing required 'success' key.")

    # Success case - no further validation needed
    if result["success"]:
        return

    # Extract error information
    error_type_str = result.get("error_type")
    error_msg = result.get("error", "")

    # Try to parse error type enum, fall back to string matching for legacy support
    error_type = None
    if error_type_str:
        try:
            error_type = ErrorType(error_type_str)
        except ValueError:
            # Unknown error type, treat as string
            pass

    # Phase 2: Structured error type handling
    if error_type and ErrorType.is_skippable_environment_error(error_type):
        pytest.fail(f"Tool failed due to environment issue: {error_type.value} - {error_msg}")

    if error_type and ErrorType.is_tool_failure(error_type):
        pytest.fail(f"Tool failed: {error_type.value} - {error_msg}")

    # Legacy Phase 1: String-based fallback for backward compatibility
    if not error_type:
        # Skip for specific LSP environment issues and general LSP server problems
        lsp_environment_indicators = [
            "lsp initialization failed",
            "lsp server unavailable",
            "lsp server also unavailable",
            "lsp server failed",
            "lsp server is down",
            "lsp timeout occurred",
            "connection to lsp failed",
            "sourcekit-lsp not found",
            "indexstoredb not found",
            "project_root cannot be none",
            "Use find_swift_project_root()",
            "This ensures IndexStoreDB can be found",
        ]

        for indicator in lsp_environment_indicators:
            if indicator in error_msg.lower():
                pytest.fail(f"Tool failed due to LSP environment issue: {error_msg}")

        # Removed the generic "symbol not found" skip - these should now be legitimate test failures
        # since we have fallback mechanisms

    # Condition 3: Unknown error type or unstructured error -> FAIL
    pytest.fail(
        f"Tool failed with an unexpected error. "
        f"Type: {error_type.value if error_type else error_type_str}, Message: {error_msg}"
    )


def validate_successful_result(result: dict[str, Any], expected_fields: list = None) -> None:
    """
    Validates that a result represents a successful tool execution.

    Args:
        result: The dictionary result returned by a Swift tool
        expected_fields: Optional list of field names that should be present in successful results

    Raises:
        AssertionError: If the result doesn't meet success criteria
    """
    handle_tool_result(result)  # This will skip/fail if not successful

    # If we reach here, the result was successful
    assert result["success"], "Result should be successful after handle_tool_result"

    # Validate expected fields if provided
    if expected_fields:
        for field in expected_fields:
            assert field in result, f"Successful result missing expected field: {field}"
