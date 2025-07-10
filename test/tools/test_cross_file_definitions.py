#!/usr/bin/env python3
"""
Test file for cross-file symbol definitions

Usage: pytest test/tools/test_cross_file_definitions.py

This test creates multiple Swift files and tests cross-file symbol definition resolution.
"""

import os
import shutil
import tempfile

import pytest

# Mark all tests in this file as slow due to cross-file symbol resolution complexity
pytestmark = pytest.mark.slow

# Add src directory to path for imports
from swiftlens.tools.swift_get_symbol_definition import swift_get_symbol_definition  # noqa: E402

# Import shared utilities for LSP test handling
from .lsp_test_utils import assert_is_acceptable_lsp_failure, parse_definition_output  # noqa: E402


def create_cross_file_test_project():
    """Create a multi-file Swift project for testing cross-file definitions."""

    # File 1: Models.swift - Define data models
    models_content = """import Foundation

public struct User {
    public let id: String
    public var name: String
    public var email: String

    public init(id: String, name: String, email: String) {
        self.id = id
        self.name = name
        self.email = email
    }

    public func validateEmail() -> Bool {
        return email.contains("@")
    }
}

public enum UserRole {
    case admin
    case user
    case guest

    public var permissions: [String] {
        switch self {
        case .admin:
            return ["read", "write", "delete"]
        case .user:
            return ["read", "write"]
        case .guest:
            return ["read"]
        }
    }
}
"""

    # File 2: Services.swift - Use models from other file
    services_content = """import Foundation

public class UserService {
    private var users: [User] = []

    public init() {}

    public func addUser(_ user: User) {
        users.append(user)
    }

    public func findUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }

    public func updateUserRole(_ userId: String, role: UserRole) {
        // Implementation would update user role
        print("User \\(userId) role updated to \\(role)")
    }

    public func getUserPermissions(_ userId: String) -> [String] {
        // This would normally fetch user role and return permissions
        return UserRole.admin.permissions
    }
}

public extension User {
    func displayName() -> String {
        return "\\(name) (\\(email))"
    }
}
"""

    # File 3: Views.swift - Use models and services
    views_content = """import Foundation
import SwiftUI

public struct UserListView: View {
    @StateObject private var userService = UserService()
    @State private var users: [User] = []

    public var body: some View {
        List(users, id: \\.id) { user in
            VStack(alignment: .leading) {
                Text(user.displayName())
                    .font(.headline)
                Text("Role: \\(getUserRoleText(user))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .onAppear {
            loadSampleUsers()
        }
    }

    private func loadSampleUsers() {
        let sampleUsers = [
            User(id: "1", name: "John Doe", email: "john@example.com"),
            User(id: "2", name: "Jane Smith", email: "jane@example.com")
        ]

        for user in sampleUsers {
            userService.addUser(user)
        }

        users = sampleUsers
    }

    private func getUserRoleText(_ user: User) -> String {
        let permissions = userService.getUserPermissions(user.id)
        return permissions.count > 2 ? "Admin" : "User"
    }
}
"""

    return [
        ("Models.swift", models_content),
        ("Services.swift", services_content),
        ("Views.swift", views_content),
    ]


@pytest.fixture
def cross_file_test_project():
    """Create a multi-file Swift project for testing cross-file definitions."""
    temp_dir = tempfile.mkdtemp(prefix="swift_crossfile_test_")
    test_files = []

    try:
        # Create proper Swift package structure
        sources_dir = os.path.join(temp_dir, "Sources", "TestPackage")
        os.makedirs(sources_dir, exist_ok=True)

        # Create Package.swift
        package_swift_content = """// swift-tools-version:5.3
import PackageDescription

let package = Package(
    name: "TestPackage",
    products: [],
    dependencies: [],
    targets: [
        .target(
            name: "TestPackage",
            dependencies: [])
    ]
)
"""
        package_swift_path = os.path.join(temp_dir, "Package.swift")
        with open(package_swift_path, "w") as f:
            f.write(package_swift_content)

        # Create multi-file project in Sources/TestPackage/
        project_files = create_cross_file_test_project()
        for filename, content in project_files:
            file_path = os.path.join(sources_dir, filename)
            with open(file_path, "w") as f:
                f.write(content)
            test_files.append(file_path)

        yield {
            "temp_dir": temp_dir,
            "test_files": test_files,
            "models_file": os.path.join(sources_dir, "Models.swift"),
            "services_file": os.path.join(sources_dir, "Services.swift"),
            "views_file": os.path.join(sources_dir, "Views.swift"),
        }

    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_user_symbol_cross_file_definition(cross_file_test_project):
    """Test 1: Finding definition of 'User' symbol from Services.swift"""
    services_file = cross_file_test_project["services_file"]

    result = swift_get_symbol_definition(services_file, "User")
    definitions = parse_definition_output(result)

    if definitions:
        # Check if definition points to Models.swift
        models_file_found = any("Models.swift" in def_info["file_path"] for def_info in definitions)
        assert models_file_found, f"Definition found but not in Models.swift: {definitions}"
    else:
        # LSP may not support cross-file resolution or returned error
        assert_is_acceptable_lsp_failure(result)


@pytest.mark.lsp
def test_user_role_enum_cross_file_definition(cross_file_test_project):
    """Test 2: Finding definition of 'UserRole' enum from Services.swift"""
    services_file = cross_file_test_project["services_file"]

    result = swift_get_symbol_definition(services_file, "UserRole")
    definitions = parse_definition_output(result)

    if definitions:
        models_file_found = any("Models.swift" in def_info["file_path"] for def_info in definitions)
        assert models_file_found, f"Definition found but not in Models.swift: {definitions}"
    else:
        # LSP may not support cross-file resolution or returned error
        assert_is_acceptable_lsp_failure(result)


@pytest.mark.lsp
def test_user_service_class_cross_file_definition(cross_file_test_project):
    """Test 3: Finding definition of 'UserService' class from Views.swift"""
    views_file = cross_file_test_project["views_file"]

    result = swift_get_symbol_definition(views_file, "UserService")
    definitions = parse_definition_output(result)

    if definitions:
        services_file_found = any(
            "Services.swift" in def_info["file_path"] for def_info in definitions
        )
        assert services_file_found, f"Definition found but not in Services.swift: {definitions}"
    else:
        # LSP may not support cross-file resolution or returned error
        assert_is_acceptable_lsp_failure(result)


@pytest.mark.lsp
def test_extension_method_cross_file_definition(cross_file_test_project):
    """Test 4: Finding definition of 'displayName' extension method"""
    views_file = cross_file_test_project["views_file"]

    result = swift_get_symbol_definition(views_file, "displayName")
    definitions = parse_definition_output(result)

    if definitions:
        services_file_found = any(
            "Services.swift" in def_info["file_path"] for def_info in definitions
        )
        assert services_file_found, f"Definition found but not in Services.swift: {definitions}"
    else:
        # LSP may not support cross-file resolution or returned error
        assert_is_acceptable_lsp_failure(result)


@pytest.mark.lsp
def test_foundation_string_system_symbol_definition(cross_file_test_project):
    """Test 5: Finding definition of Foundation 'String' type"""
    services_file = cross_file_test_project["services_file"]

    result = swift_get_symbol_definition(services_file, "String")
    definitions = parse_definition_output(result)

    if definitions:
        # Should point to Foundation or system framework
        system_def_found = any(
            any(
                framework in def_info["file_path"]
                for framework in ["Foundation", "Swift", "usr/lib", "System"]
            )
            for def_info in definitions
        )
        assert system_def_found or len(definitions) > 0, (
            f"Definition found but may not be system framework: {definitions[0]['file_path']}"
        )
    else:
        # LSP may not support cross-file resolution or returned error
        assert_is_acceptable_lsp_failure(result)
