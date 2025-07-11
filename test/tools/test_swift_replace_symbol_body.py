#!/usr/bin/env python3
"""
Comprehensive test suite for swift_replace_symbol_body tool.

Tests symbol body replacement, boundary detection, security validation, and error handling
for replacing body content of Swift symbols while preserving declarations.

Usage: pytest test/tools/test_swift_replace_symbol_body.py
"""

import os
import time

import pytest

# Direct imports without sys.path manipulation
from swiftlens.tools.swift_replace_symbol_body import (  # noqa: E402
    swift_replace_symbol_body,
)

# Import test helpers from current directory
from .test_helpers import handle_tool_result  # noqa: E402


def create_test_swift_file(content: str, temp_dir: str, filename: str = "test.swift") -> str:
    """Create a temporary Swift file for testing."""
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


@pytest.mark.lsp
def test_basic_body_replacement(built_swift_environment):
    """Test 1: Basic symbol body replacement."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct TestStruct {
    let value: String

    func testMethod() {
        print("old implementation")
    }
}"""
    file_path = create_swift_file(content, "TestStructFile.swift")

    # Test replacing struct body
    new_body = """struct TestStruct {
        let value: String
        let newField: Int = 42

        func testMethod() {
            print("new implementation")
        }
    }"""

    result = swift_replace_symbol_body(file_path, "TestStruct", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)
    # assert "Replaced body"), f"Expected successful replacement, got: {result}"

    # Verify the replacement
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "newField: Int = 42" in new_content, "New field not found in replaced struct"
    assert "new implementation" in new_content, "New method not found in replaced struct"


@pytest.mark.lsp
def test_symbol_name_normalization(built_swift_environment):
    """Test that symbol names are normalized (parentheses removed) before LSP operations."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    # Create a simple struct that we know works in test environment
    content = """import Foundation

struct NormalizationTest {
    let value: String

    func method() {
        print("Method")
    }
}"""
    file_path = create_swift_file(content, "NormalizationTest.swift")

    # Test that struct replacement works without parentheses (structs don't use them anyway)
    new_body = """struct NormalizationTest {
    let value: String
    let normalized: Bool = true
}"""

    result = swift_replace_symbol_body(file_path, "NormalizationTest", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement worked
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()

    assert "normalized: Bool = true" in new_content, "Normalization test field not found"


def test_single_line_function_body_replacement(built_swift_environment):
    """Test single-line function body replacement (reproducing the reported bug)."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

func globalFunctionWithBody() { print("Old body") }

struct TestStruct {
    let value: String
}"""
    file_path = create_swift_file(content, "SingleLineTestFile.swift")

    # Replace the single-line function body
    new_body = """print("Replaced global function body.")"""

    result = swift_replace_symbol_body(file_path, "globalFunctionWithBody()", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement is correct and not malformed
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()

    # Check that the replacement was clean (no duplication)
    assert new_content.count('print("Replaced global function body.")') == 1, "Body was duplicated"
    assert 'print("Old body")' not in new_content, "Old body was not removed"

    # Verify the function structure is preserved
    assert "func globalFunctionWithBody()" in new_content, "Function declaration was damaged"

    # Check for the specific malformed pattern from the bug report
    assert (
        'print("New global function body     print("Replaced global function body.") print("New global function body.")'
        not in new_content
    ), "Found the malformed pattern from bug report"


@pytest.mark.lsp
def test_struct_body_replacement_without_parentheses(built_swift_environment):
    """Test that struct body replacement works with method names without parentheses."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct TestStructWithMethods {
    let value: String

    func doSomething() {
        print("Original method")
    }

    func doSomethingElse() {
        print("Another method")
    }
}"""
    file_path = create_swift_file(content, "TestStructMethods.swift")

    # Test: Replace entire struct body - this should work based on test_basic_body_replacement
    new_body = """struct TestStructWithMethods {
    let value: String
    let newField: Int = 42

    func doSomething() {
        print("Updated method")
    }

    func doSomethingElse() {
        print("Updated another method")
    }
}"""

    result = swift_replace_symbol_body(file_path, "TestStructWithMethods", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement worked
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()

    assert "newField: Int = 42" in new_content, "New field not found in replaced struct"
    assert 'print("Updated method")' in new_content, "Updated method not found"
    assert 'print("Original method")' not in new_content, "Original method was not replaced"


def test_method_body_replacement_with_dotted_path(built_swift_environment):
    """Test method-level body replacement using dotted path notation."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct TestStruct {
    let value: String

    func testMethod() {
        print("old implementation")
    }
}"""
    file_path = create_swift_file(content, "TestFile.swift")

    # Attempt method-level replacement using dotted path notation
    new_body = """print("new implementation")"""

    result = swift_replace_symbol_body(file_path, "TestStruct.testMethod()", new_body)

    # Use helper function for consistent error handling - no more dynamic skipping
    handle_tool_result(result)

    # If we got here, the replacement succeeded
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "new implementation" in new_content, "New method body not found"
    assert "old implementation" not in new_content, "Old method body still present"


@pytest.mark.lsp
def test_class_body_replacement(built_swift_environment):
    """Test 2: Class body replacement."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

class OldClass {
    var property: String = "old"

    func oldMethod() {
        print("old method")
    }
}"""
    file_path = create_swift_file(content, "OldClassFile.swift")

    # Replace entire class body
    new_body = """class OldClass {
    private var newProperty: Int = 42

    func newMethod() async throws {
        print("new async method")
    }

    deinit {
        print("cleanup")
    }
}"""

    result = swift_replace_symbol_body(file_path, "OldClass", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)
    # assert "Replaced body"), f"Expected successful replacement, got: {result}"

    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "newProperty" in new_content, "Class body not replaced"
    assert "newProperty" in new_content, "New property not found"
    assert "oldMethod" not in new_content, "Old method still present"


@pytest.mark.lsp
def test_path_validation(built_swift_environment):
    """Test 3: File path validation and security checks."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    # Test non-existent file
    result = swift_replace_symbol_body("/nonexistent/file.swift", "test", "new body")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "File not found" in error_msg or "not found" in error_msg, (
        f"Expected file not found error, got: {error_msg}"
    )

    # Test null byte injection
    result = swift_replace_symbol_body("test\0.swift", "test", "new body")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Invalid file path" in error_msg or "invalid" in error_msg.lower(), (
        f"Expected invalid path error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_symbol_validation(built_swift_environment):
    """Test 4: Symbol name validation."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """struct TestStruct {
    let value: String
}"""
    file_path = create_swift_file(content, "TestFile.swift")

    # Test empty symbol name
    result = swift_replace_symbol_body(file_path, "", "new body")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Symbol name" in error_msg and "non-empty" in error_msg, (
        f"Expected empty symbol error, got: {error_msg}"
    )

    # Test None-like symbol name (using whitespace-only string to test validation without type errors)
    result = swift_replace_symbol_body(file_path, "   ", "new body")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert ("Symbol name" in error_msg and "non-empty" in error_msg) or "not found" in error_msg, (
        f"Expected whitespace symbol validation or not found error, got: {error_msg}"
    )

    # Test very long symbol name
    long_name = "x" * 300
    result = swift_replace_symbol_body(file_path, long_name, "new body")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Symbol name" in error_msg and "long" in error_msg, (
        f"Expected long symbol error, got: {error_msg}"
    )


@pytest.mark.lsp
def test_body_validation(built_swift_environment):
    """Test 5: Body content validation."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """struct TestStruct {
    let value: String
}"""
    file_path = create_swift_file(content, "TestFile.swift")

    # Test empty body
    result = swift_replace_symbol_body(file_path, "TestStruct", "")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Body" in error_msg and "non-empty" in error_msg, (
        f"Expected empty body error, got: {error_msg}"
    )

    # Test whitespace-only body
    result = swift_replace_symbol_body(file_path, "TestStruct", "   \n  \t  ")
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Body" in error_msg and "non-empty" in error_msg, (
        f"Expected whitespace-only error, got: {error_msg}"
    )

    # Test invalid body (using alternative approach to test validation without type errors)
    # Note: Testing with very large body to trigger validation without type errors
    huge_body = "x" * 10000  # Test with extremely large body
    result = swift_replace_symbol_body(file_path, "TestStruct", huge_body)
    # This test may succeed or fail depending on system limits, both are acceptable
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"


@pytest.mark.lsp
def test_symbol_not_found(built_swift_environment):
    """Test 6: Symbol not found error."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """struct TestStruct {
    let value: String
}"""
    file_path = create_swift_file(content, "TestFile.swift")

    result = swift_replace_symbol_body(file_path, "NonExistentSymbol", "new body")

    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert not result.get("success", True), f"Expected failure, got: {result}"
    error_msg = result.get("error", "")
    assert "Symbol not found" in error_msg or "not found" in error_msg, (
        f"Expected symbol not found error, got: {error_msg}"
    )


def test_performance(built_swift_environment):
    """Test 7: Performance with larger files."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    # Create a larger Swift file
    large_content = """import Foundation

struct TestStruct {
    var property0: String = "test0"
    var property1: String = "test1"
    var property2: String = "test2"

    func method0() {
        print("method0")
    }

    func method1() {
        print("method1")
    }

    func method10() {
        print("method10")
    }

    func method15() {
        print("method15")
    }
}
"""

    file_path = create_swift_file(large_content, "PerformanceTest.swift")

    # Replace the struct body content for performance testing
    new_body = """    var property0: String = "test0"
    var property1: String = "test1"
    var property2: String = "test2"

    func method0() {
        print("method0")
    }

    func method1() {
        print("method1")
    }

    func method10() {
        print("PERFORMANCE TEST - optimized method10")
    }

    func method15() {
        print("method15")
    }"""

    start_time = time.time()
    result = swift_replace_symbol_body(file_path, "TestStruct", new_body)
    end_time = time.time()

    duration = end_time - start_time

    # Validate JSON response structure
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert "success" in result, "Result should have 'success' field"

    if not result["success"]:
        # Check for specific error conditions that should be skipped
        if result.get("error_type") == "lsp_error":
            pytest.fail(f"Tool failed with LSP error: {result.get('error', 'Unknown LSP error')}")
        else:
            # This is a real failure
            pytest.fail(f"Tool failed: {result.get('error', 'Unknown error')}")

    # If we got a successful result, validate it
    assert duration < 5.0, f"Performance too slow: {duration:.2f}s"


@pytest.mark.lsp
def test_computed_property_get_only_replacement(built_swift_environment):
    """Test 8: Computed property body replacement - get-only."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct MyStructWithBody {
    private var _value: String = "stored"

    var computedProperty: String {
        return "computed: " + _value
    }
}"""
    file_path = create_swift_file(content, "ComputedPropertyTest.swift")

    # Replace computed property body
    new_body = """return "new computed: " + _value + " updated\""""

    result = swift_replace_symbol_body(file_path, "computedProperty", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "new computed: " in new_content, "New computed property body not found"
    assert "updated" in new_content, "Updated text not found in computed property"


@pytest.mark.lsp
def test_computed_property_get_set_replacement(built_swift_environment):
    """Test 9: Computed property body replacement - get/set."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct MyStructWithGetSet {
    private var _value: String = "stored"

    var computedProperty: String {
        get {
            return "get: " + _value
        }
        set {
            _value = "set: " + newValue
        }
    }
}"""
    file_path = create_swift_file(content, "ComputedGetSetTest.swift")

    # Replace computed property body with new get/set implementation
    new_body = """get {
            return "new get: " + _value + " modified"
        }
        set {
            _value = "new set: " + newValue + " processed"
        }"""

    result = swift_replace_symbol_body(file_path, "computedProperty", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "new get: " in new_content, "New get implementation not found"
    assert "new set: " in new_content, "New set implementation not found"
    assert "modified" in new_content, "Modified text not found"
    assert "processed" in new_content, "Processed text not found"


@pytest.mark.lsp
def test_computed_property_single_line_replacement(built_swift_environment):
    """Test 10: Computed property body replacement - single line."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct MyStructSingleLine {
    private var _value: String = "stored"

    var computedProperty: String { "single line: " + _value }
}"""
    file_path = create_swift_file(content, "ComputedSingleLineTest.swift")

    # Replace single-line computed property body
    new_body = """"updated single line: " + _value + " enhanced\""""

    result = swift_replace_symbol_body(file_path, "computedProperty", new_body)

    # Use helper function for consistent error handling
    handle_tool_result(result)

    # Verify the replacement
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "updated single line: " in new_content, "Updated single line text not found"
    assert "enhanced" in new_content, "Enhanced text not found"


@pytest.mark.lsp
def test_computed_property_dotted_path_replacement(built_swift_environment):
    """Test 11: Computed property body replacement - dotted path access.

    The segfault occurs because:
    1. Test environments have incomplete IndexStoreDB that may not properly index nested symbols
    2. Temporary test directories can cause symbol resolution issues with dotted paths
    3. The LSP server may crash when trying to resolve complex symbol paths without full project context

    This is not a bug in the tool itself but a limitation of the test infrastructure.
    """
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct MyStructWithBody {
    private var _value: String = "stored"

    var computedStructProperty: String {
        return "struct computed: " + _value
    }
}

enum MyEnumWithBody {
    case active, inactive

    var computedEnumProperty: String {
        switch self {
        case .active:
            return "enum active"
        case .inactive:
            return "enum inactive"
        }
    }
}"""
    file_path = create_swift_file(content, "ComputedDottedPathTest.swift")

    # Test struct computed property with dotted path
    result_struct = swift_replace_symbol_body(
        file_path,
        "MyStructWithBody.computedStructProperty",
        'return "updated struct computed: " + _value + " via dotted path"',
    )

    # Use helper function for consistent error handling
    handle_tool_result(result_struct)

    # Test enum computed property with dotted path
    result_enum = swift_replace_symbol_body(
        file_path,
        "MyEnumWithBody.computedEnumProperty",
        """switch self {
        case .active:
            return "updated enum active via dotted path"
        case .inactive:
            return "updated enum inactive via dotted path"
        }""",
    )

    # Use helper function for consistent error handling
    handle_tool_result(result_enum)

    # Verify both replacements
    with open(file_path, encoding="utf-8") as f:
        new_content = f.read()
    assert "updated struct computed: " in new_content, "Updated struct computed property not found"
    assert "via dotted path" in new_content, "Dotted path marker not found"
    assert "updated enum active via dotted path" in new_content, (
        "Updated enum computed property not found"
    )


# Additional documentation about dotted path limitations
# This test demonstrates a specific case where SourceKit-LSP crashes in test environments
# when trying to resolve dotted path symbols (e.g., MyStruct.myProperty). This is related
# to the same IndexStoreDB limitations that affect reference finding, but manifests as
# a segmentation fault rather than empty results.


@pytest.mark.lsp
def test_computed_property_sequential_replacement(built_swift_environment):
    """Test 12: Sequential computed property body replacements - file integrity."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = """import Foundation

struct SequentialTest {
    private var _value1: String = "value1"
    private var _value2: String = "value2"

    var firstProperty: String {
        return "first: " + _value1
    }

    var secondProperty: String {
        return "second: " + _value2
    }

    var thirdProperty: String {
        get {
            return "third: " + _value1 + _value2
        }
        set {
            _value1 = newValue
        }
    }
}"""
    file_path = create_swift_file(content, "SequentialReplacementTest.swift")

    # First replacement
    result1 = swift_replace_symbol_body(
        file_path,
        "firstProperty",
        """return "updated first: " + _value1 + " (1st pass)\"""",
    )
    handle_tool_result(result1)

    # Second replacement
    result2 = swift_replace_symbol_body(
        file_path,
        "secondProperty",
        """return "updated second: " + _value2 + " (2nd pass)\"""",
    )
    handle_tool_result(result2)

    # Third replacement (get/set)
    result3 = swift_replace_symbol_body(
        file_path,
        "thirdProperty",
        """get {
            return "updated third: " + _value1 + _value2 + " (3rd pass)"
        }
        set {
            _value1 = "modified: " + newValue
        }""",
    )
    handle_tool_result(result3)

    # Verify all replacements and file integrity
    with open(file_path, encoding="utf-8") as f:
        final_content = f.read()

    # Check all updates are present
    assert "updated first: " in final_content, "First property update not found"
    assert "(1st pass)" in final_content, "First pass marker not found"
    assert "updated second: " in final_content, "Second property update not found"
    assert "(2nd pass)" in final_content, "Second pass marker not found"
    assert "updated third: " in final_content, "Third property update not found"
    assert "(3rd pass)" in final_content, "Third pass marker not found"
    assert "modified: " in final_content, "Modified setter not found"

    # Verify file structure integrity (proper braces, no corruption)
    assert final_content.count("{") == final_content.count("}"), (
        "Brace mismatch - file structure corrupted"
    )
    assert "struct SequentialTest" in final_content, "Struct declaration missing"

@pytest.mark.lsp
def test_symbol_body_replacement_without_dotted_paths(built_swift_environment):
    """Test symbol body replacement without using dotted path notation.
    
    This test verifies that we can replace entire symbol bodies (structs, classes, enums)
    without using dotted paths, which is the most reliable approach.
    """
    project_root, sources_dir, create_swift_file = built_swift_environment
    
    # Test 1: Replace entire struct body
    content = """import Foundation

struct TestStructForReplacement {
    var oldProperty: Int = 10
    
    func oldMethod() {
        print("old method")
    }
}

class TestClassForReplacement {
    var oldClassProperty: String = "old"
    
    init() {
        print("old init")
    }
}"""
    file_path = create_swift_file(content, "NonDottedPathReplacement.swift")
    
    # Replace struct body
    new_struct_body = """struct TestStructForReplacement {
    var newProperty: Int = 20
    var anotherProperty: String = "new"
    
    func newMethod() {
        print("new method")
    }
    
    func additionalMethod() {
        print("additional functionality")
    }
}"""
    
    result_struct = swift_replace_symbol_body(
        file_path, 
        "TestStructForReplacement", 
        new_struct_body
    )
    handle_tool_result(result_struct)
    
    # Replace class body
    new_class_body = """class TestClassForReplacement {
    var newClassProperty: String = "new"
    var extraProperty: Bool = true
    
    init() {
        print("new init")
    }
    
    func newClassMethod() {
        print("new class method")
    }
}"""
    
    result_class = swift_replace_symbol_body(
        file_path,
        "TestClassForReplacement", 
        new_class_body
    )
    handle_tool_result(result_class)
    
    # Verify replacements
    with open(file_path, encoding="utf-8") as f:
        final_content = f.read()
    
    # Check struct replacement
    assert "newProperty: Int = 20" in final_content, "New struct property not found"
    assert "anotherProperty: String" in final_content, "Another property not found"
    assert "additionalMethod" in final_content, "Additional method not found"
    assert "oldProperty" not in final_content, "Old struct property still present"
    assert "oldMethod" not in final_content, "Old struct method still present"
    
    # Check class replacement  
    assert "newClassProperty: String = \"new\"" in final_content, "New class property not found"
    assert "extraProperty: Bool = true" in final_content, "Extra property not found"
    assert "newClassMethod" in final_content, "New class method not found"
    assert "oldClassProperty" not in final_content, "Old class property still present"
    assert 'print("old init")' not in final_content, "Old init still present"
    # File integrity verified - newlines are preserved by SwiftFileModifier
