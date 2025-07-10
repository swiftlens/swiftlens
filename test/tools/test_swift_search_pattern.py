#!/usr/bin/env python3
"""
Comprehensive test suite for swift_search_pattern tool.

Tests pattern searching in Swift files including regex patterns, literal strings,
flags functionality, context lines, and edge cases for realistic search scenarios.

Usage: pytest test/tools/test_swift_search_pattern.py
"""

import os
import tempfile

# Add src directory to path for imports
src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
# Add the parent directory to enable relative imports
parent_path = os.path.join(os.path.dirname(__file__), "..", "..")
# Now we can import normally
from swiftlens.tools.swift_search_pattern import (  # noqa: E402
    _get_context_lines,
    _get_line_number_and_char,
    _parse_flags,
    _validate_pattern,
    swift_search_pattern,
)


def create_test_swift_file(content: str, temp_dir: str, filename: str = "test.swift") -> str:
    """Create a temporary Swift file for testing."""
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def test_basic_literal_search():
    """Test 1: Basic literal string search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    let property = "test value"

    func testMethod() {
        print("Hello World")
        let another = "test value"
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for literal string
        result = swift_search_pattern(file_path, "test value", is_regex=False)

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert result.get("success", False), f"Expected success, got: {result}"

        matches = result.get("matches", [])
        assert len(matches) == 2, f"Expected 2 matches, got {len(matches)}: {result}"

        # Check first match
        first_match = matches[0]
        assert first_match["line"] == 4, f"Expected line 4, got: {first_match['line']}"
        assert first_match["character"] == 21, (
            f"Expected character 21, got: {first_match['character']}"
        )

        # Check second match
        second_match = matches[1]
        assert second_match["line"] == 8, f"Expected line 8, got: {second_match['line']}"
        assert second_match["character"] == 24, (
            f"Expected character 24, got: {second_match['character']}"
        )


def test_basic_regex_search():
    """Test 2: Basic regex pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    func method1() { }
    func method2() { }
    func anotherMethod() { }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for methods using regex
        result = swift_search_pattern(file_path, r"func method\d+\(\) \{ \}")

        # Validate JSON response structure
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert result.get("success", False), f"Expected success, got: {result}"

        matches = result.get("matches", [])
        assert len(matches) == 2, f"Expected 2 matches, got {len(matches)}: {result}"

        # Check first match
        first_match = matches[0]
        assert first_match["line"] == 4, f"Expected line 4, got: {first_match['line']}"
        assert first_match["character"] == 5, (
            f"Expected character 5, got: {first_match['character']}"
        )


def test_swift_function_patterns():
    """Test 3: Swift-specific function patterns."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class Calculator {
    func add(a: Int, b: Int) -> Int {
        return a + b
    }

    func subtract(x: Double, y: Double) -> Double {
        return x - y
    }

    func multiply<T: Numeric>(lhs: T, rhs: T) -> T {
        return lhs * rhs
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for function declarations with parameters
        result = swift_search_pattern(file_path, r"func \w+\([^)]+\) -> \w+")

        assert result["success"] and result["match_count"] == 2, (
            f"Expected 2 matches, got: {result}"
        )


def test_property_wrapper_search():
    """Test 4: Property wrapper pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import SwiftUI

struct ContentView: View {
    @State private var count: Int = 0
    @StateObject private var manager = DataManager()
    @Binding var isPresented: Bool
    @Published var updates: [String] = []

    var body: some View {
        Text("Hello")
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for property wrappers
        result = swift_search_pattern(file_path, r"@\w+ (?:private )?var \w+:")

        assert result["success"] and result["match_count"] == 3, (
            f"Expected 3 matches, got: {result}"
        )


def test_closure_patterns():
    """Test 5: Closure pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class EventHandler {
    let completion = { (result: Bool) in
        print("Completed with result: \\(result)")
    }

    let transform: (String) -> String = { input in
        return input.uppercased()
    }

    func process(callback: @escaping () -> Void) {
        DispatchQueue.main.async {
            callback()
        }
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for closure definitions
        result = swift_search_pattern(file_path, r"= \{ .*? in")

        assert result["success"] and result["match_count"] == 2, (
            f"Expected 2 matches, got: {result}"
        )


def test_async_await_patterns():
    """Test 6: Async/await pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class NetworkManager {
    func fetchData() async throws -> Data {
        let url = URL(string: "https://example.com")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return data
    }

    func processData() async {
        do {
            let data = try await fetchData()
            await MainActor.run {
                print("Data received")
            }
        } catch {
            print("Error: \\(error)")
        }
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for async functions
        result = swift_search_pattern(file_path, r"func \w+\([^)]*\) async")

        assert result["success"] and result["match_count"] == 2, (
            f"Expected 2 matches, got: {result}"
        )


def test_generic_type_patterns():
    """Test 7: Generic type pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class Container<T> {
    var items: [T] = []

    func add<U: Comparable>(item: U) where U: Codable {
        // implementation
    }
}

struct Pair<First, Second> {
    let first: First
    let second: Second
}

protocol Storage<Element> {
    associatedtype Element
    func store(_ element: Element)
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for generic type declarations
        result = swift_search_pattern(file_path, r"(?:class|struct|protocol) \w+<[^>]+>")

        assert result["success"] and result["match_count"] == 3, (
            f"Expected 3 matches, got: {result}"
        )


def test_case_insensitive_flag():
    """Test 8: Case insensitive flag functionality."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    func UPPERCASE() { }
    func lowercase() { }
    func MixedCase() { }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search with case insensitive flag
        result = swift_search_pattern(file_path, r"func uppercase\(\)", flags="i")

        assert result["success"] and result["match_count"] == 1, f"Expected 1 match, got: {result}"
        first_match = result["matches"][0]
        assert first_match["line"] == 4, f"Expected line 4, got: {first_match['line']}"


def test_multiline_flag():
    """Test 9: Multiline flag functionality."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation
// Start comment
class TestClass {
    func method() {
        print("test")
    }
}
// End comment"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search with multiline flag
        result = swift_search_pattern(file_path, r"^// Start.*?^// End", flags="ms")

        # Should match the whole multi-line comment block
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert result.get("success", False), f"Expected success, got: {result}"
        assert result["match_count"] == 1, f"Expected 1 match, got: {result}"
        match_text = result["matches"][0]["match_text"]
        assert "// Start comment" in match_text, (
            f"Expected '// Start comment' in match: {match_text}"
        )
        assert "// End" in match_text, f"Expected '// End' in match: {match_text}"


def test_context_lines():
    """Test 10: Context lines functionality."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    func targetMethod() {
        print("target")
    }

    func anotherMethod() {
        print("another")
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search with context lines
        result = swift_search_pattern(file_path, r"print\(\"target\"\)", context_lines=2)

        # Should include context lines before and after
        assert result["success"] and result["match_count"] == 1, f"Expected 1 match, got: {result}"
        context = result["matches"][0]["context"]
        assert "func targetMethod()" in context, (
            f"Expected 'func targetMethod()' in context: {context}"
        )
        assert 'print("target")' in context, f"Expected 'print(\"target\")' in context: {context}"


def test_import_statement_search():
    """Test 11: Import statement pattern search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation
import UIKit
import SwiftUI
import Combine
@testable import MyModule

class TestClass {
    // implementation
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for import statements
        result = swift_search_pattern(file_path, r"^import \w+")

        # Should match at least the first import statement
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert result.get("success", False), f"Expected success, got: {result}"
        assert result["match_count"] >= 1, f"Expected at least 1 match, got: {result}"
        first_match = result["matches"][0]
        assert "import Foundation" in first_match["match_text"], (
            f"Expected 'import Foundation' in match: {first_match}"
        )


def test_unicode_content():
    """Test 12: Unicode content search."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    let emoji = "🚀🌟⭐"
    let unicode = "café naïve résumé"
    let japanese = "こんにちは世界"

    func 测试方法() {
        print("unicode method")
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for unicode content
        result = swift_search_pattern(file_path, "🚀", is_regex=False)

        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert result.get("success", False), f"Expected success, got: {result}"
        assert result["match_count"] == 1, f"Expected 1 match, got: {result}"
        context = result["matches"][0]["context"]
        assert "🚀🌟⭐" in context, f"Expected '🚀🌟⭐' in context: {context}"


def test_no_matches():
    """Test 13: No matches scenario."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

class TestClass {
    func existingMethod() { }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for non-existent pattern
        result = swift_search_pattern(file_path, r"func nonExistentMethod\(\)")

        assert result["success"] and result["match_count"] == 0, (
            f"Expected 0 matches, got: {result}"
        )


def test_error_handling():
    """Test 14: Error handling scenarios."""

    # Test invalid regex pattern
    is_valid, error = _validate_pattern("[unclosed", True)
    assert not is_valid, "Expected invalid regex to return False"
    assert "Invalid regex pattern" in error, f"Expected 'Invalid regex pattern' in error: {error}"

    # Test invalid flags
    flags, error = _parse_flags("xyz")
    assert error, "Expected error for invalid flags"
    assert "Invalid flag" in error, f"Expected 'Invalid flag' in error: {error}"

    # Test non-existent file
    result = swift_search_pattern("/non/existent/file.swift", "pattern")
    assert not result["success"] and "File not found" in result["error"], (
        f"Expected 'File not found' in error: {result}"
    )

    # Test non-Swift file
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        txt_file = os.path.join(temp_dir, "test.txt")
        with open(txt_file, "w") as f:
            f.write("content")

        result = swift_search_pattern(txt_file, "pattern")
        assert not result["success"] and "Not a Swift file" in result["error"], (
            f"Expected 'Not a Swift file' in error: {result}"
        )


def test_empty_file():
    """Test 15: Empty file handling."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = ""
        file_path = create_test_swift_file(content, temp_dir)

        result = swift_search_pattern(file_path, "anything")

        assert result["success"] and result["match_count"] == 0, (
            f"Expected 0 matches, got: {result}"
        )


def test_complex_swift_patterns():
    """Test 16: Complex Swift language patterns."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        content = """import Foundation

actor DatabaseActor {
    private var data: [String: Any] = [:]

    func getValue(for key: String) async -> Any? {
        return data[key]
    }
}

@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

@resultBuilder
struct HTMLBuilder {
    static func buildBlock(_ components: String...) -> String {
        return components.joined()
    }
}"""
        file_path = create_test_swift_file(content, temp_dir)

        # Search for actor keyword
        result1 = swift_search_pattern(file_path, r"actor \w+")

        # Search for @main attribute
        result2 = swift_search_pattern(file_path, r"@main")

        # Search for @resultBuilder
        result3 = swift_search_pattern(file_path, r"@resultBuilder")

        assert isinstance(result1, dict), f"Expected dict response, got {type(result1)}"
        assert result1.get("success", False), f"Expected success, got: {result1}"
        assert isinstance(result2, dict), f"Expected dict response, got {type(result2)}"
        assert result2.get("success", False), f"Expected success, got: {result2}"
        assert isinstance(result3, dict), f"Expected dict response, got {type(result3)}"
        assert result3.get("success", False), f"Expected success, got: {result3}"


def test_performance():
    """Test 17: Performance with larger content."""
    with tempfile.TemporaryDirectory(prefix="swift_search_pattern_test_") as temp_dir:
        # Create larger Swift content
        large_content = "import Foundation\n\n"

        # Add many classes and methods
        for i in range(100):
            large_content += f"""
class TestClass{i} {{
    func method{i}() {{
        print("method {i}")
        let value{i} = {i}
    }}

    var property{i}: Int = {i}
}}
"""

        file_path = create_test_swift_file(large_content, temp_dir)

        # Search for print statements
        result = swift_search_pattern(file_path, r'print\("method \d+"\)')

        assert result["success"] and result["match_count"] == 100, (
            f"Expected 100 matches, got: {result}"
        )


def test_helper_functions():
    """Test 18: Helper function validation."""
    # Test _get_line_number_and_char
    content = "line1\nline2\nline3\n"
    line, char = _get_line_number_and_char(content, 8)  # Position of 'n' in line2
    assert line == 2, f"Expected line 2, got {line}"
    assert char == 3, f"Expected char 3, got {char}"

    # Test _get_context_lines
    context = _get_context_lines(content, 6, 11, 1)  # "line2" with 1 line context
    assert "line1" in context, f"Expected 'line1' in context: {context}"
    assert "line2" in context, f"Expected 'line2' in context: {context}"
    assert "line3" in context, f"Expected 'line3' in context: {context}"
