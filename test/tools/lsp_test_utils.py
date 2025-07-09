#!/usr/bin/env python3
"""
Shared utility functions for LSP-related tests.

This module provides common parsing and assertion helpers for tests that interact
with Swift LSP tools, ensuring consistency and maintainability across test files.
"""


def _safe_int(value, default=0):
    """Safely converts a value to an integer, returning a default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_definition_output(result):
    """
    Parses definition output from various tool formats into a standardized list of dicts.
    Handles both legacy string format and new JSON format.

    Args:
        result: Either a dict (JSON response) or string (legacy format)

    Returns:
        List of dicts with keys: file_path, line, char
    """
    # Handle new JSON format (dict response)
    if isinstance(result, dict):
        if not result.get("success", False):
            return []

        # Handle both direct definitions and nested data structure
        definitions_data = result.get("definitions", [])
        if not definitions_data:
            # Fallback to nested 'data' object structure for backward compatibility
            definitions_data = (result.get("data") or {}).get("definitions", [])

        return [
            {
                "file_path": item.get("file_path", ""),
                "line": item.get("line", 0),
                "char": item.get("character", 0),
            }
            for item in definitions_data
        ]

    # Handle legacy string format (for backward compatibility)
    if isinstance(result, str):
        if "No definition found" in result:
            return []

        definitions = []
        lines = result.strip().split("\n")
        for line in lines:
            if ":" in line:
                parts = line.split(":")
                if len(parts) >= 3:
                    definitions.append(
                        {
                            "file_path": parts[0],
                            "line": _safe_int(parts[1]),
                            "char": _safe_int(parts[2]),
                        }
                    )
        return definitions

    # Unknown format
    return []


def assert_is_acceptable_lsp_result_or_failure(result):
    """
    Asserts that a result is either successful with no definitions found,
    or a known, acceptable failure from the LSP.

    This helper is used to gracefully handle expected LSP behavior in CI environments
    where the LSP may not have full indexing or may encounter initialization issues.
    """
    if isinstance(result, dict):
        if result.get("success", False):
            # Success case: check that no definitions were found
            definitions_data = (result.get("data") or {}).get("definitions", [])
            # Also handle legacy format where definitions might be at root level
            if not definitions_data:
                definitions_data = result.get("definitions", [])

            # It's acceptable to have successful response with no definitions
            assert len(definitions_data) == 0, (
                f"Expected no definitions but found some: {definitions_data}"
            )
        else:
            # Failure case: check for acceptable error messages
            error_msg = result.get("error", "")
            is_known_error = (
                "not found" in error_msg.lower()
                or "no definition" in error_msg.lower()
                or result.get("error_type") == "lsp_error"
            )
            assert is_known_error, f"Unexpected LSP error received in JSON format: {result}"
    else:
        # For string format, check for expected message
        error_found = "No definition found" in str(result) or "not found" in str(result).lower()
        assert error_found, f"Unexpected string error format: {result}"


def assert_is_acceptable_lsp_failure(result):
    """
    Legacy helper - now delegates to the more comprehensive function.
    Kept for backward compatibility.
    """
    assert_is_acceptable_lsp_result_or_failure(result)


# Shared skip reason constants for consistency
SKIP_REASON_INDEXING_REQUIRED = (
    "This test requires a full project build and indexing (IndexStoreDB). "
    "Use 'make test-references' or built_swift_environment fixture for comprehensive testing. "
    "Standard LSP tests may skip reference operations without proper IndexStoreDB."
)

SKIP_REASON_LSP_UNAVAILABLE = "LSP environment not available or failed to initialize."
