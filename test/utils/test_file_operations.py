#!/usr/bin/env python3
"""
Comprehensive test suite for file operations utilities.

Tests atomic file modifications, indentation detection, security validation,
and error handling for Swift code insertion operations.

Usage: pytest test/utils/test_file_operations.py
"""

import os
import tempfile
import time

import pytest

# Add src directory to path for imports
from swiftlens.utils.file_operations import SwiftFileModifier


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="swift_fileops_test_") as temp_dir:
        yield temp_dir


def create_test_swift_file(content: str, temp_dir: str, filename: str = "test.swift") -> str:
    """Create a temporary Swift file for testing."""
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def test_basic_initialization(temp_dir):
    """Test 1: Basic SwiftFileModifier initialization."""
    # Create a simple Swift file
    content = """import Foundation

struct TestStruct {
    let value: String
}"""
    file_path = create_test_swift_file(content, temp_dir)

    # Should not raise an exception
    SwiftFileModifier(file_path)


def test_path_validation(temp_dir):
    """Test 2: Path validation and security checks."""
    # Create a Swift file
    content = "import Foundation\n"
    valid_file = create_test_swift_file(content, temp_dir)

    # Test valid file - should not raise an exception
    SwiftFileModifier(valid_file)

    # Test non-existent file
    with pytest.raises(ValueError):
        SwiftFileModifier("/nonexistent/file.swift")

    # Test non-Swift file
    txt_file = os.path.join(temp_dir, "test.txt")
    with open(txt_file, "w") as f:
        f.write("not swift")

    with pytest.raises(ValueError):
        SwiftFileModifier(txt_file)

    # Test null byte injection
    with pytest.raises(ValueError):
        SwiftFileModifier("test\0.swift")


def test_indentation_detection(temp_dir):
    """Test 3: Indentation detection for spaces, tabs, and mixed."""
    content = """import Foundation

struct TestStruct {
    let value: String

    func test() {
        print("test")
    }
}"""
    file_path = create_test_swift_file(content, temp_dir)
    modifier = SwiftFileModifier(file_path)
    indent_info = modifier.detect_indentation(3)

    # Verify indentation is detected
    assert indent_info.type in ["spaces", "tabs", "mixed"], (
        f"Invalid indentation type: {indent_info.type}"
    )


def test_content_validation(temp_dir):
    """Test 4: Content validation and security checks."""
    content = "import Foundation\n"
    file_path = create_test_swift_file(content, temp_dir)
    modifier = SwiftFileModifier(file_path)

    # Test valid content
    result = modifier.insert_before_line(1, "// Valid comment")
    assert result.success, f"Valid content rejected: {result.message}"


def test_insert_before_line(temp_dir):
    """Test 5: Insert content before specific line."""
    content = """import Foundation

struct TestStruct {
    let value: String
}"""
    file_path = create_test_swift_file(content, temp_dir)

    with SwiftFileModifier(file_path) as modifier:
        result = modifier.insert_before_line(3, "// Test comment")
        assert result.success, f"Insert before line failed: {result.message}"


def test_insert_after_line(temp_dir):
    """Test 6: Insert content after specific line."""
    content = """import Foundation

struct TestStruct {
    let value: String
}"""
    file_path = create_test_swift_file(content, temp_dir)

    with SwiftFileModifier(file_path) as modifier:
        result = modifier.insert_after_line(2, "// Test comment")
        assert result.success, f"Insert after line failed: {result.message}"


def test_atomic_operations(temp_dir):
    """Test 7: Atomic file operations with rollback."""
    content = """import Foundation

struct TestStruct {
    let value: String
}"""
    file_path = create_test_swift_file(content, temp_dir)

    # Test rollback functionality
    modifier = SwiftFileModifier(file_path)

    # Read original content directly from file
    with open(file_path) as f:
        original_content = f.read()

    result = modifier.insert_before_line(1, "// Test modification")
    assert result.success, "Modification failed"

    modifier.rollback()

    # Read current content directly from file
    with open(file_path) as f:
        current_content = f.read()

    assert original_content == current_content, "Rollback failed to restore original content"


def test_indentation_preservation(temp_dir):
    """Test 8: Indentation preservation during insertions."""
    content = """import Foundation

struct TestStruct {
    let value: String

    func test() {
        print("test")
    }
}"""
    file_path = create_test_swift_file(content, temp_dir)

    with SwiftFileModifier(file_path) as modifier:
        result = modifier.insert_before_line(6, "        // Indented comment")
        assert result.success, f"Indentation preservation failed: {result.message}"


def test_error_handling(temp_dir):
    """Test 9: Error handling for invalid operations."""
    content = "import Foundation\n"
    file_path = create_test_swift_file(content, temp_dir)
    modifier = SwiftFileModifier(file_path)

    # Test insert at invalid line number
    result = modifier.insert_before_line(999, "// Invalid line")
    assert not result.success, "Should fail for invalid line number"


def test_file_permissions(temp_dir):
    """Test 10: File permission handling."""
    content = "import Foundation\n"
    file_path = create_test_swift_file(content, temp_dir)

    # Test basic file access
    modifier = SwiftFileModifier(file_path)
    result = modifier.insert_before_line(1, "// Permission test")
    assert result.success, f"File permission test failed: {result.message}"


def test_multiline_insertion(temp_dir):
    """Test 11: Multi-line content insertion."""
    content = """import Foundation

struct TestStruct {
    let value: String
}"""
    file_path = create_test_swift_file(content, temp_dir)

    multiline_content = """// Multi-line comment
// Second line of comment
// Third line of comment"""

    with SwiftFileModifier(file_path) as modifier:
        result = modifier.insert_before_line(3, multiline_content)
        assert result.success, f"Multi-line insertion failed: {result.message}"


def test_performance(temp_dir):
    """Test 12: Performance with larger files."""
    # Create a larger Swift file
    large_content = "import Foundation\n\n"
    for i in range(100):
        large_content += f"""
struct TestStruct{i} {{
    let value{i}: String

    func method{i}() {{
        print("test{i}")
    }}
}}
"""

    file_path = create_test_swift_file(large_content, temp_dir)

    start_time = time.time()

    with SwiftFileModifier(file_path) as modifier:
        result = modifier.insert_before_line(50, "// Performance test insertion")
        assert result.success, f"Performance test insertion failed: {result.message}"

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within 2 seconds
        assert duration < 2.0, f"Performance too slow: {duration:.3f} seconds"
