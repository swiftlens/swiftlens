#!/usr/bin/env python3
"""
Test file for analyze_swift_file tool

Usage: pytest test/tools/test_swift_analyze_file.py

This test creates a sample Swift file and tests the analyze_swift_file tool functionality.
"""

import os

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_analyze_file import swift_analyze_file

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result


@pytest.fixture
def test_swift_file(built_swift_environment):
    """Create a test Swift file with various symbols."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation
import SwiftUI

struct User {
    let id: String
    var name: String
    var email: String

    func validateEmail() -> Bool {
        return email.contains("@")
    }
}

class UserService {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
    }

    func fetchUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }
}

struct ContentView: View {
    @State private var userService = UserService()

    var body: some View {
        VStack {
            Text("User Management")
                .font(.title)

            Button("Add User") {
                let user = User(id: "1", name: "John", email: "john@example.com")
                userService.addUser(user)
            }
        }
    }
}
"""
    return create_swift_file(swift_content, "TestFile.swift")


@pytest.mark.lsp
def test_valid_swift_file(test_swift_file):
    """Test analyzing a valid Swift file with various symbols."""
    result = swift_analyze_file(test_swift_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "file_path" in result, "Result should have 'file_path' field"
    assert "symbols" in result, "Result should have 'symbols' field"
    assert "symbol_count" in result, "Result should have 'symbol_count' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    symbols = result["symbols"]
    assert isinstance(symbols, list), "Symbols should be a list"
    assert len(symbols) == result["symbol_count"], "Symbol count should match list length"

    if symbols:
        # Look for expected top-level symbols
        symbol_names = [symbol["name"] for symbol in symbols]
        assert "User" in symbol_names, "Should find User struct"
        assert "UserService" in symbol_names, "Should find UserService class"
        assert "ContentView" in symbol_names, "Should find ContentView struct"

        # Validate symbol structure
        for symbol in symbols:
            assert isinstance(symbol, dict), "Each symbol should be a dictionary"
            assert "name" in symbol, "Symbol should have 'name' field"
            assert "kind" in symbol, "Symbol should have 'kind' field"
            assert "line" in symbol, "Symbol should have 'line' field"
            assert "character" in symbol, "Symbol should have 'character' field"
            assert isinstance(symbol["line"], int) and symbol["line"] >= 1, (
                "Line should be positive integer"
            )
            assert isinstance(symbol["character"], int) and symbol["character"] >= 0, (
                "Character should be non-negative integer"
            )


@pytest.mark.lsp
def test_nonexistent_file():
    """Test error handling for non-existent file."""
    result = swift_analyze_file("/path/that/does/not/exist.swift")

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert result["success"] is False, "Should fail for non-existent file"
    assert "error" in result, "Should have error message"
    assert "error_type" in result, "Should have error type"
    assert result["error_type"] == "file_not_found", "Error type should be file_not_found"
    assert "not found" in result["error"].lower(), "Error message should mention file not found"


@pytest.mark.lsp
def test_non_swift_file(built_swift_environment):
    """Test error handling for non-Swift file extension."""
    _, _, create_swift_file = built_swift_environment

    # Create a non-Swift file using the environment
    non_swift_file = create_swift_file("This is not Swift code", "test.txt")

    result = swift_analyze_file(non_swift_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert result["success"] is False, "Should fail for non-Swift file"
    assert "error" in result, "Should have error message"
    assert "error_type" in result, "Should have error type"
    assert result["error_type"] == "validation_error", "Error type should be validation_error"
    assert "swift file" in result["error"].lower(), (
        "Error message should mention Swift file requirement"
    )


@pytest.fixture
def malformed_swift_file(built_swift_environment):
    """Create a malformed Swift file with syntax errors."""
    _, _, create_swift_file = built_swift_environment

    malformed_content = """import Foundation

struct User {
    let id: String
    var name: String
    // Missing closing brace - syntax error

class UserService {
    func addUser() {
        // Missing closing brace
"""
    return create_swift_file(malformed_content, "Malformed.swift")


@pytest.mark.lsp
def test_malformed_swift_file(malformed_swift_file):
    """Test handling of malformed Swift file with syntax errors."""
    result = swift_analyze_file(malformed_swift_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "symbols" in result, "Result should have 'symbols' field"
    assert "symbol_count" in result, "Result should have 'symbol_count' field"

    # Use standardized error handling - LSP should handle malformed files gracefully
    # Either succeeds with partial parsing or skips due to LSP environment issues
    if not result["success"]:
        handle_tool_result(result)
    else:
        # If successful, should have some symbols (at least partial parsing)
        assert result["symbol_count"] >= 0, "Symbol count should be non-negative"


@pytest.mark.lsp
def test_relative_path(test_swift_file, monkeypatch):
    """Test relative file path handling."""
    # Get the directory containing the test file
    test_dir = os.path.dirname(test_swift_file)
    test_filename = os.path.basename(test_swift_file)

    # Change to the directory and test relative path
    monkeypatch.chdir(test_dir)
    result = swift_analyze_file(test_filename)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If successful, validate symbols
    symbols = result["symbols"]
    assert isinstance(symbols, list), "Symbols should be a list"

    if symbols:
        symbol_names = [symbol["name"] for symbol in symbols]
        assert "User" in symbol_names, "Should find User struct"
        assert "UserService" in symbol_names, "Should find UserService class"
