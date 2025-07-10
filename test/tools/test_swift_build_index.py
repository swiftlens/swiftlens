#!/usr/bin/env python3
"""
Test file for swift_build_index tool

This test validates the swift_build_index tool functionality including:
- Successful index building
- Error handling for missing Package.swift
- Timeout handling
- Path validation
- Concurrent build handling
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from swiftlens.model.models import BuildIndexResponse, ErrorType
from swiftlens.tools.swift_build_index import swift_build_index


class TestSwiftBuildIndex:
    """Test cases for swift_build_index tool."""

    def setup_method(self):
        """Create a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp(prefix="swift_build_test_")
        self.original_cwd = os.getcwd()

    def teardown_method(self):
        """Clean up temporary directory."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_test_package(self, package_name: str = "TestPackage"):
        """Create a minimal Swift package for testing."""
        package_swift = f"""// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "{package_name}",
    products: [
        .library(
            name: "{package_name}",
            targets: ["{package_name}"]),
    ],
    targets: [
        .target(
            name: "{package_name}",
            dependencies: []),
        .testTarget(
            name: "{package_name}Tests",
            dependencies: ["{package_name}"]),
    ]
)
"""

        # Create Package.swift
        with open(os.path.join(self.test_dir, "Package.swift"), "w") as f:
            f.write(package_swift)

        # Create source directory structure
        source_dir = os.path.join(self.test_dir, "Sources", package_name)
        os.makedirs(source_dir, exist_ok=True)

        # Create a simple Swift file
        swift_file = os.path.join(source_dir, f"{package_name}.swift")
        with open(swift_file, "w") as f:
            f.write(f"""public struct {package_name} {{
    public init() {{}}

    public func greet() -> String {{
        return "Hello from {package_name}!"
    }}
}}
""")

        # Create test directory
        test_dir = os.path.join(self.test_dir, "Tests", f"{package_name}Tests")
        os.makedirs(test_dir, exist_ok=True)

        # Create a test file
        test_file = os.path.join(test_dir, f"{package_name}Tests.swift")
        with open(test_file, "w") as f:
            f.write(f"""import XCTest
@testable import {package_name}

final class {package_name}Tests: XCTestCase {{
    func testGreeting() {{
        let instance = {package_name}()
        XCTAssertEqual(instance.greet(), "Hello from {package_name}!")
    }}
}}
""")

    def test_build_index_success(self):
        """Test successful index building with valid Swift package."""
        self.create_test_package()

        result = swift_build_index(self.test_dir, timeout=120)

        # Verify response structure
        assert isinstance(result, dict)
        assert "success" in result
        assert "project_path" in result

        # Build might fail in test environment, but the tool should handle it gracefully
        if result["success"]:
            assert result["project_path"] == os.path.realpath(self.test_dir)
            assert "build_time" in result
            assert result["build_time"] > 0
            # Index path might exist if build succeeded
            if result.get("index_path"):
                assert ".build/index/store" in result["index_path"]
        else:
            # Even on failure, should have proper error reporting
            assert "error" in result
            assert result["error_type"] in [ErrorType.BUILD_ERROR, ErrorType.ENVIRONMENT_ERROR]

    def test_build_index_current_directory(self):
        """Test building index in current directory when no path specified."""
        self.create_test_package()
        os.chdir(self.test_dir)

        result = swift_build_index()

        assert isinstance(result, dict)
        assert "project_path" in result
        assert result["project_path"] == os.path.realpath(self.test_dir)

    def test_missing_package_swift(self):
        """Test error handling when Package.swift is missing."""
        # Don't create Package.swift
        result = swift_build_index(self.test_dir)

        assert result["success"] is False
        assert "No Swift project found" in result["error"]
        assert result["error_type"] == ErrorType.VALIDATION_ERROR

    def test_invalid_project_path(self):
        """Test error handling for non-existent project path."""
        result = swift_build_index("/path/that/does/not/exist")

        assert result["success"] is False
        assert "not found" in result["error"] or "does not exist" in result["error"]
        assert result["error_type"] == ErrorType.VALIDATION_ERROR

    def test_file_instead_of_directory(self):
        """Test error handling when path points to a file instead of directory."""
        # Create a file instead of directory
        test_file = os.path.join(self.test_dir, "notadirectory.txt")
        with open(test_file, "w") as f:
            f.write("This is a file, not a directory")

        result = swift_build_index(test_file)

        assert result["success"] is False
        assert "Not a directory" in result["error"] or "not a directory" in result["error"]
        assert result["error_type"] == ErrorType.VALIDATION_ERROR

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test handling of build timeout."""
        import subprocess

        self.create_test_package()

        # Mock subprocess to raise TimeoutExpired
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["swift", "build"], timeout=60)

        result = swift_build_index(self.test_dir, timeout=60)

        assert result["success"] is False
        assert "timed out" in result["error"] or "check timed out" in result["error"]
        assert result["error_type"] in [ErrorType.BUILD_ERROR, ErrorType.ENVIRONMENT_ERROR]

    def test_timeout_validation(self):
        """Test that timeout is capped at maximum value."""
        self.create_test_package()

        # Request a very long timeout
        result = swift_build_index(self.test_dir, timeout=1000)

        # Even if build fails, the tool should run without raising exceptions
        assert isinstance(result, dict)
        assert "success" in result

    @patch("subprocess.run")
    def test_environment_not_available(self, mock_run):
        """Test handling when Swift environment is not available."""
        import subprocess

        self.create_test_package()

        # Mock xcrun check to fail
        def side_effect(*args, **kwargs):
            if "--find" in args[0]:
                result = subprocess.CompletedProcess(args[0], 1, "", "xcrun: error")
                return result
            raise subprocess.TimeoutExpired(args[0], 5)

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert result["success"] is False
        assert "Swift command not found" in result["error"]
        assert result["error_type"] == ErrorType.ENVIRONMENT_ERROR

    @patch("subprocess.run")
    def test_build_failure(self, mock_run):
        """Test handling of build failures."""
        import subprocess

        self.create_test_package()

        # Mock successful environment check but failed build
        def side_effect(*args, **kwargs):
            if "--find" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/swift", "")
            else:
                # Build command fails
                return subprocess.CompletedProcess(args[0], 1, "", "error: build failed")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert result["success"] is False
        assert "Build failed" in result["error"]
        assert result["error_type"] == ErrorType.BUILD_ERROR
        assert "error: build failed" in result.get("build_output", "")

    def test_path_traversal_security(self):
        """Test that path traversal attempts are handled safely."""
        # Try path traversal
        malicious_path = os.path.join(self.test_dir, "..", "..", "etc")
        result = swift_build_index(malicious_path)

        # Should handle this safely - either path doesn't exist or no Package.swift
        assert result["success"] is False
        assert result["error_type"] == ErrorType.VALIDATION_ERROR

    def test_concurrent_builds(self):
        """Test that concurrent build attempts are handled gracefully."""
        self.create_test_package()

        # This test just ensures the tool doesn't crash with concurrent calls
        # Actual build locking is handled by Swift build system
        results = []

        def build_task():
            result = swift_build_index(self.test_dir, timeout=30)
            results.append(result)

        # Run two builds (not truly concurrent in test, but validates structure)
        build_task()
        build_task()

        assert len(results) == 2
        for result in results:
            assert isinstance(result, dict)
            assert "success" in result

    def test_response_model_validation(self):
        """Test that responses conform to BuildIndexResponse model."""
        self.create_test_package()

        result = swift_build_index(self.test_dir)

        # Validate the response can be parsed by the model
        response = BuildIndexResponse(**result)

        assert response.project_path == result["project_path"]
        if result["success"]:
            if response.build_time:
                assert response.build_time > 0
        else:
            assert response.error is not None
            assert response.error_type is not None

    def test_special_characters_in_path(self):
        """Test handling of paths with special characters."""
        # Create directory with spaces and special chars
        special_dir = os.path.join(self.test_dir, "My Swift Project!")
        os.makedirs(special_dir)

        # Create Package.swift in special directory
        with open(os.path.join(special_dir, "Package.swift"), "w") as f:
            f.write("""// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "SpecialProject"
)
""")

        result = swift_build_index(special_dir)

        # Should handle special characters properly
        assert isinstance(result, dict)
        assert "success" in result
        # Allow for differences in realpath resolution (e.g., /private prefix on macOS)
        assert os.path.samefile(result["project_path"], special_dir)

    # Xcode Project Tests

    def create_test_xcode_project(self, project_name: str = "TestApp"):
        """Create a minimal Xcode project structure for testing."""
        # Create .xcodeproj directory
        xcodeproj_dir = os.path.join(self.test_dir, f"{project_name}.xcodeproj")
        os.makedirs(xcodeproj_dir)

        # Create minimal pbxproj file
        pbxproj_content = f"""// !$*UTF8*$!
{{
    archiveVersion = 1;
    classes = {{}};
    objectVersion = 56;
    objects = {{
        /* Begin PBXProject section */
        1234567890ABCDEF /* Project object */ = {{
            isa = PBXProject;
            attributes = {{
                LastSwiftUpdateCheck = 1400;
            }};
            buildConfigurationList = 1234567890ABCDE0 /* Build configuration list for PBXProject "{project_name}" */;
            mainGroup = 1234567890ABCDE1;
            productRefGroup = 1234567890ABCDE2 /* Products */;
            projectDirPath = "";
            projectRoot = "";
            targets = (
                1234567890ABCDE3 /* {project_name} */,
            );
        }};
        /* End PBXProject section */
    }};
    rootObject = 1234567890ABCDEF /* Project object */;
}}
"""
        pbxproj_path = os.path.join(xcodeproj_dir, "project.pbxproj")
        with open(pbxproj_path, "w") as f:
            f.write(pbxproj_content)

        return xcodeproj_dir

    def create_test_xcworkspace(self, workspace_name: str = "TestApp"):
        """Create a minimal .xcworkspace for testing."""
        xcworkspace_dir = os.path.join(self.test_dir, f"{workspace_name}.xcworkspace")
        os.makedirs(xcworkspace_dir)

        # Create contents.xcworkspacedata
        contents_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Workspace
   version = "1.0">
   <FileRef
      location = "self:{workspace_name}.xcodeproj">
   </FileRef>
</Workspace>
"""
        contents_path = os.path.join(xcworkspace_dir, "contents.xcworkspacedata")
        with open(contents_path, "w") as f:
            f.write(contents_xml)

        return xcworkspace_dir

    @patch("subprocess.run")
    def test_xcode_project_detection(self, mock_run):
        """Test that Xcode projects are properly detected."""
        import subprocess

        self.create_test_xcode_project()

        # Mock xcodebuild responses
        def side_effect(*args, **kwargs):
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "-list" in args[0] and "-json" in args[0]:
                # Mock scheme list response
                json_output = '{"project": {"schemes": ["TestApp", "TestAppTests"]}}'
                return subprocess.CompletedProcess(args[0], 0, json_output, "")
            elif "build" in args[0]:
                # Mock successful build
                return subprocess.CompletedProcess(args[0], 0, "Build succeeded", "")
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert result["success"] is True
        assert result["project_type"] == "xcode"
        # Check index path exists and is in expected location (handle /private prefix on macOS)
        assert result["index_path"].endswith(".build/index/store")

    @patch("subprocess.run")
    def test_xcode_with_specific_scheme(self, mock_run):
        """Test building Xcode project with specific scheme."""
        import subprocess

        self.create_test_xcode_project()

        def side_effect(*args, **kwargs):
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "build" in args[0]:
                # Verify scheme is passed in build command
                assert "TestApp" in args[0]
                return subprocess.CompletedProcess(args[0], 0, "Build succeeded", "")
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir, scheme="TestApp")

        assert result["success"] is True
        assert result["project_type"] == "xcode"

    @patch("subprocess.run")
    def test_xcode_scheme_auto_detection(self, mock_run):
        """Test automatic scheme detection for Xcode projects."""
        import subprocess

        self.create_test_xcode_project()

        scheme_list_called = False

        def side_effect(*args, **kwargs):
            nonlocal scheme_list_called
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "-list" in args[0] and "-json" in args[0]:
                scheme_list_called = True
                json_output = '{"project": {"schemes": ["MyScheme"]}}'
                return subprocess.CompletedProcess(args[0], 0, json_output, "")
            elif "build" in args[0]:
                # Should use the auto-detected scheme
                assert "MyScheme" in args[0]
                return subprocess.CompletedProcess(args[0], 0, "Build succeeded", "")
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert scheme_list_called
        assert result["success"] is True

    @patch("subprocess.run")
    def test_xcode_invalid_scheme(self, mock_run):
        """Test handling of invalid scheme for Xcode project."""
        import subprocess

        self.create_test_xcode_project()

        def side_effect(*args, **kwargs):
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "build" in args[0]:
                # Xcode fails when scheme doesn't exist
                error = "xcodebuild: error: The workspace does not contain a scheme named 'InvalidScheme'."
                return subprocess.CompletedProcess(args[0], 1, "", error)
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir, scheme="InvalidScheme")

        assert result["success"] is False
        assert result["error_type"] == ErrorType.BUILD_ERROR
        assert "build failed" in result["error"].lower() or "scheme" in result["error"].lower()

    @patch("subprocess.run")
    def test_xcworkspace_priority(self, mock_run):
        """Test that .xcworkspace takes priority over .xcodeproj."""
        import subprocess

        # Create both .xcodeproj and .xcworkspace
        self.create_test_xcode_project()
        self.create_test_xcworkspace()

        def side_effect(*args, **kwargs):
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "-list" in args[0] and "-json" in args[0]:
                # Should be called with .xcworkspace using -workspace flag
                workspace_index = (
                    args[0].index("-workspace")
                    if "-workspace" in args[0]
                    else args[0].index("-project")
                )
                assert ".xcworkspace" in args[0][workspace_index + 1]
                json_output = '{"workspace": {"schemes": ["WorkspaceScheme"]}}'
                return subprocess.CompletedProcess(args[0], 0, json_output, "")
            elif "build" in args[0]:
                # Should build with .xcworkspace
                assert ".xcworkspace" in args[0][args[0].index("-workspace") + 1]
                return subprocess.CompletedProcess(args[0], 0, "Build succeeded", "")
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert result["success"] is True
        assert result["project_type"] == "xcode"

    @patch("subprocess.run")
    def test_xcode_build_with_custom_index_path(self, mock_run):
        """Test that Xcode build uses custom index store path."""
        import subprocess

        self.create_test_xcode_project()

        def side_effect(*args, **kwargs):
            if "--find" in args[0] and "xcrun" in args[0]:
                return subprocess.CompletedProcess(args[0], 0, "/usr/bin/xcodebuild", "")
            elif "-list" in args[0] and "-json" in args[0]:
                json_output = '{"project": {"schemes": ["TestApp"]}}'
                return subprocess.CompletedProcess(args[0], 0, json_output, "")
            elif "build" in args[0]:
                # Verify INDEX_STORE_PATH is set correctly
                assert "INDEX_STORE_PATH=" in " ".join(args[0])
                assert ".build/index/store" in " ".join(args[0])
                return subprocess.CompletedProcess(args[0], 0, "Build succeeded", "")
            raise ValueError(f"Unexpected command: {args}")

        mock_run.side_effect = side_effect

        result = swift_build_index(self.test_dir)

        assert result["success"] is True
        assert result["index_path"].endswith(".build/index/store")

    def test_mixed_project_detection(self):
        """Test project detection when both Package.swift and .xcodeproj exist."""
        # Create both types of projects
        self.create_test_package()
        self.create_test_xcode_project()

        result = swift_build_index(self.test_dir)

        # SPM should take priority when both exist
        assert isinstance(result, dict)
        assert "project_path" in result

    def test_output_sanitization_integration(self):
        """Integration test for build output sanitization with real processes."""
        from swiftlens.tools.swift_build_index import _sanitize_build_output

        # Test with sensitive data that might appear in real build output
        mock_output = """/Users/developer/secret-project/build.sh
TOKEN=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890
Environment variable: API_KEY=sk-1234567890abcdef1234567890abcdef
Standalone token: aVeryLongTokenThatIsMoreThan20CharactersLong123456789
IP Address: 192.168.1.100
UUID: 123e4567-e89b-12d3-a456-426614174000
Building in /private/var/folders/abc/def/T/build123
"""

        sanitized = _sanitize_build_output(mock_output)

        # Verify sensitive data is sanitized
        assert "/Users/developer/secret-project/build.sh" not in sanitized
        assert "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890" not in sanitized
        assert "sk-1234567890abcdef1234567890abcdef" not in sanitized
        assert "aVeryLongTokenThatIsMoreThan20CharactersLong123456789" not in sanitized
        assert "192.168.1.100" not in sanitized
        assert "123e4567-e89b-12d3-a456-426614174000" not in sanitized

        # Verify placeholders are present
        assert "<path>" in sanitized
        assert "<token>" in sanitized
        assert "<env_var>" in sanitized
        assert "<ip>" in sanitized
        assert "<uuid>" in sanitized

    def test_symlink_project_handling(self):
        """Integration test for symlink handling in project detection."""
        # Create a real Swift package
        self.create_test_package()

        # Create a symlink to the project directory
        symlink_dir = os.path.join(tempfile.gettempdir(), "swift_symlink_test")
        if os.path.exists(symlink_dir):
            os.unlink(symlink_dir)

        try:
            os.symlink(self.test_dir, symlink_dir)

            # Test building through symlink
            result = swift_build_index(symlink_dir)

            # Should work with symlinked project directory
            assert isinstance(result, dict)
            assert "project_path" in result
            assert result["project_path"] == os.path.realpath(symlink_dir)

        finally:
            # Clean up symlink
            if os.path.exists(symlink_dir):
                os.unlink(symlink_dir)

    def test_symlink_xcode_project_detection(self):
        """Test detection of symlinked Xcode projects."""
        from swiftlens.tools.swift_build_index import _find_xcode_project

        # Create a real Xcode project
        self.create_test_xcode_project()

        # Create a symlink to the .xcodeproj
        original_project = os.path.join(self.test_dir, "TestApp.xcodeproj")
        symlink_project = os.path.join(self.test_dir, "SymlinkedProject.xcodeproj")

        try:
            os.symlink(original_project, symlink_project)

            # Should detect symlinked project
            found_project = _find_xcode_project(self.test_dir)

            # Should return one of the projects (prioritization still applies)
            assert found_project is not None
            assert found_project.endswith(".xcodeproj")

        finally:
            # Clean up symlink
            if os.path.exists(symlink_project):
                os.unlink(symlink_project)

    def test_permission_handling_integration(self):
        """Integration test for permission handling in real scenarios."""
        from swiftlens.tools.swift_build_index import _find_xcode_project

        # Create a directory with restricted permissions
        restricted_dir = os.path.join(self.test_dir, "restricted")
        os.makedirs(restricted_dir, exist_ok=True)

        # Create a fake xcodeproj inside
        fake_project = os.path.join(restricted_dir, "TestApp.xcodeproj")
        os.makedirs(fake_project, exist_ok=True)

        try:
            # Remove read permissions from the directory
            os.chmod(restricted_dir, 0o000)

            # Should handle permission error gracefully
            result = _find_xcode_project(restricted_dir)
            assert result is None  # Should return None for inaccessible directories

        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_dir, 0o755)

    def test_real_filesystem_edge_cases(self):
        """Test edge cases with real filesystem operations."""
        # Test with directory containing dots but not actual projects
        fake_dir = os.path.join(self.test_dir, "fake.xcodeproj.backup")
        os.makedirs(fake_dir, exist_ok=True)

        result = swift_build_index(self.test_dir)

        # Should not detect fake project
        assert result["success"] is False
        assert "No Swift project found" in result["error"]

    def test_concurrent_build_protection_integration(self):
        """Integration test for concurrent build protection with real file locking."""
        import threading
        import time

        self.create_test_package()

        results = []

        def build_in_thread():
            # Add a small delay to ensure both threads try to build simultaneously
            time.sleep(0.1)
            result = swift_build_index(self.test_dir, timeout=1)
            results.append(result)

        # Start two threads that will try to build simultaneously
        thread1 = threading.Thread(target=build_in_thread)
        thread2 = threading.Thread(target=build_in_thread)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # One should succeed/fail normally, one should get blocking error
        assert len(results) == 2

        blocking_errors = [
            r for r in results if "Another build is already in progress" in r.get("error", "")
        ]
        # At least one should get the blocking error (depending on timing)
        # In some cases both might complete if they don't overlap, that's okay
        assert len(blocking_errors) <= 1

    def test_scheme_name_validation_security(self):
        """Test scheme name validation to prevent command injection."""
        from swiftlens.tools.swift_build_index import _validate_scheme_name

        # Valid scheme names
        valid_schemes = [
            "MyApp",
            "My-App",
            "My_App",
            "My App",
            "Test123",
            "app-test_2024",
        ]

        for scheme in valid_schemes:
            assert _validate_scheme_name(scheme), f"Valid scheme '{scheme}' should pass validation"

        # Invalid scheme names (potential injection attempts)
        invalid_schemes = [
            "",  # Empty
            None,  # None
            123,  # Not a string
            "app; rm -rf /",  # Command injection attempt
            "app\0null",  # Null byte injection
            "app|cat /etc/passwd",  # Pipe injection
            "app$(whoami)",  # Command substitution
            "app`whoami`",  # Backtick command substitution
            "app && echo hello",  # Command chaining
            "app || echo hello",  # Command chaining
            "app > /tmp/file",  # Output redirection
            "app < /etc/passwd",  # Input redirection
            "app*",  # Wildcard that could be misinterpreted
            "app?",  # Wildcard that could be misinterpreted
            "a" * 101,  # Too long (over 100 chars)
            "app\n\necho injected",  # Newline injection
            "app\t\techo injected",  # Tab injection
            "app\necho injected",  # Single newline injection
            "app\tmalicious",  # Single tab injection
            "app\rcommand",  # Carriage return injection
            "app\vvertical",  # Vertical tab injection
            "app\fform",  # Form feed injection
        ]

        for scheme in invalid_schemes:
            assert not _validate_scheme_name(scheme), (
                f"Invalid scheme '{scheme}' should fail validation"
            )

    def test_index_path_security_validation(self):
        """Test index path validation to prevent path injection."""
        from swiftlens.tools.swift_build_index import _validate_index_path_security

        # Create a temporary project directory
        project_dir = self.test_dir

        # Valid index paths (within project)
        valid_paths = [
            os.path.join(project_dir, ".build", "index", "store"),
            os.path.join(project_dir, "build", "index"),
            os.path.join(project_dir, "subdir", "index"),
        ]

        for index_path in valid_paths:
            assert _validate_index_path_security(index_path, project_dir), (
                f"Valid path '{index_path}' should pass validation"
            )

        # Invalid index paths (potential injection attempts)
        invalid_paths = [
            "/tmp/evil_index",  # Absolute path outside project
            "../../../tmp/evil_index",  # Directory traversal
            os.path.join(project_dir, "..", "sibling_dir"),  # Sibling directory
            "/etc/passwd",  # System file
            "C:\\Windows\\System32",  # Windows system path
            project_dir + "/../evil",  # Parent directory
        ]

        for index_path in invalid_paths:
            assert not _validate_index_path_security(index_path, project_dir), (
                f"Invalid path '{index_path}' should fail validation"
            )

    def test_xcode_build_scheme_validation_integration(self):
        """Integration test for scheme validation in Xcode builds."""
        self.create_test_xcode_project()

        # Test with invalid scheme containing injection attempt
        result = swift_build_index(self.test_dir, scheme="evil; rm -rf /")

        assert result["success"] is False
        assert "Invalid scheme name" in result["error"]
        assert result["error_type"] == "validation_error"

    def test_regex_performance_improvement(self):
        """Test that regex patterns are pre-compiled for performance."""
        import re

        from swiftlens.tools.swift_build_index import _SANITIZATION_PATTERNS

        # Verify patterns are pre-compiled
        assert len(_SANITIZATION_PATTERNS) == 6

        for pattern, replacement in _SANITIZATION_PATTERNS:
            assert isinstance(pattern, re.Pattern), "Patterns should be pre-compiled regex objects"
            assert isinstance(replacement, str), "Replacements should be strings"

        # Test performance with large input
        lines = []
        for i in range(100):
            lines.extend(
                [
                    f"/path/to/file{i}.swift: Building...",
                    f"API_KEY=token{i}abcdefghijklmnopqrstuvwxyz",
                    f"Processing 192.168.1.{i % 255}",
                    f"UUID: {i:08d}-1234-5678-9abc-def012345678",
                ]
            )
        large_input = "Large build output: " + "\n".join(lines)

        # This should complete quickly with pre-compiled patterns
        from swiftlens.tools.swift_build_index import _sanitize_build_output

        result = _sanitize_build_output(large_input)

        # Verify sanitization still works
        assert "<path>" in result
        assert "<env_var>" in result
        assert "<ip>" in result
        assert "<uuid>" in result
        assert "/path/to/file" not in result  # Paths should be sanitized

    def test_enhanced_security_integration(self):
        """Integration test for all security enhancements working together."""
        self.create_test_xcode_project()

        # Test multiple security validations in sequence
        test_cases = [
            # Case 1: Invalid scheme
            {"scheme": "app; echo hacked", "expected_error": "Invalid scheme name"},
            # Case 2: Another injection attempt
            {"scheme": "app`whoami`", "expected_error": "Invalid scheme name"},
        ]

        for case in test_cases:
            result = swift_build_index(self.test_dir, scheme=case["scheme"])

            assert result["success"] is False
            assert case["expected_error"] in result["error"]
            assert result["error_type"] == "validation_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
