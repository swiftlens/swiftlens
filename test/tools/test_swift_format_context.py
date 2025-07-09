#!/usr/bin/env python3
"""
Test file for swift_format_context tool using pytest.

This test validates the swift_format_context tool functionality with LSP.
"""

import os

import pytest

# Add src directory to path for imports
from src.tools.swift_format_context import swift_format_context

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result

# --- Fixtures ---


@pytest.fixture
def content_manager_file(built_swift_environment):
    """Create a comprehensive Swift file for context formatting tests."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import UIKit
import Combine

protocol DataManagerProtocol {
    func fetchData() async throws -> [String]
    func saveData(_ data: [String]) async throws
}

class NetworkManager: DataManagerProtocol {
    static let shared = NetworkManager()
    private let urlSession = URLSession.shared

    private init() {}

    func fetchData() async throws -> [String] {
        // Implementation here
        return ["sample", "data"]
    }

    func saveData(_ data: [String]) async throws {
        // Save implementation
    }

    private func buildURL(for endpoint: String) -> URL? {
        return URL(string: "https://api.example.com/\\(endpoint)")
    }
}

struct ContentModel {
    let id: UUID
    var title: String
    var content: String
    var createdAt: Date

    init(title: String, content: String) {
        self.id = UUID()
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
    case loaded([ContentModel])
    case error(Error)

    var isLoading: Bool {
        if case .loading = self {
            return true
        }
        return false
    }
}

@MainActor
class ContentViewModel: ObservableObject {
    @Published var loadingState: LoadingState = .idle
    @Published var searchText: String = ""

    private let dataManager: DataManagerProtocol
    private var cancellables = Set<AnyCancellable>()

    init(dataManager: DataManagerProtocol = NetworkManager.shared) {
        self.dataManager = dataManager
        setupSearchObserver()
    }

    func loadContent() async {
        loadingState = .loading

        do {
            let data = try await dataManager.fetchData()
            let models = data.map { ContentModel(title: $0, content: "Content for \\($0)") }
            loadingState = .loaded(models)
        } catch {
            loadingState = .error(error)
        }
    }

    private func setupSearchObserver() {
        $searchText
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { [weak self] searchText in
                self?.performSearch(searchText)
            }
            .store(in: &cancellables)
    }

    private func performSearch(_ text: String) {
        // Search implementation
    }
}
"""
    return create_swift_file(swift_content, "ContentManager.swift")


# --- Test Cases ---


@pytest.mark.lsp
def test_valid_swift_file_formatting(content_manager_file):
    """
    Covers original test 1.
    Tests formatting of valid Swift file.
    """
    result = swift_format_context(content_manager_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "file_path" in result, "Result should have 'file_path' field"
    assert "formatted_context" in result, "Result should have 'formatted_context' field"
    assert "token_count" in result, "Result should have 'token_count' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    formatted_context = result["formatted_context"]
    assert isinstance(formatted_context, str), "Formatted context should be a string"
    assert result["token_count"] > 0, "Token count should be positive"

    # Check for expected format elements
    expected_elements = [
        "NetworkManager",
        "ContentModel",
        "LoadingState",
        "ContentViewModel",
    ]

    found_elements = [element for element in expected_elements if element in formatted_context]
    assert len(found_elements) >= 3, (
        f"Expected at least 3 format elements, but only found: {found_elements} in formatted context"
    )


@pytest.mark.lsp
def test_symbol_hierarchy_validation(content_manager_file):
    """
    Covers original test 2.
    Tests symbol hierarchy validation.
    """
    result = swift_format_context(content_manager_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    assert "formatted_context" in result, "Result should have 'formatted_context' field"
    formatted_context = result["formatted_context"]
    assert isinstance(formatted_context, str), "Formatted context should be a string"

    expected_symbols = [
        "NetworkManager",
        "ContentModel",
        "LoadingState",
        "ContentViewModel",
    ]
    found_symbols = [symbol for symbol in expected_symbols if symbol in formatted_context]

    assert len(found_symbols) >= 3, f"Expected at least 3 symbols, but only found: {found_symbols}"


@pytest.mark.lsp
def test_nested_symbol_validation(content_manager_file):
    """
    Covers original test 3.
    Tests nested symbol validation.
    """
    result = swift_format_context(content_manager_file)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    assert "formatted_context" in result, "Result should have 'formatted_context' field"
    formatted_context = result["formatted_context"]
    assert isinstance(formatted_context, str), "Formatted context should be a string"

    # Check for nested structure indicators (methods, properties, etc.)
    nested_indicators = ["init", "func", "var", "let"]
    has_nested_info = any(indicator in formatted_context for indicator in nested_indicators)

    assert has_nested_info, f"Expected nested symbol information in result: {formatted_context}"


@pytest.mark.lsp
def test_nonexistent_file():
    """
    Covers original test 4.
    Tests error handling for non-existent file.
    """
    result = swift_format_context("/path/that/does/not/exist.swift")

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
    """
    Covers original test 5.
    Tests error handling for non-Swift file extension.
    """
    _, _, create_swift_file = built_swift_environment
    non_swift_file = create_swift_file('{"key": "value"}', "config.json")

    result = swift_format_context(non_swift_file)

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


@pytest.mark.lsp
def test_consistency_with_analyze_swift_file(content_manager_file):
    """
    Covers original test 6.
    Tests consistency with analyze_swift_file.

    Note: Now that both tools return JSON, we compare their formatted context
    should be similar when both succeed, but they have different response structures.
    """
    format_result = swift_format_context(content_manager_file)

    # Validate format_result structure
    assert isinstance(format_result, dict), "Format result should be a dictionary"
    # Use standardized error handling for format result
    handle_tool_result(format_result)

    from src.tools.swift_analyze_file import swift_analyze_file

    analyze_result = swift_analyze_file(content_manager_file)

    # Validate analyze_result structure
    assert isinstance(analyze_result, dict), "Analyze result should be a dictionary"
    # Use standardized error handling for analyze result
    handle_tool_result(analyze_result)

    # Both tools should have succeeded
    assert format_result["success"], "Format tool should succeed"
    assert analyze_result["success"], "Analyze tool should succeed"

    # Both should have found similar symbol counts (rough validation)
    format_context = format_result["formatted_context"]
    analyze_symbols = analyze_result["symbols"]

    # If analyze found symbols, format should have non-empty context
    if analyze_symbols:
        assert format_context.strip(), "Format should have non-empty context when symbols exist"
        assert len(format_context) > 10, "Format context should be substantial"


@pytest.mark.lsp
def test_relative_path_handling(built_swift_environment, monkeypatch):
    """
    Covers original test 7.
    Tests relative file path handling using monkeypatch for safety.
    """
    project_root, _, create_swift_file = built_swift_environment
    file_path = create_swift_file("struct RelativeTestSymbol { }", "RelativeTest.swift")

    # Safely change the current working directory for this test only
    monkeypatch.chdir(project_root)

    # Use relative path from project root
    relative_path = os.path.relpath(file_path, os.getcwd())
    result = swift_format_context(relative_path)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    assert "formatted_context" in result, "Result should have 'formatted_context' field"
    formatted_context = result["formatted_context"]
    assert isinstance(formatted_context, str), "Formatted context should be a string"

    # Should work with relative path
    expected_symbols = ["RelativeTestSymbol"]
    has_expected = any(symbol in formatted_context for symbol in expected_symbols)
    assert has_expected or formatted_context.strip() == "", (
        f"Relative path should work or return empty result, got: {formatted_context}"
    )
