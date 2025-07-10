#!/usr/bin/env python3
"""
Test file for swift_validate_file tool

Usage: python3 test/tools/test_swift_validate_file.py

This test creates sample Swift files and tests the swift_validate_file tool functionality.
"""

import os
import shutil
import sys
import tempfile
import time

# Add src directory to path for imports
from swiftlens.tools.swift_validate_file import (
    swift_validate_file,
    swift_validate_file_basic,
    swift_validate_file_fast,
)


def create_valid_swift_file():
    """Create a valid Swift file for testing."""
    swift_content = """import Foundation

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

class UserService {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
    }

    func fetchUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }
}

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
"""
    return swift_content


def create_syntax_error_file():
    """Create a Swift file with syntax errors."""
    swift_content = """import Foundation

struct User {
    let id: String
    var name String  // Missing colon
    var email: String

    func validateEmail() -> Bool {
        return email.contains("@"  // Missing closing parenthesis
    }

    static func createEmpty() -> User {
        return User(id: "", name: "", email: "")
    // Missing closing brace
}

class UserService {
    private var users: [User] = []

    func addUser(_ user: User {  // Missing closing parenthesis
        users.append(user)
    }

    func fetchUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }
"""
    return swift_content


def create_type_error_file():
    """Create a Swift file with type errors."""
    swift_content = """import Foundation

struct User {
    let id: String
    var name: String
    var email: String

    func validateEmail() -> Bool {
        return invalidFunction()  // Function doesn't exist
    }

    static func createEmpty() -> User {
        return User(id: 123, name: "test", email: "test")  // Wrong type for id
    }
}

class UserService {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
        let count: String = users.count  // Wrong type assignment
    }

    func fetchUser(by id: String) -> User? {
        return users.first { $0.unknownProperty == id }  // Unknown property
    }
}
"""
    return swift_content


def create_import_error_file():
    """Create a Swift file with import errors."""
    swift_content = """import Foundation
import NonExistentFramework  // This framework doesn't exist
import UIKit.NonExistentModule  // This module doesn't exist

struct User {
    let id: String
    var name: String

    func useNonExistentType() -> SomeUnknownType {
        return SomeUnknownType()
    }
}
"""
    return swift_content


def create_warning_file():
    """Create a Swift file that should generate warnings."""
    swift_content = """import Foundation

struct User {
    let id: String
    var name: String

    func validateName() -> Bool {
        let unusedVariable = "test"  // Should generate unused variable warning
        return !name.isEmpty
    }
}

class UserService {
    private var users: [User] = []

    func addUser(_ user: User) {
        let x = 42  // Unused variable
        users.append(user)
    }
}
"""
    return swift_content


def create_empty_swift_file():
    """Create an empty Swift file."""
    return ""


def create_large_swift_file():
    """Create a large Swift file for performance testing."""
    swift_content = """import Foundation

"""
    # Generate many structs and classes
    for i in range(100):
        swift_content += f"""
struct TestStruct{i} {{
    let property{i}: String = "test{i}"

    func method{i}() -> String {{
        return property{i}
    }}
}}

class TestClass{i} {{
    private var value{i}: Int = {i}

    func getValue{i}() -> Int {{
        return value{i}
    }}
}}
"""
    return swift_content


def create_package_swift_context():
    """Create a simple Package.swift for testing project context."""
    package_content = """// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "TestPackage",
    targets: [
        .target(
            name: "TestPackage",
            dependencies: []),
        .testTarget(
            name: "TestPackageTests",
            dependencies: ["TestPackage"]),
    ]
)
"""
    return package_content


def run_test():
    """Run comprehensive tests for swift_validate_file tool."""
    print("🧪 Testing swift_validate_file tool...")
    print("=" * 50)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="swift_validate_test_")

    try:
        # Test 1: Valid Swift file
        print("\n📋 Test 1: Validating correct Swift file")
        valid_file = os.path.join(temp_dir, "ValidFile.swift")

        with open(valid_file, "w") as f:
            f.write(create_valid_swift_file())

        result = swift_validate_file(valid_file)
        print(f"Result: {result}")

        if result.get("success") and result.get("validation_result") == "No errors":
            print("✅ Test 1 passed: Valid file correctly validated")
        else:
            print("❌ Test 1 failed: Expected 'No errors'")

        # Test 2: Syntax errors
        print("\n📋 Test 2: Validating file with syntax errors")
        syntax_error_file = os.path.join(temp_dir, "SyntaxErrors.swift")

        with open(syntax_error_file, "w") as f:
            f.write(create_syntax_error_file())

        result = swift_validate_file(syntax_error_file)
        print(f"Result:\n{result}")

        if (
            result.get("success")
            and "error:" in result.get("validation_result", "")
            and result.get("has_errors")
        ):
            print("✅ Test 2 passed: Syntax errors correctly detected")
        else:
            print("❌ Test 2 failed: Expected syntax errors")

        # Test 3: Type errors
        print("\n📋 Test 3: Validating file with type errors")
        type_error_file = os.path.join(temp_dir, "TypeErrors.swift")

        with open(type_error_file, "w") as f:
            f.write(create_type_error_file())

        result = swift_validate_file(type_error_file)
        print(f"Result:\n{result}")

        if (
            result.get("success")
            and "error:" in result.get("validation_result", "")
            and result.get("has_errors")
        ):
            print("✅ Test 3 passed: Type errors correctly detected")
        else:
            print("❌ Test 3 failed: Expected type errors")

        # Test 4: Import errors
        print("\n📋 Test 4: Validating file with import errors")
        import_error_file = os.path.join(temp_dir, "ImportErrors.swift")

        with open(import_error_file, "w") as f:
            f.write(create_import_error_file())

        result = swift_validate_file(import_error_file)
        print(f"Result:\n{result}")

        if (
            result.get("success")
            and "error:" in result.get("validation_result", "")
            and result.get("has_errors")
        ):
            print("✅ Test 4 passed: Import errors correctly detected")
        else:
            print("❌ Test 4 failed: Expected import errors")

        # Test 5: File with warnings
        print("\n📋 Test 5: Validating file with warnings")
        warning_file = os.path.join(temp_dir, "WithWarnings.swift")

        with open(warning_file, "w") as f:
            f.write(create_warning_file())

        result = swift_validate_file(warning_file)
        print(f"Result:\n{result}")

        # Warnings might not always be generated, so this is a soft test
        if (result.get("success") and result.get("validation_result") == "No errors") or (
            result.get("success") and "warning:" in result.get("validation_result", "")
        ):
            print("✅ Test 5 passed: Warnings handled correctly")
        else:
            print("❓ Test 5 unclear: Warning detection varies by Swift version")

        # Test 6: Empty file
        print("\n📋 Test 6: Validating empty Swift file")
        empty_file = os.path.join(temp_dir, "EmptyFile.swift")

        with open(empty_file, "w") as f:
            f.write(create_empty_swift_file())

        result = swift_validate_file(empty_file)
        print(f"Result: {result}")

        if result.get("success") and result.get("validation_result") == "No errors":
            print("✅ Test 6 passed: Empty file handled correctly")
        else:
            print("❌ Test 6 failed: Expected 'No errors' for empty file")

        # Test 7: Non-existent file
        print("\n📋 Test 7: Testing non-existent file")
        non_existent_file = os.path.join(temp_dir, "NonExistent.swift")

        result = swift_validate_file(non_existent_file)
        print(f"Result: {result}")

        if not result.get("success") and "File not found" in result.get("error", ""):
            print("✅ Test 7 passed: Non-existent file handled with error")
        else:
            print("❌ Test 7 failed: Expected file not found error")

        # Test 8: Non-Swift file
        print("\n📋 Test 8: Testing non-Swift file")
        non_swift_file = os.path.join(temp_dir, "NotSwift.txt")

        with open(non_swift_file, "w") as f:
            f.write("This is not a Swift file")

        result = swift_validate_file(non_swift_file)
        print(f"Result: {result}")

        if not result.get("success") and "Swift file" in result.get("error", ""):
            print("✅ Test 8 passed: Non-Swift file rejected")
        else:
            print("❌ Test 8 failed: Expected non-Swift file error")

        # Test 9: Basic validation mode
        print("\n📋 Test 9: Testing basic validation mode")
        result = swift_validate_file_basic(valid_file)
        print(f"Result: {result}")

        if result.get("success") and result.get("validation_result") == "No errors":
            print("✅ Test 9 passed: Basic validation works")
        else:
            print("❌ Test 9 failed: Basic validation failed")

        # Test 10: Fast validation mode
        print("\n📋 Test 10: Testing fast validation mode")
        result = swift_validate_file_fast(valid_file)
        print(f"Result: {result}")

        if result.get("success") and result.get("validation_result") == "No errors":
            print("✅ Test 10 passed: Fast validation works")
        else:
            print("❌ Test 10 failed: Fast validation failed")

        # Test 11: Large file performance
        print("\n📋 Test 11: Testing large file performance")
        large_file = os.path.join(temp_dir, "LargeFile.swift")

        with open(large_file, "w") as f:
            f.write(create_large_swift_file())

        start_time = time.time()
        result = swift_validate_file(large_file)
        end_time = time.time()

        print(f"Processing time: {end_time - start_time:.2f} seconds")
        print(f"Result: {result}")

        # Should handle large files within reasonable time
        if (
            (end_time - start_time) < 30
            and result.get("success")
            and result.get("validation_result") == "No errors"
        ):
            print("✅ Test 11 passed: Large file processed efficiently")
        else:
            print("❌ Test 11 failed: Large file processing too slow or failed")

        # Test 12: Package.swift context (if possible)
        print("\n📋 Test 12: Testing Package.swift context")

        # Create a subdirectory with Package.swift
        package_dir = os.path.join(temp_dir, "TestPackage")
        os.makedirs(package_dir, exist_ok=True)

        package_file = os.path.join(package_dir, "Package.swift")
        with open(package_file, "w") as f:
            f.write(create_package_swift_context())

        # Create a Swift file in the package
        sources_dir = os.path.join(package_dir, "Sources", "TestPackage")
        os.makedirs(sources_dir, exist_ok=True)

        package_swift_file = os.path.join(sources_dir, "TestFile.swift")
        with open(package_swift_file, "w") as f:
            f.write(create_valid_swift_file())

        result = swift_validate_file(package_swift_file)
        print(f"Result: {result}")

        # Package context might fail due to various reasons, so this is informational
        if "No errors" in result or "Error:" in result:
            print("✅ Test 12 passed: Package context handled gracefully")
        else:
            print("❓ Test 12 unclear: Package context results vary")

        # Test 13: Relative path handling
        print("\n📋 Test 13: Testing relative path handling")

        # Change to temp directory and use relative path
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            result = swift_validate_file("ValidFile.swift")  # Relative path
            print(f"Result: {result}")

            if result.get("success") and result.get("validation_result") == "No errors":
                print("✅ Test 13 passed: Relative path handled correctly")
            else:
                print("❌ Test 13 failed: Relative path not handled properly")
        finally:
            os.chdir(original_cwd)

        print("\n" + "=" * 50)
        print("🎯 All swift_validate_file tests completed!")

    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        return False

    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 Cleaned up test directory: {temp_dir}")
        except Exception as e:
            print(f"⚠️ Failed to clean up: {str(e)}")

    return True


if __name__ == "__main__":
    success = run_test()
    if not success:
        sys.exit(1)
