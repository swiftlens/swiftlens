#!/usr/bin/env python3
"""
Test file for swift_analyze_files tool - unified single/multiple file analysis

Usage: pytest test/tools/test_swift_analyze_files.py

This test validates the swift_analyze_files tool functionality with LSP.
"""

import os

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_analyze_files import swift_analyze_files

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result


@pytest.fixture
def single_swift_file(built_swift_environment):
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


# --- Test Cases for Single File Analysis ---


@pytest.mark.lsp
def test_single_valid_swift_file(single_swift_file):
    """Test analyzing a single Swift file (passed as a list with one item)."""
    result = swift_analyze_files([single_swift_file], allow_outside_cwd=True)

    # Validate response structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' field"
    assert "files" in result, "Result should have 'files' field"
    assert "total_files" in result, "Result should have 'total_files' field"
    assert "total_symbols" in result, "Result should have 'total_symbols' field"

    # Use standardized error handling
    handle_tool_result(result)

    # Validate single file result
    assert result["total_files"] == 1, "Should have analyzed 1 file"
    files = result["files"]
    assert single_swift_file in files, "Should have result for the input file"

    file_result = files[single_swift_file]
    # Debug output
    if not file_result["success"]:
        print(f"File analysis failed with error: {file_result.get('error', 'Unknown error')}")
        print(f"Error type: {file_result.get('error_type', 'Unknown')}")
    assert file_result["success"], "File analysis should succeed"
    symbols = file_result["symbols"]
    assert isinstance(symbols, list), "Symbols should be a list"

    if symbols:
        # Look for expected top-level symbols
        symbol_names = [symbol["name"] for symbol in symbols]
        assert "User" in symbol_names, "Should find User struct"
        assert "UserService" in symbol_names, "Should find UserService class"
        assert "ContentView" in symbol_names, "Should find ContentView struct"

        # Validate symbol structure and positions
        for symbol in symbols:
            assert isinstance(symbol, dict), "Each symbol should be a dictionary"
            assert "name" in symbol, "Symbol should have name"
            assert "kind" in symbol, "Symbol should have kind"
            assert "line" in symbol, "Symbol should have line"
            assert "character" in symbol, "Symbol should have character"
            # Check actual positions
            if symbol["name"] == "User":
                assert symbol["line"] == 4, f"User should be at line 4, not {symbol['line']}"
                assert symbol["character"] == 0, (
                    f"User should start at character 0, not {symbol['character']}"
                )
            elif symbol["name"] == "UserService":
                assert symbol["line"] == 14, (
                    f"UserService should be at line 14, not {symbol['line']}"
                )
                assert symbol["character"] == 0, (
                    f"UserService should start at character 0, not {symbol['character']}"
                )
            elif symbol["name"] == "ContentView":
                assert symbol["line"] == 26, (
                    f"ContentView should be at line 26, not {symbol['line']}"
                )
                assert symbol["character"] == 0, (
                    f"ContentView should start at character 0, not {symbol['character']}"
                )


@pytest.mark.lsp
def test_symbol_line_positions_accuracy(single_swift_file):
    """Test that symbol line positions are accurately reported."""
    result = swift_analyze_files([single_swift_file], allow_outside_cwd=True)
    handle_tool_result(result)

    file_result = result["files"][single_swift_file]
    symbols = file_result["symbols"]

    # Build maps of symbol names to their reported positions
    symbol_positions = {
        symbol["name"]: {"line": symbol["line"], "character": symbol["character"]}
        for symbol in symbols
    }

    # Verify specific symbol positions based on the test file content
    expected_positions = {
        "User": {"line": 4, "character": 0},  # struct User is on line 4, column 0
        "UserService": {"line": 14, "character": 0},  # class UserService is on line 14, column 0
        "ContentView": {"line": 26, "character": 0},  # struct ContentView is on line 26, column 0
    }

    for symbol_name, expected_pos in expected_positions.items():
        assert symbol_name in symbol_positions, f"Should find {symbol_name} symbol"
        actual_pos = symbol_positions[symbol_name]
        assert actual_pos["line"] == expected_pos["line"], (
            f"{symbol_name} should be at line {expected_pos['line']}, but found at line {actual_pos['line']}"
        )
        assert actual_pos["character"] == expected_pos["character"], (
            f"{symbol_name} should be at character {expected_pos['character']}, but found at character {actual_pos['character']}"
        )


# --- Test Cases for Multiple File Analysis ---


@pytest.mark.lsp
def test_multiple_valid_swift_files(multiple_swift_files):
    """Tests analyzing multiple valid Swift files."""
    result = swift_analyze_files(multiple_swift_files, allow_outside_cwd=True)

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
        f"Total files should be {len(multiple_swift_files)}"
    )

    # Check that we have results for all files
    for file_path in multiple_swift_files:
        assert file_path in files, f"Should have result for {file_path}"
        file_result = files[file_path]

        # Each file result should have the expected structure
        assert "success" in file_result, f"File result for {file_path} should have 'success' field"
        assert "file_path" in file_result, (
            f"File result for {file_path} should have 'file_path' field"
        )
        assert "symbols" in file_result, f"File result for {file_path} should have 'symbols' field"
        assert "symbol_count" in file_result, (
            f"File result for {file_path} should have 'symbol_count' field"
        )

        if file_result["success"]:
            symbols = file_result["symbols"]
            assert isinstance(symbols, list), f"Symbols for {file_path} should be a list"
            assert len(symbols) == file_result["symbol_count"], (
                f"Symbol count for {file_path} should match list length"
            )

    # Verify that total_symbols is the sum of all file symbol counts
    expected_total = sum(
        files[f]["symbol_count"] for f in multiple_swift_files if files[f]["success"]
    )
    assert result["total_symbols"] == expected_total, (
        f"Total symbols ({result['total_symbols']}) should equal sum of file counts ({expected_total})"
    )

    # Check for expected symbols in specific files
    # Product.swift should have Product struct and Category enum
    product_file = multiple_swift_files[0]
    product_symbols = [s["name"] for s in files[product_file]["symbols"]]
    assert "Product" in product_symbols, "Should find Product struct"
    assert "Category" in product_symbols, "Should find Category enum"

    # ProductService.swift should have protocol and class
    service_file = multiple_swift_files[1]
    service_symbols = [s["name"] for s in files[service_file]["symbols"]]
    assert "ProductServiceProtocol" in service_symbols, "Should find ProductServiceProtocol"
    assert "ProductService" in service_symbols, "Should find ProductService class"

    # ProductListView.swift should have both views
    view_file = multiple_swift_files[2]
    view_symbols = [s["name"] for s in files[view_file]["symbols"]]
    assert "ProductListView" in view_symbols, "Should find ProductListView struct"
    assert "ProductRowView" in view_symbols, "Should find ProductRowView struct"


@pytest.mark.lsp
def test_mixed_valid_and_invalid_files(multiple_swift_files):
    """Test analyzing a mix of valid and non-existent files."""
    # Add a non-existent file to the list
    non_existent = "/tmp/does_not_exist.swift"
    file_list = multiple_swift_files + [non_existent]

    result = swift_analyze_files(file_list, allow_outside_cwd=True)

    # Should still get a successful response
    handle_tool_result(result)

    files = result["files"]
    assert len(files) == len(file_list), "Should have results for all files"

    # Check valid files have successful results
    for file_path in multiple_swift_files:
        assert files[file_path]["success"], f"{file_path} should be analyzed successfully"

    # Check non-existent file has error
    assert not files[non_existent]["success"], "Non-existent file should fail"
    assert "error" in files[non_existent], "Failed file should have error message"
    assert files[non_existent]["error_type"] == "file_not_found", "Should have FILE_NOT_FOUND error"


def test_empty_file_list():
    """Test analyzing an empty list of files."""
    result = swift_analyze_files([])

    assert not result["success"], "Empty list should fail"
    assert "error" in result, "Should have error message"
    assert result["error_type"] == "validation_error", "Should have VALIDATION_ERROR"
    assert result["total_files"] == 0, "Should have 0 total files"
    assert result["total_symbols"] == 0, "Should have 0 total symbols"


def test_non_list_input():
    """Test that non-list input is properly rejected at server level."""
    # This test would be handled by the server.py validation
    # The tool itself expects a list, so we test with invalid list contents
    result = swift_analyze_files(None)  # type: ignore

    # Should handle gracefully
    assert not result["success"], "None input should fail"
    assert "error" in result, "Should have error message"


def test_non_swift_files(tmp_path):
    """Test analyzing non-Swift files."""
    # Create a non-Swift file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("This is not a Swift file")

    result = swift_analyze_files([str(txt_file)], allow_outside_cwd=True)

    # Should get a response with error for the file
    print(f"Result: {result}")
    assert result["success"], "Overall operation should succeed"
    files = result["files"]
    assert str(txt_file) in files, "Should have result for the file"

    file_result = files[str(txt_file)]
    assert not file_result["success"], "Non-Swift file should fail"
    assert "error" in file_result, "Should have error message"
    assert file_result["error_type"] == "validation_error", "Should have VALIDATION_ERROR"


@pytest.mark.lsp
def test_symbol_hierarchy_preservation(single_swift_file):
    """Test that nested symbol hierarchies are preserved."""
    result = swift_analyze_files([single_swift_file], allow_outside_cwd=True)
    handle_tool_result(result)

    file_result = result["files"][single_swift_file]
    symbols = file_result["symbols"]

    # Find the User struct
    user_struct = next((s for s in symbols if s["name"] == "User"), None)
    assert user_struct is not None, "Should find User struct"

    # Check for nested symbols (properties and methods)
    if "children" in user_struct:
        children = user_struct["children"]
        child_names = [child["name"] for child in children]

        # Should have properties and methods
        assert "id" in child_names, "Should find id property"
        assert "name" in child_names, "Should find name property"
        assert "email" in child_names, "Should find email property"
        assert "validateEmail()" in child_names, "Should find validateEmail method"

        # Comprehensive character position validation for nested symbols
        child_map = {child["name"]: child for child in children}

        # Validate character positions for properties (indented by 4 spaces)
        # Line numbers adjusted for actual content: User struct starts at line 4
        assert child_map["id"]["line"] == 5, (
            f"id property should be at line 5, got {child_map['id']['line']}"
        )
        assert child_map["id"]["character"] == 4, (
            f"id property should start at character 4 (after 4 spaces), got {child_map['id']['character']}"
        )

        assert child_map["name"]["line"] == 6, (
            f"name property should be at line 6, got {child_map['name']['line']}"
        )
        assert child_map["name"]["character"] == 4, (
            f"name property should start at character 4 (after 4 spaces), got {child_map['name']['character']}"
        )

        assert child_map["email"]["line"] == 7, (
            f"email property should be at line 7, got {child_map['email']['line']}"
        )
        assert child_map["email"]["character"] == 4, (
            f"email property should start at character 4 (after 4 spaces), got {child_map['email']['character']}"
        )

        # Validate character position for method
        assert child_map["validateEmail()"]["line"] == 9, (
            f"validateEmail() should be at line 9, got {child_map['validateEmail()']['line']}"
        )
        assert child_map["validateEmail()"]["character"] == 4, (
            f"validateEmail() should start at character 4 (after 4 spaces), got {child_map['validateEmail()']['character']}"
        )

    # Test UserService class nested symbols
    user_service = next((s for s in symbols if s["name"] == "UserService"), None)
    assert user_service is not None, "Should find UserService class"

    if "children" in user_service:
        service_children = user_service["children"]
        service_child_map = {child["name"]: child for child in service_children}

        # UserService starts at line 14, so its children are offset from there
        assert "users" in service_child_map, "Should find users property"
        assert service_child_map["users"]["line"] == 15, (
            f"users property should be at line 15, got {service_child_map['users']['line']}"
        )
        assert service_child_map["users"]["character"] == 4, (
            f"users property should start at character 4 (after 4 spaces), got {service_child_map['users']['character']}"
        )

        assert "addUser(_:)" in service_child_map, "Should find addUser method"
        assert service_child_map["addUser(_:)"]["line"] == 17, (
            f"addUser(_:) should be at line 17, got {service_child_map['addUser(_:)']['line']}"
        )
        assert service_child_map["addUser(_:)"]["character"] == 4, (
            f"addUser(_:) should start at character 4 (after 4 spaces), got {service_child_map['addUser(_:)']['character']}"
        )

        assert "fetchUser(by:)" in service_child_map, "Should find fetchUser method"
        assert service_child_map["fetchUser(by:)"]["line"] == 21, (
            f"fetchUser(by:) should be at line 21, got {service_child_map['fetchUser(by:)']['line']}"
        )
        assert service_child_map["fetchUser(by:)"]["character"] == 4, (
            f"fetchUser(by:) should start at character 4 (after 4 spaces), got {service_child_map['fetchUser(by:)']['character']}"
        )


@pytest.mark.performance
@pytest.mark.lsp
def test_performance_with_many_files(built_swift_environment):
    """Test performance with a larger number of files."""
    _, _, create_swift_file = built_swift_environment

    # Create 10 Swift files
    swift_files = []
    for i in range(10):
        content = f"""
import Foundation

struct Model{i} {{
    let id: String
    var value: Int

    func process() -> Int {{
        return value * {i + 1}
    }}
}}

class Service{i} {{
    func fetchData() -> Model{i}? {{
        return nil
    }}
}}
"""
        file_path = create_swift_file(content, f"Model{i}.swift")
        swift_files.append(file_path)

    # Analyze all files
    import time

    start_time = time.time()
    result = swift_analyze_files(swift_files, allow_outside_cwd=True)
    end_time = time.time()

    # Should complete successfully
    handle_tool_result(result)
    assert result["total_files"] == 10, "Should analyze all 10 files"

    # Performance check - should complete in reasonable time
    elapsed = end_time - start_time
    assert elapsed < 30, f"Should complete within 30 seconds, took {elapsed:.2f}s"

    # Verify parallel processing worked
    print(f"Analyzed {len(swift_files)} files in {elapsed:.2f} seconds")
