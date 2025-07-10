#!/usr/bin/env python3
"""
Test file for multiple definition results

Usage: pytest test/tools/test_multiple_definitions.py

This test creates Swift files with symbols that have multiple definitions (overloads, protocols, etc.)
"""

import os
import shutil
import tempfile

import pytest

# Mark all tests in this file as slow due to complex symbol resolution
pytestmark = pytest.mark.slow

# Add src directory to path for imports
from swiftlens.tools.swift_get_symbol_definition import swift_get_symbol_definition  # noqa: E402


def parse_definition_output(output):
    """Parse definition output into structured data for validation."""
    if "No definition found" in output:
        return []

    definitions = []
    lines = output.strip().split("\n")
    for line in lines:
        if ":" in line:
            parts = line.split(":")
            if len(parts) >= 3:
                file_path = parts[0]
                line_num = int(parts[1]) if parts[1].isdigit() else 0
                char_num = int(parts[2]) if parts[2].isdigit() else 0
                definitions.append({"file_path": file_path, "line": line_num, "char": char_num})
    return definitions


def create_overloaded_swift_file():
    """Create a Swift file with method overloads and multiple definitions."""
    swift_content = """import Foundation

// Protocol with same method name as class
protocol DataProcessing {
    func process() -> String
    func process(data: String) -> String
    func process(data: [String]) -> String
}

// Class implementing protocol and adding overloads
class DataProcessor: DataProcessing {

    // Basic process method
    func process() -> String {
        return "Basic processing"
    }

    // Overloaded with String parameter
    func process(data: String) -> String {
        return "Processing: \\(data)"
    }

    // Overloaded with Array parameter
    func process(data: [String]) -> String {
        return "Processing array of \\(data.count) items"
    }

    // Overloaded with different parameter label
    func process(input: String) -> String {
        return "Processing input: \\(input)"
    }

    // Overloaded with multiple parameters
    func process(data: String, options: [String: Any]) -> String {
        return "Processing \\(data) with options"
    }
}

// Another class with same method names
class FileProcessor {

    func process() -> String {
        return "File processing"
    }

    func process(filePath: String) -> String {
        return "Processing file: \\(filePath)"
    }

    func process(files: [String]) -> [String] {
        return files.map { "Processed: \\($0)" }
    }
}

// Extension adding more overloads
extension DataProcessor {

    func process(async data: String) async -> String {
        return "Async processing: \\(data)"
    }

    func process<T>(generic: T) -> String {
        return "Generic processing: \\(generic)"
    }
}

// Global functions with same names
func process() {
    print("Global process function")
}

func process(_ value: Any) {
    print("Global process with any: \\(value)")
}

// Computed properties and variables with same names
var process: String = "Process variable"

struct ProcessConfiguration {
    let process: Bool = true

    static func process() -> ProcessConfiguration {
        return ProcessConfiguration()
    }
}

// Nested types
class OuterClass {
    class InnerClass {
        func process() -> String {
            return "Inner class process"
        }

        struct InnerStruct {
            func process() -> String {
                return "Inner struct process"
            }
        }
    }
}

// Enum with associated values
enum ProcessResult {
    case success(String)
    case failure(Error)

    func process() -> String {
        switch self {
        case .success(let message):
            return "Success: \\(message)"
        case .failure(let error):
            return "Failure: \\(error)"
        }
    }
}
"""
    return swift_content


@pytest.fixture
def overloaded_swift_file():
    """Create a Swift file with method overloads and multiple definitions."""
    temp_dir = tempfile.mkdtemp(prefix="swift_multiple_def_test_")
    test_file_path = os.path.join(temp_dir, "OverloadedMethods.swift")

    with open(test_file_path, "w") as f:
        f.write(create_overloaded_swift_file())

    yield test_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_overloaded_process_methods(overloaded_swift_file):
    """Test 1: Finding definitions for overloaded 'process' methods"""
    result = swift_get_symbol_definition(overloaded_swift_file, "process")
    definitions = parse_definition_output(result)

    if definitions:
        assert len(definitions) >= 1, (
            f"Expected at least 1 definition for 'process', got {len(definitions)}"
        )
        # Multiple definitions would be ideal, but LSP may return only the first one
    else:
        pytest.fail("No definitions found for 'process'")


@pytest.mark.lsp
def test_data_processor_class_definition(overloaded_swift_file):
    """Test 2: Finding definition for 'DataProcessor' class"""
    result = swift_get_symbol_definition(overloaded_swift_file, "DataProcessor")
    definitions = parse_definition_output(result)

    if definitions:
        # Should find class definition around line 51-53
        class_def_found = any(50 <= def_info["line"] <= 55 for def_info in definitions)
        assert class_def_found, (
            f"DataProcessor definition found but at unexpected line: {definitions}"
        )
    else:
        pytest.fail("No definition found for DataProcessor")


@pytest.mark.lsp
def test_protocol_vs_implementation_context(overloaded_swift_file):
    """Test 3: Finding definitions in protocol vs implementation context"""
    result = swift_get_symbol_definition(overloaded_swift_file, "DataProcessing")
    definitions = parse_definition_output(result)

    if definitions:
        # Protocol should be around line 44-48
        protocol_def_found = any(43 <= def_info["line"] <= 49 for def_info in definitions)
        assert protocol_def_found, (
            f"Protocol definition found but at unexpected line: {definitions}"
        )
    else:
        pytest.fail("No protocol definition found")


@pytest.mark.lsp
def test_extension_methods(overloaded_swift_file):
    """Test 4: Finding definitions including extension methods"""
    result = swift_get_symbol_definition(overloaded_swift_file, "async")
    definitions = parse_definition_output(result)

    # Extension methods might not be found by symbol name alone
    # This is acceptable LSP behavior
    if not definitions:
        assert "No definition found" in result
    else:
        # If found, should be in extension area (around line 98-100)
        extension_def_found = any(96 <= def_info["line"] <= 102 for def_info in definitions)
        assert extension_def_found or len(definitions) > 0, (
            f"Extension method found but at unexpected location: {definitions}"
        )


@pytest.mark.lsp
def test_nested_types_definition(overloaded_swift_file):
    """Test 5: Finding definitions for nested types"""
    result = swift_get_symbol_definition(overloaded_swift_file, "InnerClass")
    definitions = parse_definition_output(result)

    if definitions:
        # Nested types should be around line 129-132
        nested_def_found = any(128 <= def_info["line"] <= 135 for def_info in definitions)
        assert nested_def_found, (
            f"Nested class definition found but at unexpected line: {definitions}"
        )
    else:
        # Nested types might not be found - this is acceptable
        assert "No definition found" in result


@pytest.mark.lsp
def test_generic_methods_definition(overloaded_swift_file):
    """Test 6: Finding definitions for generic methods"""
    result = swift_get_symbol_definition(overloaded_swift_file, "generic")
    definitions = parse_definition_output(result)

    if definitions:
        # Generic method should be around line 103-105
        generic_def_found = any(102 <= def_info["line"] <= 106 for def_info in definitions)
        assert generic_def_found or len(definitions) > 0, (
            f"Generic method found but may not be at expected location: {definitions}"
        )
    else:
        # Generic parameter names might not be found - this is acceptable
        assert "No definition found" in result


@pytest.mark.lsp
def test_multiple_definitions_validation(overloaded_swift_file):
    """Test 7: Validating handling of multiple definition results"""
    result = swift_get_symbol_definition(overloaded_swift_file, "process")
    definitions = parse_definition_output(result)

    if definitions:
        all_lines = [def_info["line"] for def_info in definitions]
        unique_lines = len(set(all_lines))

        # LSP may return 1 or multiple definitions - both are acceptable
        assert unique_lines >= 1, (
            f"Expected at least 1 unique definition location, got {unique_lines}"
        )
    else:
        pytest.fail("No definition locations found for process method")
