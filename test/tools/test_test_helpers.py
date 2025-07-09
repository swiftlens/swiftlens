#!/usr/bin/env python3
"""
Unit tests for test helper functions.

Tests the `handle_tool_result` and `validate_successful_result` functions
to ensure they correctly distinguish between environment issues and tool failures.
"""

import pytest

# Add src directory to path for imports
# Add test directory to path for helper imports
from .test_helpers import handle_tool_result, validate_successful_result


class TestHandleToolResult:
    """Test cases for handle_tool_result function."""

    def test_success_case_passes_through(self):
        """Test that successful results pass through without exception."""
        result = {"success": True, "data": "some data"}
        # Should run without raising any exception
        handle_tool_result(result)

    def test_fails_on_lsp_error_type(self):
        """Test that explicit lsp_error type causes failure."""
        result = {
            "success": False,
            "error_type": "lsp_error",
            "error": "LSP server initialization timeout",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            handle_tool_result(result)

    def test_fails_on_lsp_in_message_case_insensitive(self):
        """Test that LSP in error message causes failure (case insensitive)."""
        test_cases = [
            {"success": False, "error": "LSP server failed"},
            {"success": False, "error": "lsp timeout occurred"},
            {"success": False, "error": "Connection to Lsp failed"},
        ]

        for result in test_cases:
            with pytest.raises(
                pytest.fail.Exception, match="Tool failed due to.*environment issue"
            ):
                handle_tool_result(result)

    def test_fails_on_symbol_not_found(self):
        """Test that 'Symbol not found' now causes test failure since we have fallback mechanisms."""
        result = {"success": False, "error": "Symbol not found: MyClass"}
        with pytest.raises(pytest.fail.Exception, match="Tool failed with an unexpected error"):
            handle_tool_result(result)

    def test_symbol_not_found_case_insensitive_now_fails(self):
        """Test that symbol not found errors now cause test failures instead of skips."""
        test_cases = [
            {"success": False, "error": "Symbol not found: TestClass"},
            {"success": False, "error": "symbol not found: testMethod"},
            {"success": False, "error": "SYMBOL NOT FOUND: GlobalFunction"},
            {"success": False, "error": "The Symbol Not Found in the index"},
        ]

        for result in test_cases:
            with pytest.raises(pytest.fail.Exception, match="Tool failed with an unexpected error"):
                handle_tool_result(result)

    def test_fails_on_unexpected_error(self):
        """Test that unexpected errors cause test failure."""
        result = {
            "success": False,
            "error_type": "some_other_error",
            "error": "A real tool bug occurred",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed with an unexpected error"):
            handle_tool_result(result)

    def test_fails_on_malformed_result_non_dict(self):
        """Test that non-dict results cause assertion failure."""
        with pytest.raises(AssertionError, match="Expected dict response"):
            handle_tool_result("not a dict")

    def test_fails_on_missing_success_key(self):
        """Test that missing success key causes test failure."""
        result = {"error": "Malformed response without success field"}
        with pytest.raises(pytest.fail.Exception, match="missing required 'success' key"):
            handle_tool_result(result)

    def test_complex_error_messages(self):
        """Test handling of complex error messages with multiple keywords."""
        # Should fail on LSP even if other error types mentioned
        result1 = {
            "success": False,
            "error": "File not found but LSP server also unavailable",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            handle_tool_result(result1)

        # Should prioritize LSP environment issues over symbol not found
        result2 = {
            "success": False,
            "error": "Symbol not found because LSP initialization failed",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            handle_tool_result(result2)


class TestValidateSuccessfulResult:
    """Test cases for validate_successful_result function."""

    def test_successful_result_validation(self):
        """Test that successful results pass validation."""
        result = {"success": True, "lines_inserted": 5, "insertion_line": 42}
        # Should run without exception
        validate_successful_result(result, expected_fields=["lines_inserted", "insertion_line"])

    def test_successful_result_missing_expected_fields(self):
        """Test that missing expected fields cause assertion failure."""
        result = {
            "success": True,
            "lines_inserted": 5,
            # Missing "insertion_line"
        }
        with pytest.raises(AssertionError, match="missing expected field: insertion_line"):
            validate_successful_result(result, expected_fields=["lines_inserted", "insertion_line"])

    def test_unsuccessful_result_fails_appropriately(self):
        """Test that unsuccessful results are handled by underlying handle_tool_result."""
        result = {
            "success": False,
            "error_type": "lsp_error",
            "error": "LSP initialization failed",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            validate_successful_result(result)

    def test_no_expected_fields_validation(self):
        """Test that validation works when no expected fields specified."""
        result = {"success": True, "data": "anything"}
        # Should run without exception
        validate_successful_result(result)

    def test_empty_expected_fields_list(self):
        """Test that empty expected fields list works correctly."""
        result = {"success": True, "data": "anything"}
        # Should run without exception
        validate_successful_result(result, expected_fields=[])


class TestErrorHierarchy:
    """Test the priority hierarchy of error conditions."""

    def test_lsp_error_type_takes_precedence(self):
        """Test that explicit error_type='lsp_error' takes precedence over message content."""
        result = {
            "success": False,
            "error_type": "lsp_error",
            "error": "Some other error message without LSP keywords",
        }
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            handle_tool_result(result)

    def test_lsp_in_message_takes_precedence_over_symbol_not_found(self):
        """Test that LSP in message takes precedence over Symbol not found."""
        result = {
            "success": False,
            "error": "Symbol not found because LSP server is down",
        }
        # Should fail due to LSP issue, not symbol not found
        with pytest.raises(pytest.fail.Exception, match="Tool failed due to.*environment issue"):
            handle_tool_result(result)

    def test_symbol_not_found_now_fails_when_no_lsp_issues(self):
        """Test that Symbol not found now causes failure when no LSP issues present."""
        result = {"success": False, "error": "Symbol not found: TestClass"}
        with pytest.raises(pytest.fail.Exception, match="Tool failed with an unexpected error"):
            handle_tool_result(result)
