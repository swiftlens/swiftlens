#!/usr/bin/env python3
"""
Test file for performance and scalability of symbol definitions

Usage: pytest test/tools/test_performance_definitions.py

This test creates large Swift files and tests performance characteristics.
"""

import os
import shutil
import tempfile
import time

import pytest

# Mark all tests in this file as slow due to performance testing nature
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


def create_large_swift_file(num_classes=100, methods_per_class=20):
    """Create a large Swift file with many classes and methods for performance testing."""
    swift_content = """import Foundation
import SwiftUI

// Performance test file with {num_classes} classes and {methods_per_class} methods each
// Total symbols: {total_symbols}

""".format(  # noqa: UP032
        num_classes=num_classes,
        methods_per_class=methods_per_class,
        total_symbols=num_classes * (methods_per_class + 1),  # +1 for class declaration
    )

    for class_i in range(num_classes):
        class_name = f"TestClass{class_i:03d}"

        swift_content += f"""
class {class_name} {{
    private var id: String = "{class_i}"
    private var data: [String: Any] = [:]

    init(id: String = "{class_i}") {{
        self.id = id
    }}
"""

        # Add methods to the class
        for method_i in range(methods_per_class):
            method_name = f"testMethod{method_i:03d}"
            swift_content += f"""
    func {method_name}() -> String {{
        return "Result from {class_name}.{method_name}"
    }}

    func {method_name}WithParam(_ param: String) -> String {{
        return "Result from {class_name}.{method_name}: \\(param)"
    }}
"""

        swift_content += "}\n"

    # Add some global functions for variety
    swift_content += """
// Global utility functions
func performanceTestUtility() -> String {
    return "Utility function"
}

func measureExecutionTime<T>(_ block: () -> T) -> (result: T, time: TimeInterval) {
    let startTime = CFAbsoluteTimeGetCurrent()
    let result = block()
    let timeElapsed = CFAbsoluteTimeGetCurrent() - startTime
    return (result, timeElapsed)
}

extension String {
    func performanceTestExtension() -> String {
        return "Extended: \\(self)"
    }
}
"""

    return swift_content


def create_deeply_nested_swift_file():
    """Create a Swift file with deeply nested structures for complexity testing."""
    swift_content = """import Foundation

// Deeply nested structure for complexity testing
class OuterClass {
    class MiddleClass1 {
        class InnerClass1 {
            struct DeepStruct1 {
                enum DeepEnum1 {
                    case option1
                    case option2(String)

                    func deepMethod1() -> String {
                        return "Deep method 1"
                    }
                }

                let deepProperty1: String = "Deep property"

                func deepMethod2() -> DeepEnum1 {
                    return .option1
                }
            }

            func innerMethod1() -> DeepStruct1 {
                return DeepStruct1()
            }
        }

        class InnerClass2 {
            struct DeepStruct2 {
                func deepMethod3() -> String {
                    return "Deep method 3"
                }
            }
        }

        func middleMethod1() -> InnerClass1 {
            return InnerClass1()
        }
    }

    class MiddleClass2 {
        func middleMethod2() -> String {
            return "Middle method 2"
        }
    }

    func outerMethod() -> MiddleClass1 {
        return MiddleClass1()
    }
}

// Protocol with complex requirements
protocol ComplexProtocol {
    associatedtype DataType
    associatedtype ResultType

    func complexMethod1<T: Hashable>(_ input: T) -> ResultType
    func complexMethod2(data: DataType) async throws -> ResultType
    var complexProperty: DataType { get set }
}

// Generic class implementing complex protocol
class GenericComplexClass<T: Hashable, U: Codable>: ComplexProtocol {
    typealias DataType = T
    typealias ResultType = U

    var complexProperty: T

    init(data: T) {
        self.complexProperty = data
    }

    func complexMethod1<V: Hashable>(_ input: V) -> U {
        // Complex implementation would go here
        fatalError("Not implemented")
    }

    func complexMethod2(data: T) async throws -> U {
        // Complex async implementation would go here
        fatalError("Not implemented")
    }
}
"""

    return swift_content


@pytest.fixture
def large_swift_file():
    """Create a large Swift file for performance testing."""
    temp_dir = tempfile.mkdtemp(prefix="swift_performance_test_")
    large_file_path = os.path.join(temp_dir, "LargeFile.swift")

    # Create large file (100 classes, 20 methods each)
    large_content = create_large_swift_file(100, 20)

    with open(large_file_path, "w") as f:
        f.write(large_content)

    yield large_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def nested_swift_file():
    """Create a Swift file with deeply nested structures."""
    temp_dir = tempfile.mkdtemp(prefix="swift_nested_test_")
    nested_file_path = os.path.join(temp_dir, "NestedStructures.swift")

    with open(nested_file_path, "w") as f:
        f.write(create_deeply_nested_swift_file())

    yield nested_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_large_file_symbol_lookup(large_swift_file):
    """Test 1: Large file with many symbols"""
    os.path.getsize(large_swift_file) / (1024 * 1024)

    # Test finding definition in large file
    test_symbol = "TestClass050"  # Middle of the file

    start_time = time.time()
    result = swift_get_symbol_definition(large_swift_file, test_symbol)
    end_time = time.time()
    execution_time = end_time - start_time

    definitions = parse_definition_output(result)

    if definitions:
        # Performance benchmark - should complete within reasonable time
        assert execution_time < 10.0, f"Performance too slow: {execution_time:.3f}s >= 10.0s"
    else:
        pytest.fail(f"No definition found for {test_symbol} (took {execution_time:.3f}s)")


@pytest.mark.lsp
def test_batch_symbol_lookups(large_swift_file):
    """Test 2: Multiple symbol lookups in large file"""
    test_symbols = [f"TestClass{i:03d}" for i in range(0, 100, 10)]  # Every 10th class

    start_time = time.time()
    found_count = 0

    for symbol in test_symbols:
        result = swift_get_symbol_definition(large_swift_file, symbol)
        definitions = parse_definition_output(result)
        if definitions:
            found_count += 1

    end_time = time.time()
    batch_execution_time = end_time - start_time
    avg_time_per_lookup = batch_execution_time / len(test_symbols)

    # Should find most symbols and complete in reasonable time
    assert found_count >= len(test_symbols) * 0.8, (
        f"Only found {found_count}/{len(test_symbols)} symbols"
    )
    assert avg_time_per_lookup < 2.0, f"Batch performance too slow: {avg_time_per_lookup:.3f}s avg"


@pytest.mark.lsp
def test_deeply_nested_structure_complexity(nested_swift_file):
    """Test 3: Deeply nested structure complexity"""
    nested_symbols = [
        "OuterClass",
        "MiddleClass1",
        "InnerClass1",
        "DeepStruct1",
        "DeepEnum1",
        "ComplexProtocol",
        "GenericComplexClass",
    ]

    nested_found_count = 0
    nested_start_time = time.time()

    for symbol in nested_symbols:
        result = swift_get_symbol_definition(nested_swift_file, symbol)
        definitions = parse_definition_output(result)
        if definitions:
            nested_found_count += 1

    nested_end_time = time.time()
    nested_execution_time = nested_end_time - nested_start_time

    # Should find most nested symbols with acceptable performance
    assert nested_found_count >= len(nested_symbols) * 0.7, (
        f"Only found {nested_found_count}/{len(nested_symbols)} nested symbols"
    )
    assert nested_execution_time < 15.0, f"Nested lookup too slow: {nested_execution_time:.3f}s"


@pytest.mark.lsp
def test_scaling_characteristics(swift_project):
    """Test 4: Resource usage scaling characteristics"""
    temp_dir = tempfile.mkdtemp(prefix="swift_scaling_test_")

    try:
        # Test with progressively larger files
        sizes = [10, 50, 100]
        times = []

        for size in sizes:
            size_file_path = os.path.join(temp_dir, f"Size{size}.swift")
            size_content = create_large_swift_file(size, 10)

            with open(size_file_path, "w") as f:
                f.write(size_content)

            start_time = time.time()
            swift_get_symbol_definition(size_file_path, f"TestClass{size // 2:03d}")
            end_time = time.time()

            times.append(end_time - start_time)

        # Check if time scales reasonably (not exponentially)
        time_ratio_1 = times[1] / times[0] if times[0] > 0 else float("inf")
        time_ratio_2 = times[2] / times[1] if times[1] > 0 else float("inf")

        # Scaling should be reasonable - not more than 10x worse per doubling
        assert time_ratio_1 < 10.0, f"Poor scaling 10→50 classes: {time_ratio_1:.2f}x"
        assert time_ratio_2 < 10.0, f"Poor scaling 50→100 classes: {time_ratio_2:.2f}x"

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
