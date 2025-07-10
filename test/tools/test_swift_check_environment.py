#!/usr/bin/env python3
"""
Test file for check_swift_environment tool.

This test validates the check_swift_environment tool functionality using pytest.
"""

import sys

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_check_environment import swift_check_environment


@pytest.fixture(scope="module")
def environment_check_result():
    """
    Fixture that runs swift_check_environment() once per module and provides its
    output to the test functions. This is more efficient than running it for each test.
    """
    result = swift_check_environment()
    # The fixture can also contain basic, shared assertions.
    assert result is not None, "The tool should never return None."
    assert isinstance(result, dict), "Result should be a dictionary"
    return result


def test_basic_functionality(environment_check_result):
    """
    Original Test 1: Validates that the tool returns a proper JSON structure.
    """
    # Validate response structure
    assert "success" in environment_check_result, "Result should have 'success' field"
    assert "environment" in environment_check_result, "Result should have 'environment' field"
    assert "ready" in environment_check_result, "Result should have 'ready' field"
    assert "recommendations" in environment_check_result, (
        "Result should have 'recommendations' field"
    )

    # Environment should be a dictionary
    assert isinstance(environment_check_result["environment"], dict), (
        "Environment should be a dictionary"
    )
    assert isinstance(environment_check_result["recommendations"], list), (
        "Recommendations should be a list"
    )


def test_expected_content_validation(environment_check_result):
    """
    Original Test 2: Checks that the environment contains expected fields.
    Updated for macOS-only requirement.
    """
    # Skip validation on non-macOS since tool now requires macOS
    if sys.platform != "darwin":
        pytest.skip("Tool requires macOS - skipping environment validation on non-macOS")

    environment = environment_check_result["environment"]
    expected_keys = ["xcrun_available", "sourcekit_lsp_available", "python_version"]
    found_keys = [key for key in expected_keys if key in environment]
    assert len(found_keys) >= 3, f"Missing expected environment keys. Found only: {found_keys}"

    # Validate types
    assert isinstance(environment["xcrun_available"], bool), "xcrun_available should be boolean"
    assert isinstance(environment["sourcekit_lsp_available"], bool), (
        "sourcekit_lsp_available should be boolean"
    )
    assert isinstance(environment["python_version"], str), "python_version should be string"


def test_status_indicators_validation(environment_check_result):
    """
    Original Test 3: Verifies that the result includes proper boolean status indicators.
    Updated for macOS-only requirement.
    """
    # Skip validation on non-macOS since tool now requires macOS
    if sys.platform != "darwin":
        pytest.skip("Tool requires macOS - skipping status validation on non-macOS")

    # Check ready status
    assert isinstance(environment_check_result["ready"], bool), "Ready should be a boolean"

    # Check environment boolean fields
    environment = environment_check_result["environment"]
    assert isinstance(environment["xcrun_available"], bool), "xcrun_available should be boolean"
    assert isinstance(environment["sourcekit_lsp_available"], bool), (
        "sourcekit_lsp_available should be boolean"
    )


# Non-macOS test removed - tool now requires macOS only


def test_no_exceptions_on_run(environment_check_result):
    """
    Original Test 5: Ensures the tool runs without raising exceptions.
    Updated for macOS-only requirement.
    """
    # The presence of the result is the test.
    assert environment_check_result is not None

    # On macOS, should succeed. On non-macOS, should fail gracefully with clear error
    if sys.platform == "darwin":
        assert environment_check_result["success"] is True, (
            "Environment check should succeed on macOS even if tools unavailable"
        )
    else:
        assert environment_check_result["success"] is False, (
            "Environment check should fail on non-macOS with clear error message"
        )
        assert "requires macOS" in environment_check_result.get("error", ""), (
            "Non-macOS error should mention macOS requirement"
        )
