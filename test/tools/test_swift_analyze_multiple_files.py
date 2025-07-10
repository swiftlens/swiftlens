#!/usr/bin/env python3
"""
Test file for swift_analyze_multiple_files tool using pytest.

This test validates the swift_analyze_multiple_files tool functionality with LSP.
"""

import os

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_analyze_multiple_files import swift_analyze_multiple_files

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result

# --- Fixtures ---


@pytest.fixture
def multiple_swift_files(built_swift_environment):
    """Create multiple test Swift files with different structures."""
    _, _, create_swift_file = built_swift_environment

    # File 1: Model file
    model_content = """import Foundation

struct Product {
    let id: String
    var name: String
    var price: Double

    func formattedPrice() -> String {
        return String(format: "%.2f", price)
    }
}

enum Category {
    case electronics
    case clothing
    case books

    var displayName: String {
        switch self {
        case .electronics: return "Electronics"
        case .clothing: return "Clothing"
        case .books: return "Books"
        }
    }
}
"""

    # File 2: Service file
    service_content = """import Foundation

protocol ProductServiceProtocol {
    func fetchProducts() async -> [Product]
    func addProduct(_ product: Product) async
}

class ProductService: ProductServiceProtocol {
    private var products: [Product] = []

    func fetchProducts() async -> [Product] {
        return products
    }

    func addProduct(_ product: Product) async {
        products.append(product)
    }

    func searchProducts(by name: String) -> [Product] {
        return products.filter { $0.name.contains(name) }
    }
}
"""

    # File 3: View file
    view_content = """import SwiftUI

struct ProductListView: View {
    @StateObject private var service = ProductService()
    @State private var products: [Product] = []

    var body: some View {
        NavigationView {
            List(products, id: \\.id) { product in
                ProductRowView(product: product)
            }
            .navigationTitle("Products")
            .task {
                products = await service.fetchProducts()
            }
        }
    }
}

struct ProductRowView: View {
    let product: Product

    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(product.name)
                    .font(.headline)
                Text(product.formattedPrice())
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
    }
}
"""

    # Create the three test files
    product_file = create_swift_file(model_content, "Product.swift")
    service_file = create_swift_file(service_content, "ProductService.swift")
    view_file = create_swift_file(view_content, "ProductListView.swift")

    return [product_file, service_file, view_file]


# --- Test Cases ---


@pytest.mark.lsp
def test_multiple_valid_swift_files(multiple_swift_files):
    """
    Covers original test 1.
    Tests analyzing multiple valid Swift files.
    """
    result = swift_analyze_multiple_files(multiple_swift_files)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "files" in result, "Result should have 'files' field"
    assert "total_files" in result, "Result should have 'total_files' field"
    assert "total_symbols" in result, "Result should have 'total_symbols' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    files = result["files"]
    assert isinstance(files, dict), "Files should be a dictionary"
    assert result["total_files"] == len(multiple_swift_files), (
        "Total files should match input count"
    )

    # Check that all files were processed
    expected_count = len(multiple_swift_files)
    assert len(files) == expected_count, f"Expected {expected_count} files, got {len(files)}"

    # Verify each file has proper structure
    for _file_path, file_result in files.items():
        assert isinstance(file_result, dict), "Each file result should be a dictionary"
        assert "success" in file_result, "File result should have 'success' field"
        assert "symbols" in file_result, "File result should have 'symbols' field"
        assert "symbol_count" in file_result, "File result should have 'symbol_count' field"


@pytest.mark.lsp
def test_mix_valid_invalid_files(multiple_swift_files):
    """
    Covers original test 2.
    Tests mix of valid and invalid files.
    """
    mixed_files = multiple_swift_files + ["/path/that/does/not/exist.swift"]
    result = swift_analyze_multiple_files(mixed_files)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "files" in result, "Result should have 'files' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Should handle mix gracefully
    files = result["files"]
    assert isinstance(files, dict), "Files should be a dictionary"

    # Check that we processed all files including the non-existent one
    assert len(files) == len(mixed_files), "Should process all files including invalid ones"

    # Verify that non-existent file has error
    non_existent_file = "/path/that/does/not/exist.swift"
    if non_existent_file in files:
        non_existent_result = files[non_existent_file]
        assert not non_existent_result["success"], "Non-existent file should fail"
        assert non_existent_result["error_type"] == "file_not_found", (
            "Should have correct error type"
        )


@pytest.mark.lsp
def test_empty_file_list():
    """
    Covers original test 3.
    Tests empty file list handling.
    """
    result = swift_analyze_multiple_files([])

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert result["success"] is False, "Should fail for empty file list"
    assert "error" in result, "Should have error message"
    assert "error_type" in result, "Should have error type"
    assert result["error_type"] == "validation_error", "Error type should be validation_error"
    assert "no files" in result["error"].lower(), "Error message should mention no files"
    assert result["total_files"] == 0, "Total files should be 0"


@pytest.mark.lsp
def test_single_file_analysis(multiple_swift_files):
    """
    Covers original test 4.
    Tests single file analysis (edge case).
    """
    result = swift_analyze_multiple_files([multiple_swift_files[0]])

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "files" in result, "Result should have 'files' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Should work with single file
    files = result["files"]
    assert len(files) == 1, "Should process exactly one file"
    assert result["total_files"] == 1, "Total files should be 1"

    # Verify the single file result
    file_path = multiple_swift_files[0]
    assert file_path in files, "Input file should be in results"
    file_result = files[file_path]
    assert isinstance(file_result, dict), "File result should be a dictionary"


@pytest.mark.lsp
def test_non_swift_files_in_list(built_swift_environment):
    """
    Covers original test 5.
    Tests handling of non-Swift files in list.
    """
    _, _, create_swift_file = built_swift_environment

    # Create a valid Swift file and a non-Swift file
    swift_file = create_swift_file("struct TestStruct { }", "Test.swift")
    non_swift_file = create_swift_file("# This is not Swift", "README.md")

    mixed_types = [swift_file, non_swift_file]
    result = swift_analyze_multiple_files(mixed_types)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "files" in result, "Result should have 'files' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Should handle non-Swift files gracefully
    files = result["files"]
    assert len(files) == 2, "Should process both files"

    # Check non-Swift file handling
    if non_swift_file in files:
        non_swift_result = files[non_swift_file]
        assert not non_swift_result["success"], "Non-Swift file should fail"
        assert non_swift_result["error_type"] == "validation_error", "Should have validation error"
        assert "swift file" in non_swift_result["error"].lower(), (
            "Error should mention Swift file requirement"
        )

    # Check Swift file handling
    if swift_file in files:
        swift_result = files[swift_file]
        # Swift file might succeed or fail depending on LSP environment
        assert isinstance(swift_result, dict), "Swift file result should be a dictionary"
