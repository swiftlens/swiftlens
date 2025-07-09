#!/usr/bin/env python3
"""
Master test runner for all Swift Context MCP tools

Usage: python3 test/tools/run_all_tests.py

This script runs all individual tool tests and provides a summary report.
"""

import glob
import os
import subprocess
import sys
import time
from pathlib import Path


def run_single_test(test_file):
    """Run a single test file and return the result."""
    print(f"\n{'=' * 60}")
    print(f"Running: {test_file}")
    print("=" * 60)

    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout per test
        )
        end_time = time.time()

        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        # Explicit success/failure indication
        if result.returncode == 0:
            print(f"✅ {os.path.basename(test_file)} PASSED")
        else:
            print(f"❌ {os.path.basename(test_file)} FAILED (exit code: {result.returncode})")

        duration = end_time - start_time

        return {
            "name": os.path.basename(test_file),
            "success": result.returncode == 0,
            "duration": duration,
            "output": result.stdout,
            "error": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "name": os.path.basename(test_file),
            "success": False,
            "duration": 10.0,
            "output": "",
            "error": "Test timed out after 10 seconds",
        }
    except Exception as e:
        return {
            "name": os.path.basename(test_file),
            "success": False,
            "duration": 0.0,
            "output": "",
            "error": f"Failed to run test: {e}",
        }


def main():
    """Run all tests and generate a summary report."""
    print("Swift Context MCP - All Tools Test Suite")
    print("=" * 60)

    # Find test directory
    test_dir = Path(__file__).parent

    # Automatic test discovery: find all test_*.py files
    test_pattern = str(test_dir / "test_*.py")
    discovered_test_files = glob.glob(test_pattern)

    # Exclude the runner itself if it matches the pattern
    runner_script = str(Path(__file__).resolve())
    test_files = [f for f in discovered_test_files if str(Path(f).resolve()) != runner_script]

    # Sort for consistent execution order
    test_files.sort()

    if not test_files:
        print("❌ No test files found matching pattern 'test_*.py'")
        return False

    print(f"🔍 Discovered {len(test_files)} test files automatically:")
    for test_file in test_files:
        print(f"  • {Path(test_file).name}")

    print(f"\nTest directory: {test_dir}")

    # Run all tests
    results = []
    start_time = time.time()

    for test_file_path in test_files:
        result = run_single_test(test_file_path)
        results.append(result)

    total_time = time.time() - start_time

    # Generate summary report
    print("\n" + "=" * 60)
    print("TEST SUMMARY REPORT")
    print("=" * 60)

    passed_tests = [r for r in results if r["success"]]
    failed_tests = [r for r in results if not r["success"]]

    print(f"Total tests run: {len(results)}")
    print(f"Tests passed: {len(passed_tests)} ✅")
    print(f"Tests failed: {len(failed_tests)} ❌")
    print(f"Total duration: {total_time:.2f} seconds")

    print("\nDETAILED RESULTS:")
    print("-" * 40)

    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{result['name']:<35} {status} ({result['duration']:.2f}s)")

        if not result["success"] and result["error"]:
            print(f"  Error: {result['error']}")

    if failed_tests:
        print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
        for result in failed_tests:
            print(f"  • {result['name']}")
            if result["error"]:
                print(f"    {result['error']}")

    # Overall result
    all_passed = len(failed_tests) == 0

    if all_passed:
        print(f"\n🎉 ALL TESTS PASSED! ({len(passed_tests)}/{len(results)})")
        return True
    else:
        print(f"\n💥 SOME TESTS FAILED! ({len(passed_tests)}/{len(results)} passed)")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test run interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)
