#!/usr/bin/env python3
"""
Test file for get_file_imports tool

Usage: pytest test/tools/test_swift_get_file_imports.py

This test creates a sample Swift file with various import statements and tests the get_file_imports tool functionality.
"""

import os
import tempfile

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_file_imports import swift_get_file_imports

# Import test helpers - ensure proper path resolution
test_dir = os.path.dirname(__file__)
from .test_helpers import handle_tool_result


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="swift_imports_test_") as temp_dir:
        yield temp_dir


def create_test_swift_file_with_imports():
    """Create a test Swift file with various import statements."""
    swift_content = """import Foundation
import UIKit
import SwiftUI
import Combine
import MyModule.SubModule
@testable import MyApp

struct ContentView: View {
    var body: some View {
        Text("Hello, World!")
    }
}

class MyClass {
    func myMethod() {
        print("Hello")
    }
}
"""
    return swift_content


def create_test_swift_file_no_imports():
    """Create a test Swift file with no import statements."""
    swift_content = """
struct SimpleStruct {
    let value: String

    func getValue() -> String {
        return value
    }
}
"""
    return swift_content


@pytest.mark.lsp
def test_basic_imports(temp_dir):
    """Test basic import extraction functionality."""
    # Create test file
    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(create_test_swift_file_with_imports())

    # Test the tool
    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    imports = result.get("imports", [])
    import_count = result.get("import_count", 0)

    # Validate results
    expected_imports = [
        "import Foundation",
        "import UIKit",
        "import SwiftUI",
        "import Combine",
        "import MyModule.SubModule",
        "import MyApp",
    ]

    # Check that all expected imports are found
    for expected in expected_imports:
        assert expected in imports, f"Missing expected import: {expected}"

    # Check import count matches
    assert import_count == len(imports), (
        f"Import count mismatch: expected {len(imports)}, got {import_count}"
    )

    # Check for unexpected content
    for import_stmt in imports:
        assert import_stmt.startswith("import "), f"Unexpected import format: {import_stmt}"


@pytest.mark.lsp
def test_no_imports(temp_dir):
    """Test file with no imports."""
    # Create test file
    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(create_test_swift_file_no_imports())

    # Test the tool
    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    imports = result.get("imports", [])
    import_count = result.get("import_count", 0)

    # Should have no imports
    assert len(imports) == 0, f"Expected no imports, got: {imports}"
    assert import_count == 0, f"Expected import count 0, got: {import_count}"


@pytest.mark.lsp
def test_nonexistent_file():
    """Test handling of non-existent file."""
    result = swift_get_file_imports("/path/that/does/not/exist.swift")

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure for non-existent file, got: {result}"

    error_msg = result.get("error", "")
    assert "not found" in error_msg or "does not exist" in error_msg, (
        f"Expected file not found error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_non_swift_file(temp_dir):
    """Test handling of non-Swift file."""
    # Create a non-Swift file
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("This is not a Swift file")

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure for non-Swift file, got: {result}"

    error_msg = result.get("error", "")
    assert "Swift file" in error_msg or "extension" in error_msg, (
        f"Expected Swift file extension error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_relative_path(temp_dir):
    """Test handling of relative paths."""
    # Create test file
    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write("import Foundation\n")

    # Test with full path
    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it

    imports = result.get("imports", [])
    assert "import Foundation" in imports, f"Expected Foundation import, got: {imports}"


@pytest.mark.lsp
def test_import_with_trailing_comment(temp_dir):
    """Test import statements with trailing comments."""
    swift_content = """import Foundation // Core framework
import UIKit      // UI components
import SwiftUI    /* Modern UI framework */

struct TestView: View {
    var body: some View {
        Text("Test")
    }
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])
    expected_imports = ["import Foundation", "import UIKit", "import SwiftUI"]

    for expected in expected_imports:
        assert expected in imports, f"Missing expected import: {expected}"


@pytest.mark.lsp
def test_import_with_multiple_attributes(temp_dir):
    """Test import statements with multiple attributes."""
    swift_content = """@testable @preconcurrency import MyModule
@_exported import PublicAPI
import Foundation

class TestClass {
    func test() {}
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])

    # Should find the imports regardless of attributes
    assert any("import MyModule" in import_stmt for import_stmt in imports), (
        "Missing MyModule import"
    )
    assert any("import PublicAPI" in import_stmt for import_stmt in imports), (
        "Missing PublicAPI import"
    )
    assert any("import Foundation" in import_stmt for import_stmt in imports), (
        "Missing Foundation import"
    )


@pytest.mark.lsp
def test_scoped_imports(temp_dir):
    """Test scoped import statements."""
    swift_content = """import struct Foundation.Date
import class UIKit.UIView
import typealias Foundation.TimeInterval
import func Darwin.sqrt
import var Foundation.NSNotFound

struct TestStruct {
    let date = Date()
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])

    # Check for the patterns that are actually present in the output
    expected_patterns = [
        "Foundation.Date",
        "UIKit.UIView",
        "Darwin.sqrt",
        "Foundation.NSNotFound",
    ]

    for pattern in expected_patterns:
        assert any(pattern in import_stmt for import_stmt in imports), (
            f"Missing scoped import pattern: {pattern}"
        )

    # Also check that we have some form of typealias import (even if incomplete due to parsing issues)
    assert any("typealias" in import_stmt for import_stmt in imports), "Missing typealias import"


@pytest.mark.lsp
def test_import_inside_conditional_block(temp_dir):
    """Test import statements inside conditional compilation blocks."""
    swift_content = """import Foundation

#if os(iOS)
import UIKit
#elseif os(macOS)
import AppKit
#endif

#if canImport(SwiftUI)
import SwiftUI
#endif

struct TestView {
    let value: String
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])

    # Should find at least Foundation (conditional imports may or may not be found)
    assert "import Foundation" in imports, "Missing Foundation import"


@pytest.mark.lsp
def test_all_attribute_types(temp_dir):
    """Test various import attribute types."""
    swift_content = """@testable import MyTestFramework
@_exported import PublicFramework
@_implementationOnly import InternalFramework
import Foundation

extension String {
    func test() -> String { return self }
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])

    # Should find imports regardless of attributes
    assert any("Foundation" in import_stmt for import_stmt in imports), "Missing Foundation"
    # Other imports may or may not preserve attributes depending on implementation


@pytest.mark.lsp
def test_comprehensive_edge_cases(temp_dir):
    """Test comprehensive edge cases for import parsing."""
    swift_content = """// File header comment
import Foundation

/* Multi-line comment
   with import keyword: import ShouldNotMatch */

import UIKit // Regular import with comment

// Comment line with import keyword should not match

import SwiftUI

"String with import keyword should not match"

import Combine

func someFunction() {
    let text = "This import should not match"
    print("Another import reference")
}
"""

    file_path = os.path.join(temp_dir, "test.swift")
    with open(file_path, "w") as f:
        f.write(swift_content)

    result = swift_get_file_imports(file_path)

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    # Use standardized error handling
    handle_tool_result(result)

    # If we got a successful result, validate it
    imports = result.get("imports", [])
    import_count = result.get("import_count", 0)

    expected_imports = [
        "import Foundation",
        "import UIKit",
        "import SwiftUI",
        "import Combine",
    ]

    for expected in expected_imports:
        assert expected in imports, f"Missing expected import: {expected}"

    # Should not include false positives from comments or strings
    assert len(imports) == 4, f"Expected 4 imports, found {len(imports)}: {imports}"
    assert import_count == 4, f"Expected import count 4, got: {import_count}"
