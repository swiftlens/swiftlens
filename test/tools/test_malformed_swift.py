#!/usr/bin/env python3
"""
Test file for malformed Swift code handling

Usage: pytest test/tools/test_malformed_swift.py

This test validates that all tools handle malformed Swift code gracefully
and don't crash when encountering syntax errors.
"""

import os
import shutil
import tempfile

import pytest

# Mark all tests in this file as malformed to exclude from default test runs
pytestmark = pytest.mark.malformed

# Add src directory to path for imports
from swiftlens.tools.swift_analyze_file import swift_analyze_file  # noqa: E402
from swiftlens.tools.swift_find_symbol_references_files import (
    swift_find_symbol_references_files,  # noqa: E402
)
from swiftlens.tools.swift_get_declaration_context import (
    swift_get_declaration_context,  # noqa: E402
)
from swiftlens.tools.swift_get_hover_info import swift_get_hover_info  # noqa: E402
from swiftlens.tools.swift_get_symbol_definition import swift_get_symbol_definition  # noqa: E402
from swiftlens.tools.swift_get_symbols_overview import swift_get_symbols_overview  # noqa: E402
from swiftlens.tools.swift_summarize_file import swift_summarize_file  # noqa: E402
from swiftlens.tools.swift_validate_file import swift_validate_file  # noqa: E402


def create_malformed_swift_files():
    """Create various malformed Swift files to test error handling."""

    # File 1: Missing closing braces
    missing_braces = """import Foundation

struct User {
    let id: String
    var name: String
    // Missing closing brace

class UserService {
    func addUser() {
        // Missing closing brace for both function and class
"""

    # File 2: Invalid syntax
    invalid_syntax = """import Foundation

struct User {
    let id: String
    var name String  // Missing colon

    func validateEmail() -> Bool {
        return email.contains("@"  // Missing closing parenthesis
    }

    // Invalid function declaration
    func someFunction(param1, param2) {  // Missing types
        return "invalid"
    }
}

// Invalid class declaration
class UserService : {  // Invalid inheritance syntax
    var users: [User] = []

    func addUser(_ user: User {  // Missing closing parenthesis
        users.append(user)
    // Missing closing brace
"""

    # File 3: Incomplete declarations
    incomplete_declarations = """import Foundation

struct User {
    let id: String
    var name: String

    func  // Incomplete function declaration

enum Status {
    case active
    case  // Incomplete case

    var description: String {
        // Missing implementation and closing brace

protocol UserProtocol {
    func validate() -> Bool
    // Missing closing brace

class UserService  // Missing opening brace entirely
    var users: [User] = []
"""

    # File 4: Mixed valid and invalid code
    mixed_code = """import Foundation

// Valid part
struct ValidUser {
    let id: String
    var name: String

    func validateEmail() -> Bool {
        return true
    }
}

// Invalid part starts here
struct InvalidUser {
    let id: String
    var name String  // Missing colon

    func validateEmail() -> Bool {
        return email.contains("@"  // Missing closing parenthesis
    }
    // Missing closing brace

// Another valid part
enum UserStatus {
    case active
    case inactive

    var description: String {
        switch self {
        case .active: return "Active"
        case .inactive: return "Inactive"
        }
    }
}
"""

    # File 5: Empty file
    empty_file = ""

    # File 6: Only comments and imports
    comments_only = """// This is a comment file
/* Multi-line comment
   with some content */

import Foundation
import UIKit

// No actual code declarations
"""

    return [
        ("MissingBraces.swift", missing_braces),
        ("InvalidSyntax.swift", invalid_syntax),
        ("IncompleteDeclarations.swift", incomplete_declarations),
        ("MixedCode.swift", mixed_code),
        ("Empty.swift", empty_file),
        ("CommentsOnly.swift", comments_only),
    ]


def _test_tool_with_malformed_file(tool_function, tool_name, file_path, *args):
    """Test a tool function with a malformed file and validate graceful handling."""
    try:
        if args:
            # Special handling for multi-file functions that now take file_paths as a list
            if tool_name == "swift_find_symbol_references_files":
                result = tool_function([file_path], *args)
            else:
                result = tool_function(file_path, *args)
        else:
            result = tool_function(file_path)

        # Tool should either return:
        # 1. A successful dict response (success=True/False with data)
        # 2. An error response (success=False with error message)
        # But it should NOT crash or return completely malformed output

        if isinstance(result, dict):
            # Valid dict response - check if it has proper structure
            if "success" in result:
                # This is the expected format from all tools
                return True, result
            else:
                # Still a dict but missing success field - accept it
                return True, result
        elif isinstance(result, str):
            # Check for valid file path patterns (e.g., /path/file.swift:3:8)
            import re

            file_path_pattern = re.compile(r".*\.swift:\d+:\d+$")

            if (
                "Error:" in result
                or "No symbols found" in result
                or "No symbols" in result  # swift_summarize_file output
                or "Empty file" in result  # swift_summarize_file output
                or "No top-level symbols" in result  # swift_get_symbols_overview output
                or "Summary:" in result  # swift_validate_file output with diagnostics
                or result == "No errors"  # swift_validate_file valid output
                or "No references found" in result
                or "No hover information" in result
                or "📋 Hover Info:" in result  # Valid hover response
                or len(result.strip()) == 0
                or file_path_pattern.match(result.strip())  # Valid symbol definition result
                or any(
                    keyword in result
                    for keyword in [
                        "(Struct)",
                        "(Class)",
                        "(Enum)",
                        "(Interface)",
                        "Class:",
                        "Struct:",
                        "Method:",
                        "Property:",
                    ]
                )
            ):
                return True, result
            else:
                return False, f"Unexpected result format: {result}"
        else:
            return False, f"Tool returned unexpected type: {type(result)}"

    except Exception as e:
        return False, f"Tool crashed with exception: {e}"


@pytest.fixture
def malformed_swift_files():
    """Create various malformed Swift files to test error handling."""
    temp_dir = tempfile.mkdtemp(prefix="swift_malformed_test_")

    malformed_files = create_malformed_swift_files()
    test_files = []

    for filename, content in malformed_files:
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w") as f:
            f.write(content)
        test_files.append((filename, file_path))

    yield test_files

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.parametrize(
    "tool_func,tool_name",
    [
        (swift_analyze_file, "swift_analyze_file"),
        (swift_get_declaration_context, "swift_get_declaration_context"),
        (swift_summarize_file, "swift_summarize_file"),
        (swift_get_symbols_overview, "swift_get_symbols_overview"),
        (swift_validate_file, "swift_validate_file"),
    ],
)
def test_basic_tools_with_malformed_files(malformed_swift_files, tool_func, tool_name):
    """Test basic tools with malformed Swift files"""
    for filename, file_path in malformed_swift_files:
        success, result = _test_tool_with_malformed_file(tool_func, tool_name, file_path)
        assert success, f"{tool_name} failed on {filename}: {result}"


@pytest.mark.parametrize(
    "tool_func,tool_name,symbol",
    [
        (swift_find_symbol_references_files, "swift_find_symbol_references_files", "User"),
        (swift_get_symbol_definition, "swift_get_symbol_definition", "User"),
    ],
)
def test_reference_tools_with_malformed_files(malformed_swift_files, tool_func, tool_name, symbol):
    """Test reference finding tools with malformed Swift files"""
    for filename, file_path in malformed_swift_files:
        success, result = _test_tool_with_malformed_file(tool_func, tool_name, file_path, symbol)
        assert success, f"{tool_name} failed on {filename}: {result}"


@pytest.mark.parametrize("line,char", [(5, 10)])
def test_hover_tools_with_malformed_files(malformed_swift_files, line, char):
    """Test hover tools with malformed Swift files"""
    for filename, file_path in malformed_swift_files:
        success, result = _test_tool_with_malformed_file(
            swift_get_hover_info, "swift_get_hover_info", file_path, line, char
        )
        assert success, f"swift_get_hover_info failed on {filename}: {result}"


def test_malformed_files_graceful_handling_summary(malformed_swift_files):
    """Test summary: Ensure all tools handle malformed files gracefully"""
    tools_to_test = [
        (swift_analyze_file, "swift_analyze_file"),
        (swift_get_declaration_context, "swift_get_declaration_context"),
        (swift_summarize_file, "swift_summarize_file"),
        (swift_get_symbols_overview, "swift_get_symbols_overview"),
        (swift_validate_file, "swift_validate_file"),
    ]

    # Tools that require additional parameters
    reference_tools = [
        (swift_find_symbol_references_files, "swift_find_symbol_references_files", "User"),
        (swift_get_symbol_definition, "swift_get_symbol_definition", "User"),
    ]

    hover_tools = [
        (swift_get_hover_info, "swift_get_hover_info", 5, 10),
    ]

    total_tests = 0
    passed_tests = 0

    # Test basic tools
    for tool_func, tool_name in tools_to_test:
        for _filename, file_path in malformed_swift_files:
            total_tests += 1
            success, result = _test_tool_with_malformed_file(tool_func, tool_name, file_path)
            if success:
                passed_tests += 1

    # Test reference finding tools
    for tool_func, tool_name, symbol in reference_tools:
        for _filename, file_path in malformed_swift_files:
            total_tests += 1
            success, result = _test_tool_with_malformed_file(
                tool_func, tool_name, file_path, symbol
            )
            if success:
                passed_tests += 1

    # Test hover tools
    for tool_func, tool_name, line, char in hover_tools:
        for _filename, file_path in malformed_swift_files:
            total_tests += 1
            success, result = _test_tool_with_malformed_file(
                tool_func, tool_name, file_path, line, char
            )
            if success:
                passed_tests += 1

    # We expect at least 90% success rate for graceful handling
    success_rate = (passed_tests / total_tests) * 100
    assert success_rate >= 90.0, (
        f"Only {success_rate:.1f}% success rate for graceful handling (expected >= 90%)"
    )
