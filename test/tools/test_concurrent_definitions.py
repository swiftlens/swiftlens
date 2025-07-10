#!/usr/bin/env python3
"""
Test file for concurrent symbol definition requests

Usage: pytest test/tools/test_concurrent_definitions.py

This test validates concurrent access to the get_symbol_definition tool.
"""

import os
import queue
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# Mark all tests in this file as slow due to concurrent LSP process creation
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


def create_concurrent_test_swift_file():
    """Create a Swift file for concurrent testing."""
    swift_content = """import Foundation

// Concurrent test file with various symbols
class ConcurrentTestManager {
    private var data: [String: Any] = [:]
    private let queue = DispatchQueue(label: "test.concurrent")

    init() {
        setupInitialData()
    }

    func setupInitialData() {
        data["initialized"] = true
    }

    func addData(key: String, value: Any) {
        queue.sync {
            data[key] = value
        }
    }

    func getData(for key: String) -> Any? {
        return queue.sync {
            return data[key]
        }
    }

    func processDataAsync() async -> [String: Any] {
        return await withCheckedContinuation { continuation in
            queue.async {
                let processedData = self.data.mapValues { value in
                    return "Processed: \\(value)"
                }
                continuation.resume(returning: processedData)
            }
        }
    }
}

class ConcurrentDataProcessor {
    private let processingQueue = DispatchQueue(label: "processing")

    func processData(_ data: String) async -> String {
        return await withCheckedContinuation { continuation in
            processingQueue.async {
                let result = "Async processed: \\(data)"
                continuation.resume(returning: result)
            }
        }
    }
}

struct ConcurrentValue {
    let id: String
    var value: Int

    init(id: String, value: Int = 0) {
        self.id = id
        self.value = value
    }

    mutating func increment() {
        value += 1
    }

    func doubled() -> Int {
        return value * 2
    }
}

enum ConcurrentOperation {
    case read(String)
    case write(String, Any)
    case delete(String)

    var description: String {
        switch self {
        case .read(let key):
            return "Reading \\(key)"
        case .write(let key, let value):
            return "Writing \\(value) to \\(key)"
        case .delete(let key):
            return "Deleting \\(key)"
        }
    }
}

// Global functions for testing
func globalConcurrentFunction() -> String {
    return "Global concurrent function"
}

func globalAsyncFunction() async -> String {
    return "Global async function"
}

// Extension for additional methods
extension ConcurrentTestManager {
    func batchProcess(_ items: [String]) -> [String] {
        return items.map { item in
            return "Batch processed: \\(item)"
        }
    }

    func concurrentBatchProcess(_ items: [String]) async -> [String] {
        return await withTaskGroup(of: String.self) { group in
            for item in items {
                group.addTask {
                    return "Concurrent processed: \\(item)"
                }
            }

            var results: [String] = []
            for await result in group {
                results.append(result)
            }
            return results
        }
    }
}
"""
    return swift_content


def concurrent_symbol_lookup(file_path, symbol_name, thread_id, result_queue, iterations=5):
    """Perform multiple symbol lookups from a single thread."""
    results = []
    thread_start_time = time.time()

    try:
        for i in range(iterations):
            start_time = time.time()
            output = swift_get_symbol_definition(file_path, symbol_name)
            end_time = time.time()

            definitions = parse_definition_output(output)

            results.append(
                {
                    "thread_id": thread_id,
                    "iteration": i,
                    "symbol": symbol_name,
                    "success": len(definitions) > 0,
                    "execution_time": end_time - start_time,
                    "definitions": definitions,
                }
            )

        thread_end_time = time.time()
        result_queue.put(
            {
                "thread_id": thread_id,
                "results": results,
                "total_time": thread_end_time - thread_start_time,
            }
        )

    except Exception as e:
        result_queue.put(
            {
                "thread_id": thread_id,
                "error": str(e),
                "results": [],
                "total_time": time.time() - thread_start_time,
            }
        )


@pytest.fixture
def concurrent_test_file():
    """Create a temporary Swift file for concurrent testing."""
    temp_dir = tempfile.mkdtemp(prefix="swift_concurrent_test_")
    test_file_path = os.path.join(temp_dir, "ConcurrentTest.swift")

    with open(test_file_path, "w") as f:
        f.write(create_concurrent_test_swift_file())

    yield test_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_concurrent_same_symbol_access(concurrent_test_file):
    """Test 1: Multiple threads accessing the same symbol concurrently."""
    result_queue = queue.Queue()
    threads = []
    num_threads = 5
    symbol_name = "ConcurrentTestManager"

    start_time = time.time()

    for i in range(num_threads):
        thread = threading.Thread(
            target=concurrent_symbol_lookup,
            args=(concurrent_test_file, symbol_name, i, result_queue, 3),
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    end_time = time.time()
    total_time = end_time - start_time

    # Collect results
    thread_results = []
    while not result_queue.empty():
        thread_results.append(result_queue.get())

    # Analyze results
    total_lookups = sum(len(tr["results"]) for tr in thread_results)
    successful_lookups = sum(
        sum(1 for r in tr["results"] if r.get("success", False)) for tr in thread_results
    )

    assert total_lookups > 0, "No lookups were performed"
    assert successful_lookups >= total_lookups * 0.9, (
        f"Only {successful_lookups}/{total_lookups} lookups successful. "
        f"Expected at least 90% success rate. Total time: {total_time:.3f}s"
    )


@pytest.mark.lsp
def test_concurrent_different_symbols(concurrent_test_file):
    """Test 2: Different symbols from different threads."""
    symbols = [
        "ConcurrentTestManager",
        "ConcurrentDataProcessor",
        "ConcurrentValue",
        "ConcurrentOperation",
        "globalConcurrentFunction",
    ]

    result_queue = queue.Queue()
    threads = []

    start_time = time.time()

    for i, symbol in enumerate(symbols):
        thread = threading.Thread(
            target=concurrent_symbol_lookup,
            args=(concurrent_test_file, symbol, i, result_queue, 3),
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    end_time = time.time()
    total_time = end_time - start_time

    # Collect and analyze results
    thread_results = []
    while not result_queue.empty():
        thread_results.append(result_queue.get())

    symbols_found = set()
    for tr in thread_results:
        for result in tr["results"]:
            if result.get("success", False):
                symbols_found.add(result["symbol"])

    assert len(symbols_found) >= len(symbols) * 0.8, (
        f"Only found {len(symbols_found)}/{len(symbols)} symbols. "
        f"Expected at least 80% symbols found. Total time: {total_time:.3f}s"
    )


@pytest.mark.lsp
def test_threadpool_executor_concurrent_access(concurrent_test_file):
    """Test 3: ThreadPoolExecutor concurrent access."""

    def lookup_symbol(args):
        file_path, symbol, thread_id = args
        start_time = time.time()
        try:
            output = swift_get_symbol_definition(file_path, symbol)
            definitions = parse_definition_output(output)
            return {
                "thread_id": thread_id,
                "symbol": symbol,
                "success": len(definitions) > 0,
                "execution_time": time.time() - start_time,
                "definitions": definitions,
            }
        except Exception as e:
            return {
                "thread_id": thread_id,
                "symbol": symbol,
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    # Create tasks for executor
    test_symbols = [
        "ConcurrentTestManager",
        "ConcurrentDataProcessor",
        "ConcurrentValue",
    ] * 3  # 9 tasks

    tasks = []
    for i, symbol in enumerate(test_symbols):
        tasks.append((concurrent_test_file, symbol, i))

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_task = {executor.submit(lookup_symbol, task): task for task in tasks}
        results = []

        for future in as_completed(future_to_task):
            try:
                result = future.result(timeout=5)  # 5 second timeout
                results.append(result)
            except Exception as e:
                task = future_to_task[future]
                results.append(
                    {
                        "symbol": task[1],
                        "success": False,
                        "error": str(e),
                        "execution_time": 0,
                    }
                )

    end_time = time.time()
    executor_time = end_time - start_time

    successful_executor = sum(1 for r in results if r.get("success", False))

    assert successful_executor >= len(tasks) * 0.9, (
        f"Only {successful_executor}/{len(tasks)} tasks successful with ThreadPoolExecutor. "
        f"Expected at least 90% success rate. Executor time: {executor_time:.3f}s"
    )


@pytest.mark.lsp
def test_race_condition_detection(concurrent_test_file):
    """Test 4: Race condition detection (stress test)."""

    def lookup_symbol(args):
        file_path, symbol, thread_id = args
        start_time = time.time()
        try:
            output = swift_get_symbol_definition(file_path, symbol)
            definitions = parse_definition_output(output)
            return {
                "thread_id": thread_id,
                "symbol": symbol,
                "success": len(definitions) > 0,
                "execution_time": time.time() - start_time,
                "definitions": definitions,
            }
        except Exception as e:
            return {
                "thread_id": thread_id,
                "symbol": symbol,
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    stress_symbols = ["ConcurrentTestManager"] * 20  # Same symbol 20 times
    stress_tasks = [(concurrent_test_file, symbol, i) for i, symbol in enumerate(stress_symbols)]

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        stress_results = list(executor.map(lookup_symbol, stress_tasks))

    end_time = time.time()
    stress_time = end_time - start_time

    stress_successful = sum(1 for r in stress_results if r.get("success", False))

    # Check for consistency in results
    successful_definitions = [r["definitions"] for r in stress_results if r.get("success", False)]

    if successful_definitions:
        consistent_results = (
            len(
                {
                    tuple(sorted((d["file_path"], d["line"], d["char"]) for d in defs))
                    for defs in successful_definitions
                }
            )
            <= 1
        )  # All successful results should be identical
    else:
        consistent_results = True  # No results to compare

    assert stress_successful >= len(stress_tasks) * 0.95, (
        f"Only {stress_successful}/{len(stress_tasks)} stress tasks successful. "
        f"Expected at least 95% success rate. Stress time: {stress_time:.3f}s"
    )

    assert consistent_results, (
        "Results were not consistent across concurrent executions - possible race condition"
    )
