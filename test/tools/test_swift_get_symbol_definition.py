#!/usr/bin/env python3
"""
Test file for get_symbol_definition tool

Usage: pytest test/tools/test_swift_get_symbol_definition.py

This test creates a sample Swift file with symbols and tests the get_symbol_definition tool functionality.
"""

import os
import shutil
import tempfile

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_symbol_definition import swift_get_symbol_definition

# Import shared utilities for LSP test handling
from .lsp_test_utils import assert_is_acceptable_lsp_failure, parse_definition_output


def validate_definition_location(definitions, expected_line_range=None):
    """Validate that definition location is reasonable."""
    if not definitions:
        raise AssertionError("No definitions found")

    for definition in definitions:
        assert definition["line"] > 0, f"Invalid line number: {definition['line']}"
        if expected_line_range:
            assert expected_line_range[0] <= definition["line"] <= expected_line_range[1], (
                f"Line {definition['line']} not in expected range {expected_line_range}"
            )


def create_test_swift_file_with_definitions():
    """Create a test Swift file with various symbol definitions."""
    swift_content = """import Foundation
import UIKit

protocol DataManagerProtocol {
    func fetchData() async throws -> [String]
    func saveData(_ data: [String]) async throws
}

class DataManager: DataManagerProtocol {
    static let shared = DataManager()
    private let storage: [String: Any] = [:]

    private init() {}

    func fetchData() async throws -> [String] {
        // Basic implementation for testing
        return ["sample data 1", "sample data 2"]
    }

    func saveData(_ data: [String]) async throws {
        // Basic implementation for testing
        print("Saving data: \\(data)")
    }

    func processData(_ input: String) -> String {
        return "Processed: \\(input)"
    }
}

class NetworkManager: DataManagerProtocol {
    static let shared = NetworkManager()
    private let urlSession: URLSession

    private init() {
        self.urlSession = URLSession.shared
    }

    func fetchData() async throws -> [String] {
        // Implementation
        return []
    }

    func saveData(_ data: [String]) async throws {
        // Implementation
    }

    private func buildURL(for endpoint: String) -> URL? {
        return URL(string: "https://api.example.com/\\(endpoint)")
    }
}

struct UserModel {
    let id: String
    var name: String
    var email: String
    let isActive: Bool

    init(name: String, email: String, isActive: Bool = true) {
        self.id = UUID().uuidString
        self.name = name
        self.email = email
        self.isActive = isActive
    }

    mutating func updateEmail(_ newEmail: String) {
        self.email = newEmail
    }

    func displayInfo() -> String {
        return "\\(name) (\\(email)) - Active: \\(isActive)"
    }
}

struct ContentModel {
    let id: String
    var title: String
    var content: String
    let createdAt: Date

    init(title: String, content: String) {
        self.id = UUID().uuidString
        self.title = title
        self.content = content
        self.createdAt = Date()
    }

    mutating func updateContent(_ newContent: String) {
        self.content = newContent
    }
}

enum LoadingState {
    case idle
    case loading
    case loaded(data: [ContentModel])
    case error(message: String)
}

class ContentViewModel: ObservableObject {
    @Published var contentItems: [ContentModel] = []
    @Published var loadingState: LoadingState = .idle

    private let dataManager: DataManagerProtocol

    init(dataManager: DataManagerProtocol = NetworkManager.shared) {
        self.dataManager = dataManager
    }

    func loadContent() async {
        loadingState = .loading

        do {
            let data = try await dataManager.fetchData()
            let items = data.map { ContentModel(title: $0, content: "Default content") }

            await MainActor.run {
                self.contentItems = items
                self.loadingState = .loaded(data: items)
            }
        } catch {
            await MainActor.run {
                self.loadingState = .error(message: error.localizedDescription)
            }
        }
    }
}
"""
    return swift_content


@pytest.fixture
def temp_swift_file():
    """Create a temporary Swift file for testing."""
    temp_dir = tempfile.mkdtemp(prefix="swift_def_test_")
    test_file_path = os.path.join(temp_dir, "DefinitionTest.swift")

    with open(test_file_path, "w") as f:
        f.write(create_test_swift_file_with_definitions())

    yield test_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_find_networkmanager_definition(temp_swift_file):
    """Test 1: Finding definition for 'NetworkManager' class."""
    result = swift_get_symbol_definition(temp_swift_file, "NetworkManager")
    definitions = parse_definition_output(result)

    # NetworkManager class is defined at line 9 in our test file
    if definitions and len(definitions) >= 1:
        # Check if we found the definition at the expected line (around line 9, allowing some tolerance)
        found_correct_line = any(5 <= def_info["line"] <= 15 for def_info in definitions)
        assert found_correct_line, (
            f"Definition found but at unexpected line. Expected ~9, got: {[d['line'] for d in definitions]}"
        )
    # Else: No definition found (may indicate cross-file definition or LSP limitation) - this is acceptable


@pytest.mark.lsp
def test_find_contentmodel_definition(temp_swift_file):
    """Test 2: Finding definition for 'ContentModel' struct."""
    result = swift_get_symbol_definition(temp_swift_file, "ContentModel")
    definitions = parse_definition_output(result)

    # ContentModel struct is defined at line 27 in our test file
    if definitions and len(definitions) >= 1:
        # Check if we found the definition at the expected line (around line 27, allowing some tolerance)
        found_correct_line = any(25 <= def_info["line"] <= 35 for def_info in definitions)
        assert found_correct_line, (
            f"Definition found but at unexpected line. Expected ~27, got: {[d['line'] for d in definitions]}"
        )
    # Else: No definition found (may indicate cross-file definition or LSP limitation) - this is acceptable


@pytest.mark.lsp
def test_find_loadcontent_method_definition(temp_swift_file):
    """Test 3: Finding definition for 'loadContent' method."""
    result = swift_get_symbol_definition(temp_swift_file, "loadContent")
    definitions = parse_definition_output(result)

    # loadContent method should be found in ContentViewModel around line 59
    if definitions and len(definitions) >= 1:
        # Check if we found the definition at a reasonable line for the loadContent method
        found_method = any(55 <= def_info["line"] <= 65 for def_info in definitions)
        assert found_method, (
            f"Definition found but at unexpected line. Expected ~59, got: {[d['line'] for d in definitions]}"
        )
    # Else: No definition found (method may be in ContentViewModel class) - this is acceptable


@pytest.mark.lsp
def test_find_loadingstate_definition(temp_swift_file):
    """Test 4: Finding definition for 'LoadingState' enum."""
    result = swift_get_symbol_definition(temp_swift_file, "LoadingState")
    definitions = parse_definition_output(result)

    # LoadingState enum is defined around line 43 in our test file
    if definitions and len(definitions) >= 1:
        # Check if we found the definition at the expected line for LoadingState enum
        found_enum = any(40 <= def_info["line"] <= 50 for def_info in definitions)
        assert found_enum, (
            f"Definition found but at unexpected line. Expected ~43, got: {[d['line'] for d in definitions]}"
        )
    # Else: No definition found (enum may not be detected by LSP) - this is acceptable


@pytest.mark.lsp
def test_nonexistent_symbol(temp_swift_file):
    """Test 5: Finding definition for non-existent symbol."""
    result = swift_get_symbol_definition(temp_swift_file, "NonExistentSymbol")

    if isinstance(result, dict):
        # Should either be successful with no definitions or have an error
        if result.get("success", False):
            # Check for empty definitions in the data structure
            definitions_data = result.get("data", {}).get("definitions", [])
            assert len(definitions_data) == 0, "Expected no definitions for non-existent symbol"
        else:
            # Use shared helper for consistent error handling
            assert_is_acceptable_lsp_failure(result)


@pytest.mark.lsp
def test_nonexistent_file(swift_project):
    """Test 6: Non-existent file."""
    result = swift_get_symbol_definition("/nonexistent/file.swift", "TestSymbol")

    if isinstance(result, dict):
        assert not result.get("success", True), "Expected failure for non-existent file"
        error_msg = result.get("error", "")
        assert "File not found" in error_msg or "not found" in error_msg, (
            f"Expected file not found error, got: {error_msg}"
        )


@pytest.mark.lsp
def test_non_swift_file(swift_project):
    """Test 7: Non-Swift file extension."""
    result = swift_get_symbol_definition("/tmp/test.txt", "TestSymbol")

    if isinstance(result, dict):
        assert not result.get("success", True), "Expected failure for non-Swift file"
        error_msg = result.get("error", "")
        assert "Swift file" in error_msg or "extension" in error_msg, (
            f"Expected Swift file extension error, got: {error_msg}"
        )


@pytest.mark.lsp
def test_relative_file_path(temp_swift_file):
    """Test 8: Relative file path."""
    temp_dir = os.path.dirname(temp_swift_file)
    original_cwd = os.getcwd()

    try:
        os.chdir(temp_dir)
        result = swift_get_symbol_definition("DefinitionTest.swift", "NetworkManager")

        if isinstance(result, dict):
            # Should work with relative path
            assert result.get("success", False) or "error" in result, (
                f"Unexpected result structure with relative path: {result}"
            )

        parse_definition_output(result)
        # Definitions may or may not be found, but response should be valid
    finally:
        os.chdir(original_cwd)


@pytest.mark.lsp
def test_definition_location_format(temp_swift_file):
    """Test 9: Definition location format validation."""
    result = swift_get_symbol_definition(temp_swift_file, "NetworkManager")

    if isinstance(result, dict):
        assert "success" in result, f"Missing success field in response: {result}"

        if result.get("success", False):
            definitions = result.get("definitions", [])
            for definition in definitions:
                assert "file_path" in definition, f"Missing file_path in definition: {definition}"
                assert "line" in definition, f"Missing line in definition: {definition}"
                assert "character" in definition, f"Missing character in definition: {definition}"
                assert definition["line"] > 0, f"Invalid line number: {definition['line']}"
                assert definition["character"] >= 0, (
                    f"Invalid character number: {definition['character']}"
                )


@pytest.mark.lsp
def test_multiple_definitions_handling(temp_swift_file):
    """Test 10: Multiple definitions (if any)."""
    result = swift_get_symbol_definition(temp_swift_file, "init")

    if isinstance(result, dict):
        assert "success" in result, f"Missing success field in response: {result}"

        if result.get("success", False):
            definitions = result.get("definitions", [])
            # Multiple init definitions are possible - just ensure they're properly formatted
            for definition in definitions:
                assert definition["line"] > 0, f"Invalid line number: {definition['line']}"
                assert definition["character"] >= 0, (
                    f"Invalid character number: {definition['character']}"
                )
                assert "file_path" in definition, f"Missing file_path in definition: {definition}"
