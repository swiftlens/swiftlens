#!/usr/bin/env python3
"""
Test file for find_symbol_references_files tool using pytest.

This test validates the swift_find_symbol_references_files tool functionality with LSP.

IMPORTANT: References Now Work in Test Environments
==================================================

Previously, the textDocument/references operation had limitations in test environments
due to missing -index-db-path argument. This has been FIXED by providing both:
- -index-store-path: Points to the compiled index data
- -index-db-path: Points to LSP's own database for quick lookups

With both arguments, SourceKit-LSP can properly track references across files
even in test environments.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from swiftlens.tools.swift_find_symbol_references_files import swift_find_symbol_references_files


@pytest.fixture(scope="session")
def multi_file_swift_project(built_swift_environment):
    """Creates multiple Swift files for multi-file testing."""
    _, _, create_swift_file = built_swift_environment

    # Create first file with User struct and references
    user_content = """import Foundation

struct User {
    let id: String
    var name: String
    var email: String

    func validateEmail() -> Bool {
        return email.contains("@")
    }
}

class UserManager {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
    }

    func findUser(by id: String) -> User? {
        return users.first { $0.id == id }
    }
}"""

    # Create second file with more User references
    service_content = """import Foundation

class UserService {
    private let userManager = UserManager()

    func processUser(_ user: User) {
        if user.validateEmail() {
            userManager.addUser(user)
        }
    }

    func createTestUser() -> User {
        return User(id: "test", name: "Test", email: "test@example.com")
    }
}"""

    user_file = create_swift_file(user_content, "User.swift")
    service_file = create_swift_file(service_content, "UserService.swift")

    return [user_file, service_file]


class TestSwiftFindSymbolReferencesFiles:
    """Test swift_find_symbol_references_files tool with multi-file functionality."""

    def test_basic_multi_file_functionality(self, multi_file_swift_project):
        """Test basic multi-file symbol reference search functionality."""
        file_paths = multi_file_swift_project
        symbol = "User"

        result = swift_find_symbol_references_files(file_paths, symbol)

        # Should succeed overall
        assert result["success"] is True
        assert result["total_files"] == 2
        assert len(result["files"]) == 2

        # All files should be in results
        for file_path in file_paths:
            assert file_path in result["files"]

        # Each file should have a result structure
        for file_path in file_paths:
            file_result = result["files"][file_path]
            assert "success" in file_result
            assert "file_path" in file_result
            assert "symbol_name" in file_result
            assert "references" in file_result
            assert "reference_count" in file_result
            assert file_result["file_path"] == file_path
            assert file_result["symbol_name"] == symbol

    def test_empty_file_list_error(self):
        """Test error handling for empty file list."""
        result = swift_find_symbol_references_files([], "User")

        assert result["success"] is False
        assert result["total_files"] == 0
        assert len(result["files"]) == 0
        assert "No files provided" in result["error"]

    def test_empty_symbol_name_error(self, multi_file_swift_project):
        """Test error handling for empty symbol name."""
        file_paths = multi_file_swift_project[:1]  # Use just one file

        # Test with None
        result = swift_find_symbol_references_files(file_paths, None)
        assert result["success"] is False
        assert "Symbol name cannot be empty" in result["error"]

        # Test with empty string
        result = swift_find_symbol_references_files(file_paths, "")
        assert result["success"] is False
        assert "Symbol name cannot be empty" in result["error"]

        # Test with whitespace only
        result = swift_find_symbol_references_files(file_paths, "   ")
        assert result["success"] is False
        assert "Symbol name cannot be empty" in result["error"]

    def test_non_existent_file_handling(self, multi_file_swift_project):
        """Test handling of non-existent files."""
        valid_file = multi_file_swift_project[0]
        non_existent = "/non/existent/file.swift"
        file_paths = [valid_file, non_existent]
        symbol = "User"

        result = swift_find_symbol_references_files(file_paths, symbol)

        # Should succeed overall
        assert result["success"] is True
        assert result["total_files"] == 2
        assert len(result["files"]) == 2

        # Valid file should have normal result
        assert valid_file in result["files"]
        valid_result = result["files"][valid_file]
        assert "success" in valid_result

        # Non-existent file should have error
        assert non_existent in result["files"]
        invalid_result = result["files"][non_existent]
        assert invalid_result["success"] is False
        assert "File not found" in invalid_result["error"]

    def test_non_swift_file_handling(self, multi_file_swift_project):
        """Test handling of non-Swift files."""
        valid_file = multi_file_swift_project[0]

        # Create a non-Swift file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Not Swift")
            non_swift = f.name

        try:
            file_paths = [valid_file, non_swift]
            symbol = "User"

            result = swift_find_symbol_references_files(file_paths, symbol)

            # Should succeed overall
            assert result["success"] is True
            assert result["total_files"] == 2
            assert len(result["files"]) == 2

            # Valid file should have normal result
            assert valid_file in result["files"]
            valid_result = result["files"][valid_file]
            assert "success" in valid_result

            # Non-Swift file should have error
            assert non_swift in result["files"]
            invalid_result = result["files"][non_swift]
            assert invalid_result["success"] is False
            assert "must be a Swift file" in invalid_result["error"]

        finally:
            os.unlink(non_swift)

    def test_relative_path_handling(self, built_swift_environment, monkeypatch):
        """Test relative path handling."""
        project_root, _, create_swift_file = built_swift_environment

        # Create test file
        test_file = create_swift_file("struct TestStruct { var name: String }", "TestFile.swift")

        # Change to project directory for relative path testing
        monkeypatch.chdir(project_root)

        # Get relative path
        relative_path = os.path.relpath(test_file, project_root)

        result = swift_find_symbol_references_files([relative_path], "TestStruct")

        # Should succeed
        assert result["success"] is True
        assert result["total_files"] == 1
        assert len(result["files"]) == 1

        # File should be found in results (key might be normalized)
        file_found = False
        for file_path in result["files"].keys():
            if "TestFile.swift" in file_path:
                file_found = True
                break
        assert file_found, f"Expected file result not found in {list(result['files'].keys())}"

    def test_mixed_valid_invalid_files(self, multi_file_swift_project):
        """Test handling of mixed valid and invalid files."""
        valid_file = multi_file_swift_project[0]
        non_existent = "/non/existent/file.swift"

        # Create non-Swift file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Not Swift")
            non_swift = f.name

        try:
            # Create a temporary second Swift file for testing
            with tempfile.NamedTemporaryFile(mode="w", suffix=".swift", delete=False) as f2:
                f2.write("struct TestStruct { var id: Int }")
                second_swift_file = f2.name

            file_paths = [valid_file, non_existent, second_swift_file, non_swift]
            symbol = "TestSymbol"

            result = swift_find_symbol_references_files(file_paths, symbol)

            # Should succeed overall
            assert result["success"] is True
            assert result["total_files"] == 4
            assert len(result["files"]) == 4

            # Check that we have results for all files
            assert valid_file in result["files"]
            assert second_swift_file in result["files"]
            assert non_existent in result["files"]
            assert non_swift in result["files"]

            # Valid Swift files should have normal results
            valid_files = [valid_file, second_swift_file]
            for file_path in valid_files:
                file_result = result["files"][file_path]
                assert "success" in file_result
                # May be True or False depending on LSP capabilities in test env

            # Invalid files should have errors
            assert result["files"][non_existent]["success"] is False
            assert result["files"][non_swift]["success"] is False

        finally:
            os.unlink(non_swift)
            os.unlink(second_swift_file)

    def test_single_file_compatibility(self, multi_file_swift_project):
        """Test that the tool works with a single file (backward compatibility)."""
        file_paths = [multi_file_swift_project[0]]
        symbol = "User"

        result = swift_find_symbol_references_files(file_paths, symbol)

        assert result["success"] is True
        assert result["total_files"] == 1
        assert len(result["files"]) == 1
        assert multi_file_swift_project[0] in result["files"]

        file_result = result["files"][multi_file_swift_project[0]]
        assert file_result["file_path"] == multi_file_swift_project[0]
        assert file_result["symbol_name"] == symbol

    @pytest.mark.lsp
    def test_lsp_integration_empty_results_normal(self, multi_file_swift_project):
        """Test that empty reference results are handled gracefully (normal in test env)."""
        file_paths = multi_file_swift_project
        symbol = "nonExistentSymbol"

        result = swift_find_symbol_references_files(file_paths, symbol)

        # Should succeed even with no references (normal in test environment)
        assert result["success"] is True
        assert result["total_files"] == len(file_paths)
        assert len(result["files"]) == len(file_paths)

        # All files should have results (even if empty references)
        for file_path in file_paths:
            assert file_path in result["files"]
            file_result = result["files"][file_path]
            assert file_result["symbol_name"] == symbol
            # References list may be empty due to test environment limitations
            assert isinstance(file_result["references"], list)

    def test_client_parameter_handling(self, multi_file_swift_project):
        """Test the client parameter for test performance optimization."""
        file_paths = [multi_file_swift_project[0]]
        symbol = "User"

        # Create mock client and analyzer
        mock_client = MagicMock()
        mock_analyzer = MagicMock()

        # Mock FileAnalyzer constructor to return our mock
        import swiftlens.tools.swift_find_symbol_references_files as module

        original_file_analyzer = module.FileAnalyzer

        def mock_file_analyzer_constructor(client):
            # Verify the analyzer method was called for our file
            mock_analyzer.find_symbol_references.return_value = {
                "success": True,
                "references": [],
                "reference_count": 0,
            }
            return mock_analyzer

        try:
            module.FileAnalyzer = mock_file_analyzer_constructor

            # Also mock validation to pass
            with patch(
                "swiftlens.tools.swift_find_symbol_references_files._validate_file_path"
            ) as mock_validate:
                mock_validate.return_value = (True, file_paths[0], None)

                # Call with mock client
                result = swift_find_symbol_references_files(file_paths, symbol, client=mock_client)

                # Should use the provided client path
                assert result["success"] is True

                # Verify the analyzer method was called for our file
                mock_analyzer.find_symbol_references.assert_called_once_with(file_paths[0], symbol)

        finally:
            # Restore original
            module.FileAnalyzer = original_file_analyzer

    def test_reference_aggregation(self, multi_file_swift_project):
        """Test that references are properly aggregated across files."""
        file_paths = multi_file_swift_project
        symbol = "User"

        result = swift_find_symbol_references_files(file_paths, symbol)

        assert result["success"] is True
        assert result["total_files"] == len(file_paths)
        assert len(result["files"]) == len(file_paths)

        # Check aggregation fields
        assert "total_references" in result
        assert isinstance(result["total_references"], int)
        assert result["total_references"] >= 0

        # Each file should contribute to total (even if 0 in test env)
        file_reference_sum = sum(result["files"][fp]["reference_count"] for fp in file_paths)
        assert result["total_references"] == file_reference_sum

    def test_error_isolation(self, multi_file_swift_project):
        """Test that errors in one file don't affect others."""
        valid_file = multi_file_swift_project[0]
        non_existent = "/non/existent/file.swift"
        file_paths = [valid_file, non_existent]
        symbol = "User"

        result = swift_find_symbol_references_files(file_paths, symbol)

        # Should succeed overall despite one file error
        assert result["success"] is True
        assert result["total_files"] == 2
        assert len(result["files"]) == 2

        # Valid file should succeed
        valid_result = result["files"][valid_file]
        assert "success" in valid_result

        # Invalid file should fail but be isolated
        invalid_result = result["files"][non_existent]
        assert invalid_result["success"] is False
        assert "File not found" in invalid_result["error"]

        # Total references should only count successful files
        assert result["total_references"] == valid_result["reference_count"]
