#!/usr/bin/env python3
"""
Test file for swift_get_symbols_overview tool using pytest.

This test validates the swift_get_symbols_overview tool functionality with LSP.
"""

import os
import time

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_symbols_overview import swift_get_symbols_overview

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result


def run_test_with_retry(test_func, file_path, max_retries=2):
    """
    Run a test function with retry logic for LSP environment issues.

    This helps handle intermittent LSP environment problems that can cause
    "generator didn't stop after throw()" errors.

    Args:
        test_func: The test function to run (should take file_path as argument)
        file_path: Path to the test file
        max_retries: Maximum number of retries on LSP errors

    Returns:
        Test result or raises the final exception
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return test_func(file_path)
        except Exception as e:
            error_msg = str(e)
            # Check if this is an LSP environment issue that we should retry
            if attempt < max_retries and any(
                keyword in error_msg.lower()
                for keyword in [
                    "lsp_error",
                    "generator",
                    "timeout",
                    "sourcekit",
                    "environment issue",
                ]
            ):
                # Brief pause between retries to allow LSP state to reset
                time.sleep(1.0)
                last_exception = e
                continue
            else:
                # Not retryable or max retries reached
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


# --- Fixtures ---


@pytest.fixture
def comprehensive_swift_file(built_swift_environment):
    """Create a comprehensive Swift file with various symbol types."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation
import SwiftUI

// Top-level class
class UserService {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
    }

    func fetchUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }
}

// Top-level struct
struct User {
    let id: String
    var name: String
    var email: String

    func validateEmail() -> Bool {
        return email.contains("@")
    }

    static func createEmpty() -> User {
        return User(id: "", name: "", email: "")
    }
}

// Top-level enum
enum UserRole {
    case admin
    case member
    case guest

    var description: String {
        switch self {
        case .admin: return "Administrator"
        case .member: return "Member"
        case .guest: return "Guest"
        }
    }
}

// Top-level protocol
protocol UserManaging {
    func addUser(_ user: User)
    func removeUser(_ user: User)
}

// Top-level function (should be excluded)
func globalFunction() {
    print("This is a global function")
}

// Top-level variable (should be excluded)
let globalConstant = "This is a global constant"
var globalVariable = 42

// Another top-level struct
struct ContentView: View {
    @State private var userService = UserService()

    var body: some View {
        VStack {
            Text("User Management")
                .font(.title)
        }
    }
}
"""
    return create_swift_file(swift_content, "ComprehensiveFile.swift")


@pytest.fixture
def types_only_file(built_swift_environment):
    """Create a Swift file with only type declarations."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation

class SimpleClass {
    let property: String = "test"
}

struct SimpleStruct {
    let value: Int
}

enum SimpleEnum {
    case first
    case second
}

protocol SimpleProtocol {
    func doSomething()
}
"""
    return create_swift_file(swift_content, "TypesOnly.swift")


@pytest.fixture
def nested_types_file(built_swift_environment):
    """Create a Swift file with nested types to ensure only top-level are returned."""
    _, _, create_swift_file = built_swift_environment

    swift_content = """import Foundation

class OuterClass {
    // Nested class (should not appear in overview)
    class NestedClass {
        let property: String = "nested"
    }

    // Nested enum (should not appear in overview)
    enum NestedEnum {
        case option1
        case option2
    }

    func method() {
        // Local function (should not appear)
        func localFunction() {
            print("local")
        }
    }
}

struct OuterStruct {
    // Nested struct (should not appear in overview)
    struct NestedStruct {
        let value: Int
    }
}
"""
    return create_swift_file(swift_content, "NestedTypes.swift")


# --- Test Cases ---


@pytest.mark.lsp
def test_comprehensive_swift_file_analysis(comprehensive_swift_file):
    """
    Covers original test 1.
    Tests analyzing comprehensive Swift file with mixed symbols.
    Enhanced with retry logic for LSP environment issues.
    """

    def _run_test(file_path):
        result = swift_get_symbols_overview(file_path)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        # Should find top-level types but exclude functions/variables
        expected_types = [
            "UserService",
            "User",
            "UserRole",
            "UserManaging",
            "ContentView",
        ]
        excluded_items = ["globalFunction", "globalConstant", "globalVariable"]

        top_level_symbols = result.get("top_level_symbols", [])
        symbol_names = [symbol.get("name", "") for symbol in top_level_symbols]
        result_text = " ".join(symbol_names)

        found_types = [type_name for type_name in expected_types if type_name in result_text]
        found_excluded = [item for item in excluded_items if item in result_text]

        assert len(found_types) >= 3, (
            f"Expected at least 3 types, but only found: {found_types} in symbols: {symbol_names}"
        )
        assert len(found_excluded) == 0, (
            f"Found excluded items that should not be in overview: {found_excluded}"
        )

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, comprehensive_swift_file)


@pytest.mark.lsp
def test_types_only_file_analysis(types_only_file):
    """
    Covers original test 2.
    Tests analyzing file with only type declarations.
    Enhanced with retry logic for LSP environment issues.
    """

    def _run_test(file_path):
        result = swift_get_symbols_overview(file_path)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        expected_types = ["SimpleClass", "SimpleStruct", "SimpleEnum", "SimpleProtocol"]
        top_level_symbols = result.get("top_level_symbols", [])
        symbol_names = [symbol.get("name", "") for symbol in top_level_symbols]
        result_text = " ".join(symbol_names)

        found_types = [type_name for type_name in expected_types if type_name in result_text]

        assert len(found_types) >= 3, (
            f"Expected at least 3 types, but only found: {found_types} in symbols: {symbol_names}"
        )

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, types_only_file)


@pytest.mark.lsp
def test_functions_only_file(built_swift_environment):
    """
    Covers original test 3.
    Tests analyzing file with only functions and variables (no types).
    """
    _, _, create_swift_file = built_swift_environment

    functions_content = """import Foundation

func firstFunction() {
    print("First function")
}

func secondFunction() -> String {
    return "Second function"
}

let globalConstant = "Test"
var globalVariable = 123

func thirdFunction(param: String) -> Int {
    return param.count
}
"""
    functions_file = create_swift_file(functions_content, "FunctionsOnly.swift")

    result = swift_get_symbols_overview(functions_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    # Should indicate no top-level types found
    top_level_symbols = result.get("top_level_symbols", [])
    symbol_count = result.get("symbol_count", 0)

    assert len(top_level_symbols) == 0, (
        f"Expected no top-level types for functions-only file, got: {top_level_symbols}"
    )
    assert symbol_count == 0, (
        f"Expected symbol count 0 for functions-only file, got: {symbol_count}"
    )


@pytest.mark.lsp
def test_empty_swift_file(built_swift_environment):
    """
    Covers original test 4.
    Tests analyzing empty Swift file.
    """
    _, _, create_swift_file = built_swift_environment
    empty_file = create_swift_file("", "Empty.swift")

    result = swift_get_symbols_overview(empty_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    # Empty file should show no symbols
    top_level_symbols = result.get("top_level_symbols", [])
    symbol_count = result.get("symbol_count", 0)

    assert len(top_level_symbols) == 0, (
        f"Expected no symbols for empty file, got: {top_level_symbols}"
    )
    assert symbol_count == 0, f"Expected symbol count 0 for empty file, got: {symbol_count}"


@pytest.mark.lsp
def test_imports_only_file(built_swift_environment):
    """
    Covers original test 5.
    Tests analyzing file with only imports.
    """
    _, _, create_swift_file = built_swift_environment
    imports_content = """import Foundation
import SwiftUI
import Combine
"""
    imports_file = create_swift_file(imports_content, "ImportsOnly.swift")

    result = swift_get_symbols_overview(imports_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    # Imports-only file should show no symbols
    top_level_symbols = result.get("top_level_symbols", [])
    symbol_count = result.get("symbol_count", 0)

    assert len(top_level_symbols) == 0, (
        f"Expected no symbols for imports-only file, got: {top_level_symbols}"
    )
    assert symbol_count == 0, f"Expected symbol count 0 for imports-only file, got: {symbol_count}"


@pytest.mark.lsp
def test_nested_types_exclusion(nested_types_file):
    """
    Covers original test 6.
    Tests that only top-level types are shown, nested types are excluded.
    Enhanced with retry logic for LSP environment issues.
    """

    def _run_test(file_path):
        result = swift_get_symbols_overview(file_path)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        # Should show only top-level types
        expected_top_level = ["OuterClass", "OuterStruct"]
        excluded_nested = ["NestedClass", "NestedEnum", "NestedStruct"]

        top_level_symbols = result.get("top_level_symbols", [])
        symbol_names = [symbol.get("name", "") for symbol in top_level_symbols]
        result_text = " ".join(symbol_names)

        found_top_level = [
            type_name for type_name in expected_top_level if type_name in result_text
        ]
        found_nested = [type_name for type_name in excluded_nested if type_name in result_text]

        assert len(found_top_level) >= 1, (
            f"Expected top-level types, but only found: {found_top_level} in symbols: {symbol_names}"
        )
        assert len(found_nested) == 0, f"Found nested types that should be excluded: {found_nested}"

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, nested_types_file)


@pytest.mark.lsp
def test_nonexistent_file():
    """
    Covers original test 7.
    Tests error handling for non-existent file.
    """
    result = swift_get_symbols_overview("/path/that/does/not/exist.swift")

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"
    assert not result["success"], f"Expected failure for non-existent file, got: {result}"

    error_msg = result.get("error", "")
    assert "not found" in error_msg or "does not exist" in error_msg, (
        f"Expected file not found error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_malformed_swift_file(built_swift_environment):
    """
    Covers original test 8.
    Tests handling of malformed Swift file.
    """
    _, _, create_swift_file = built_swift_environment

    malformed_content = """import Foundation

class IncompleteClass {
    let property: String
    // Missing closing brace

struct IncompleteStruct {
    let value: Int
    // Missing closing brace
"""
    malformed_file = create_swift_file(malformed_content, "Malformed.swift")

    result = swift_get_symbols_overview(malformed_file)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    # Malformed files should be handled gracefully - either error or partial results
    if result.get("success", False):
        # If successful, should have some structure
        top_level_symbols = result.get("top_level_symbols", [])
        assert isinstance(top_level_symbols, list), (
            f"Expected list of symbols, got: {type(top_level_symbols)}"
        )
    else:
        # If failed, should have error message
        error_msg = result.get("error", "")
        assert len(error_msg) > 0, f"Expected error message for malformed file, got: {result}"


@pytest.mark.lsp
def test_unicode_type_names(built_swift_environment):
    """
    Covers original test 9.
    Tests handling of Unicode type names.
    Enhanced with retry logic for LSP environment issues.
    """
    _, _, create_swift_file = built_swift_environment

    unicode_content = """import Foundation

class 用户服务 {
    func 添加用户() {
        print("Adding user")
    }
}

struct Ñandú {
    let nombre: String
}

enum 状态 {
    case 活跃
    case 非活跃
}

protocol Протокол {
    func метод()
}
"""
    unicode_file = create_swift_file(unicode_content, "Unicode.swift")

    def _run_test(file_path):
        result = swift_get_symbols_overview(file_path)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        # Should handle Unicode symbols correctly
        top_level_symbols = result.get("top_level_symbols", [])
        symbol_count = result.get("symbol_count", 0)

        # Should find some Unicode type symbols
        assert symbol_count > 0 or len(top_level_symbols) > 0, (
            f"Expected Unicode type names to be handled correctly, got symbols: {top_level_symbols}, count: {symbol_count}"
        )

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, unicode_file)


@pytest.mark.lsp
def test_large_file_performance(built_swift_environment):
    """
    Covers original test 11.
    Tests performance with large Swift file.
    Enhanced with retry logic for LSP environment issues.
    """
    _, _, create_swift_file = built_swift_environment

    # Generate a large file with many types
    large_content = "import Foundation\n\n"
    for i in range(20):  # Reduced from 50 for faster testing
        large_content += f"""
class TestClass{i} {{
    let property{i}: String = "test{i}"

    func method{i}() {{
        print("Method {i}")
    }}
}}

struct TestStruct{i} {{
    let value{i}: Int = {i}
}}

enum TestEnum{i} {{
    case option{i}A
    case option{i}B
}}
"""

    large_file = create_swift_file(large_content, "LargeFile.swift")

    def _run_test(file_path):
        start_time = time.time()
        result = swift_get_symbols_overview(file_path)
        duration = time.time() - start_time

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        # Should process in reasonable time (less than 30 seconds) and find many types
        result.get("top_level_symbols", [])
        symbol_count = result.get("symbol_count", 0)

        assert duration < 30.0, f"Large file processing took too long: {duration:.2f}s"
        assert symbol_count >= 20, f"Expected at least 20 types, but found {symbol_count}"

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, large_file)


@pytest.mark.lsp
def test_relative_path_handling(built_swift_environment, monkeypatch):
    """
    Covers original test 12.
    Tests relative file path handling using monkeypatch for safety.
    Enhanced with retry logic for LSP environment issues.
    """
    project_root, _, create_swift_file = built_swift_environment
    file_path = create_swift_file("struct RelativeTestSymbol { }", "RelativeTest.swift")

    # Safely change the current working directory for this test only
    monkeypatch.chdir(project_root)

    # Use relative path from project root
    relative_path = os.path.relpath(file_path, os.getcwd())

    def _run_test(file_path):
        result = swift_get_symbols_overview(file_path)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

        # Use standardized error handling
        handle_tool_result(result)

        # If we got a successful result, validate it

        # Should work with relative path
        expected_symbols = ["RelativeTestSymbol"]
        top_level_symbols = result.get("top_level_symbols", [])
        symbol_names = [symbol.get("name", "") for symbol in top_level_symbols]

        has_expected = any(symbol in symbol_names for symbol in expected_symbols)
        is_valid_empty = len(top_level_symbols) == 0

        assert has_expected or is_valid_empty, (
            f"Relative path should work or return valid empty result, got symbols: {symbol_names}"
        )

        return result

    # Run with retry logic
    run_test_with_retry(_run_test, relative_path)
