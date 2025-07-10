#!/usr/bin/env python3
"""
Test file for get_hover_info tool using pytest.

This test validates the swift_get_hover_info tool functionality with LSP.
"""

import os

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_hover_info import swift_get_hover_info

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result

# --- Fixtures ---


@pytest.fixture
def data_app_file(built_swift_environment):
    """
    Fixture that creates a Swift file with various typed symbols.
    """
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation
import SwiftUI

struct DataModel: Codable {
    let id: UUID
    var title: String
    var isCompleted: Bool
    var createdAt: Date

    init(title: String) {
        self.id = UUID()
        self.title = title
        self.isCompleted = false
        self.createdAt = Date()
    }

    func markCompleted() -> DataModel {
        var updated = self
        updated.isCompleted = true
        return updated
    }
}

class DataService: ObservableObject {
    @Published var items: [DataModel] = []
    private let storage = UserDefaults.standard

    init() {
        loadItems()
    }

    func addItem(title: String) {
        let newItem = DataModel(title: title)
        items.append(newItem)
        saveItems()
    }

    func toggleItem(at index: Int) {
        guard index < items.count else { return }
        items[index] = items[index].markCompleted()
        saveItems()
    }

    private func loadItems() {
        // Load implementation
    }

    private func saveItems() {
        // Save implementation
    }
}

struct ContentView: View {
    @StateObject private var dataService = DataService()
    @State private var newItemTitle = ""

    var body: some View {
        NavigationView {
            VStack {
                HStack {
                    TextField("New item", text: $newItemTitle)
                        .textFieldStyle(RoundedBorderTextFieldStyle())

                    Button("Add") {
                        dataService.addItem(title: newItemTitle)
                        newItemTitle = ""
                    }
                    .disabled(newItemTitle.isEmpty)
                }
                .padding()

                List {
                    ForEach(dataService.items.indices, id: \\.self) { index in
                        HStack {
                            Text(dataService.items[index].title)
                            Spacer()
                            Button(dataService.items[index].isCompleted ? "✓" : "○") {
                                dataService.toggleItem(at: index)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Items")
        }
    }
}

// Generic function for testing hover info
func processData<T: Codable>(_ data: T) -> String {
    return String(describing: data)
}

func processDataWithMultipleConstraints<T: Codable & Equatable, U: Hashable>(_ data: T, key: U) -> [U: String] {
    return [key: String(describing: data)]
}
"""
    return create_swift_file(swift_content, "DataApp.swift")


# --- Test Cases ---


@pytest.mark.lsp
@pytest.mark.parametrize(
    "line, char, expected_keywords, test_name",
    [
        # Test 1: Hover info for DataModel struct (line 4, struct name at char 8)
        (4, 8, ["DataModel", "struct"], "struct-DataModel"),
        # Test 2: Hover info for typed property 'id' (line 5, id at char 9)
        (5, 9, ["id", "UUID"], "property-id"),
        # Test 3: Hover info for function 'markCompleted' (line 17)
        (17, 10, ["markCompleted", "func"], "function-markCompleted"),
        # Test 4: Hover info for class 'DataService' (line 24)
        (24, 7, ["DataService", "class"], "class-DataService"),
        # Test 5: Hover info for property 'items' (line 25)
        (25, 20, ["Published", "items"], "property-items"),
        # Test 6: Hover info for generic function 'processData' (line 90)
        (90, 6, ["processData", "func"], "generic-function-processData"),
        # Test 7: Hover info for complex generic function (line 94)
        (
            94,
            6,
            ["processDataWithMultipleConstraints", "func"],
            "generic-function-complex",
        ),
    ],
)
def test_get_hover_info_for_symbols(data_app_file, line, char, expected_keywords, test_name):
    """
    Covers original tests 1-5.
    Validates hover information for various symbols in the test file.
    """
    result = swift_get_hover_info(data_app_file, line, char)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "file_path" in result, "Result should have 'file_path' field"
    assert "line" in result, "Result should have 'line' field"
    assert "character" in result, "Result should have 'character' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Verify input parameters were preserved
    assert result["file_path"] == data_app_file
    assert result["line"] == line
    assert result["character"] == char

    # Check hover info content
    hover_info = result.get("hover_info")
    if not hover_info:
        pytest.fail(
            f"LSP returned no hover information for {test_name} - this should not happen with a working LSP environment"
        )

    # If we got hover info, check for expected keywords
    has_expected_info = any(keyword in hover_info for keyword in expected_keywords)
    assert has_expected_info, (
        f"Expected hover info containing one of {expected_keywords}, but got: '{hover_info}'"
    )


@pytest.mark.lsp
def test_invalid_position(data_app_file):
    """
    Covers original test 6.
    Ensures that an out-of-bounds position is handled gracefully.
    """
    result = swift_get_hover_info(data_app_file, 1000, 1000)

    # Validate JSON structure
    assert isinstance(result, dict), f"Result should be a dictionary, got: {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert "file_path" in result, "Result should have 'file_path' field"
    assert "line" in result, "Result should have 'line' field"
    assert "character" in result, "Result should have 'character' field"

    # For an invalid position, we expect either:
    # 1. Success with no hover info
    # 2. LSP error (acceptable)
    if result["success"]:
        # Success with no hover info is acceptable
        assert result.get("hover_info") is None, "Invalid position should return no hover info"
    else:
        # LSP error is also acceptable for invalid positions
        assert result.get("error_type") == "lsp_error", (
            f"Expected LSP error for invalid position, got: {result}"
        )


@pytest.mark.lsp
def test_nonexistent_file():
    """
    Covers original test 7. This test does not need any fixtures.
    """
    result = swift_get_hover_info("/path/that/does/not/exist.swift", 1, 1)

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
    Covers original test 8.
    """
    _, _, create_swift_file = built_swift_environment
    non_swift_file = create_swift_file('{"test": "data"}', "data.json")

    result = swift_get_hover_info(non_swift_file, 1, 1)

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
