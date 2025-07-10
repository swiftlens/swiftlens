#!/usr/bin/env python3
"""
Test file for swift_summarize_file tool using pytest.

This test validates the swift_summarize_file tool functionality with LSP.
"""

import os
import time

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_summarize_file import swift_summarize_file

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result

# --- Fixtures ---


@pytest.fixture
def complex_swift_file(built_swift_environment):
    """Complex Swift file with multiple symbol types."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation
import SwiftUI

struct User: Codable {
    let id: UUID
    var name: String
    var email: String

    init(name: String, email: String) {
        self.id = UUID()
        self.name = name
        self.email = email
    }

    func validateEmail() -> Bool {
        return email.contains("@")
    }

    static func createTestUser() -> User {
        return User(name: "Test", email: "test@example.com")
    }
}

class UserService: ObservableObject {
    @Published var users: [User] = []
    private let storage = UserDefaults.standard

    func addUser(_ user: User) {
        users.append(user)
        saveUsers()
    }

    private func saveUsers() {
        // Save implementation
    }

    class DatabaseManager {
        static let shared = DatabaseManager()
        private var cache: [String: Any] = [:]

        func save(_ data: Any) {
            // Save implementation
        }
    }
}

enum UserRole: String, CaseIterable {
    case admin = "admin"
    case user = "user"
    case guest = "guest"

    var displayName: String {
        switch self {
        case .admin: return "Administrator"
        case .user: return "User"
        case .guest: return "Guest"
        }
    }
}

protocol UserProtocol {
    var id: UUID { get }
    func validateEmail() -> Bool
}

extension User: UserProtocol {
    // Already conforms
}
"""
    return create_swift_file(swift_content, "ComplexFile.swift")


# --- Test Cases ---


@pytest.mark.lsp
def test_complex_swift_file_analysis(complex_swift_file):
    """
    Covers original test 1.
    Tests analysis of complex Swift file with multiple symbol types.
    """
    result = swift_summarize_file(complex_swift_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Debug print result
    print(f"DEBUG Result: {result}")

    # Use standardized error handling
    handle_tool_result(result)

    # Should contain symbol counts
    symbol_counts = result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)

    assert total_symbols > 0, f"Expected symbols in complex file, got: {symbol_counts}"
    assert len(symbol_counts) > 0, f"Expected symbol types in complex file, got: {symbol_counts}"


@pytest.mark.lsp
def test_empty_swift_file(built_swift_environment):
    """
    Covers original test 2.
    Tests handling of empty Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    empty_file = create_swift_file("", "Empty.swift")

    result = swift_summarize_file(empty_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Empty file should have zero symbols
    symbol_counts = result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)

    assert total_symbols == 0, f"Expected no symbols in empty file, got: {total_symbols}"
    assert len(symbol_counts) == 0, f"Expected no symbol types in empty file, got: {symbol_counts}"


@pytest.mark.lsp
def test_simple_swift_file(built_swift_environment):
    """
    Covers original test 3.
    Tests analysis of simple Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    simple_content = """func hello() {
    print("Hello World")
}

let greeting = "Hello"
"""
    simple_file = create_swift_file(simple_content, "Simple.swift")

    result = swift_summarize_file(simple_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Should find at least the function or variable
    symbol_counts = result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)

    assert total_symbols > 0, f"Expected symbols in simple file, got: {symbol_counts}"


@pytest.mark.lsp
def test_nonexistent_file():
    """
    Covers original test 4.
    Tests error handling for non-existent file.
    """
    result = swift_summarize_file("/path/that/does/not/exist.swift")

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure for non-existent file, got: {result}"

    error_msg = result.get("error", "")
    assert "not found" in error_msg or "does not exist" in error_msg, (
        f"Expected file not found error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_non_swift_file(built_swift_environment):
    """
    Covers original test 5.
    Tests error handling for non-Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    non_swift_file = create_swift_file("Not Swift code", "test.txt")

    result = swift_summarize_file(non_swift_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure for non-Swift file, got: {result}"

    error_msg = result.get("error", "")
    assert "Swift file" in error_msg or "extension" in error_msg, (
        f"Expected Swift file extension error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_malformed_swift_file(built_swift_environment):
    """
    Covers original test 6.
    Tests handling of malformed Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    malformed_content = """struct Broken {
    let incomplete
    func missing_brace() {
    // Missing closing brace
"""
    malformed_file = create_swift_file(malformed_content, "Malformed.swift")

    result = swift_summarize_file(malformed_file)

    # LSP should handle malformed files gracefully - either return error or partial results
    assert isinstance(result, dict), f"Expected dict result for malformed file, got: {type(result)}"


@pytest.mark.lsp
def test_deeply_nested_symbols(built_swift_environment):
    """
    Covers original test 7.
    Tests handling of deeply nested symbols.
    """
    _, _, create_swift_file = built_swift_environment
    nested_content = """struct Level1 {
    struct Level2 {
        struct Level3 {
            struct Level4 {
                func deepMethod() { }
            }
        }
    }
}"""
    nested_file = create_swift_file(nested_content, "DeepNested.swift")

    result = swift_summarize_file(nested_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Should handle deep nesting without crashing
    result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)
    assert total_symbols >= 0, f"Expected valid symbol count, got: {total_symbols}"


@pytest.mark.lsp
def test_unicode_symbols(built_swift_environment):
    """
    Covers original test 8.
    Tests handling of Unicode symbols.
    """
    _, _, create_swift_file = built_swift_environment
    unicode_content = """struct 用户 {
    let 名字: String
    func 验证() -> Bool { return true }
}

class 🚀RocketService {
    func 🌟starMethod() { }
}"""
    unicode_file = create_swift_file(unicode_content, "Unicode.swift")

    result = swift_summarize_file(unicode_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Should handle Unicode symbols
    result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)
    assert total_symbols >= 0, f"Expected valid symbol count, got: {total_symbols}"


@pytest.mark.lsp
def test_large_file_performance(built_swift_environment):
    """
    Covers original test 9.
    Tests performance with larger Swift file.
    """
    _, _, create_swift_file = built_swift_environment

    # Generate a larger file with many symbols
    large_content = "import Foundation\n\n"
    for i in range(50):
        large_content += f"""
struct TestStruct{i} {{
    let property{i}: String
    func method{i}() -> Int {{ return {i} }}
}}
"""

    large_file = create_swift_file(large_content, "LargeFile.swift")

    start_time = time.time()
    result = swift_summarize_file(large_file)
    duration = time.time() - start_time

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Should process in reasonable time (less than 10 seconds)
    assert duration < 10.0, f"Large file processing took too long: {duration:.2f}s"
    result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)
    assert total_symbols > 0, f"Expected symbols in large file, got: {total_symbols}"


@pytest.mark.lsp
def test_relative_path_handling(built_swift_environment, monkeypatch):
    """
    Covers original test 10.
    Tests relative file path handling.
    """
    project_root, _, create_swift_file = built_swift_environment
    file_path = create_swift_file("struct RelativeTest { }", "RelativeTest.swift")

    # Safely change working directory
    monkeypatch.chdir(project_root)

    relative_path = os.path.relpath(file_path, os.getcwd())
    result = swift_summarize_file(relative_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # Should work with relative path
    result.get("symbol_counts", {})
    total_symbols = result.get("total_symbols", 0)
    assert total_symbols >= 0, f"Expected valid symbol count, got: {total_symbols}"
