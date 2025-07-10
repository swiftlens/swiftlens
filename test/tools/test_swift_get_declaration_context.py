#!/usr/bin/env python3
"""
Test file for get_declaration_context tool using pytest.

This test validates the swift_get_declaration_context tool functionality with LSP.
"""

import os

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_declaration_context import swift_get_declaration_context

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result

# --- Fixtures ---


@pytest.fixture
def context_test_file(built_swift_environment):
    """
    Fixture that creates a Swift file with various nested symbols for declaration context testing.
    """
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

    struct Address {
        let street: String
        let city: String

        func isValid() -> Bool {
            return !street.isEmpty && !city.isEmpty
        }
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

    class DatabaseManager {
        static let shared = DatabaseManager()

        func save(_ data: Any) {
            // Save implementation
        }
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

enum UserRole {
    case admin
    case user
    case guest

    var description: String {
        switch self {
        case .admin: return "Administrator"
        case .user: return "User"
        case .guest: return "Guest"
        }
    }
}
"""
    return create_swift_file(swift_content, "TestFile.swift")


# --- Test Cases ---


@pytest.mark.lsp
def test_valid_swift_file_with_nested_symbols(context_test_file):
    """
    Covers original test 1.
    Tests declaration context extraction for valid Swift file with nested symbols.
    """
    result = swift_get_declaration_context(context_test_file)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "file_path" in result, "Result should have 'file_path' field"
    assert "declarations" in result, "Result should have 'declarations' field"
    assert "declaration_count" in result, "Result should have 'declaration_count' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Verify file path
    assert result["file_path"] == context_test_file

    # Check declarations content
    declarations = result["declarations"]
    assert isinstance(declarations, list), "Declarations should be a list"
    assert result["declaration_count"] == len(declarations), (
        "Declaration count should match list length"
    )

    # Check for main symbol types - at least some should be present
    main_symbols = ["User", "UserService", "ContentView", "UserRole"]
    declarations_text = " ".join(declarations)
    found_symbols = [symbol for symbol in main_symbols if symbol in declarations_text]

    assert len(found_symbols) >= 2, (
        f"Expected at least 2 main symbols, but only found: {found_symbols} in declarations: {declarations}"
    )


@pytest.mark.lsp
def test_nonexistent_file():
    """
    Covers original test 2.
    Tests error handling for non-existent file.
    """
    result = swift_get_declaration_context("/path/that/does/not/exist.swift")

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "error" in result, "Result should have 'error' field for nonexistent file"
    assert "error_type" in result, "Result should have 'error_type' field"

    # Should be a validation failure
    assert result["success"] is False, "Should fail for nonexistent file"
    assert result["error_type"] == "file_not_found", (
        f"Expected file_not_found error, got: {result['error_type']}"
    )
    assert "not found" in result["error"].lower(), (
        f"Error message should mention file not found, got: {result['error']}"
    )


@pytest.mark.lsp
def test_non_swift_file(built_swift_environment):
    """
    Covers original test 3.
    Tests error handling for non-Swift file extension.
    """
    _, _, create_swift_file = built_swift_environment
    non_swift_file = create_swift_file("This is not Swift code", "test.txt")

    result = swift_get_declaration_context(non_swift_file)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "error" in result, "Result should have 'error' field for non-Swift file"
    assert "error_type" in result, "Result should have 'error_type' field"

    # Should be a validation failure
    assert result["success"] is False, "Should fail for non-Swift file"
    assert result["error_type"] == "validation_error", (
        f"Expected validation_error, got: {result['error_type']}"
    )
    assert "swift file" in result["error"].lower(), (
        f"Error should mention Swift file requirement, got: {result['error']}"
    )


@pytest.mark.lsp
def test_relative_path_handling(built_swift_environment, monkeypatch):
    """
    Covers original test 4.
    Tests relative file path handling using monkeypatch for safety.
    """
    project_root, _, create_swift_file = built_swift_environment
    file_path = create_swift_file("struct TestSymbol { }", "RelativeTest.swift")

    # Safely change the current working directory for this test only
    monkeypatch.chdir(project_root)

    # Use relative path from project root
    relative_path = os.path.relpath(file_path, os.getcwd())
    result = swift_get_declaration_context(relative_path)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "declarations" in result, "Result should have 'declarations' field"
    assert "declaration_count" in result, "Result should have 'declaration_count' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Should work with relative path - either find symbols or return empty list
    declarations = result["declarations"]
    declarations_text = " ".join(declarations)
    assert "TestSymbol" in declarations_text or len(declarations) == 0, (
        f"Relative path should work and find TestSymbol or return empty, got: {declarations}"
    )


@pytest.mark.lsp
def test_empty_swift_file(built_swift_environment):
    """
    Covers original test 5.
    Tests handling of empty Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    empty_file = create_swift_file("", "Empty.swift")

    result = swift_get_declaration_context(empty_file)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "declarations" in result, "Result should have 'declarations' field"
    assert "declaration_count" in result, "Result should have 'declaration_count' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Empty file should return empty declarations list
    declarations = result["declarations"]
    assert isinstance(declarations, list), "Declarations should be a list"
    assert len(declarations) == 0, f"Empty file should have no declarations, got: {declarations}"
    assert result["declaration_count"] == 0, (
        f"Declaration count should be 0 for empty file, got: {result['declaration_count']}"
    )
