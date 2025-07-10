"""
Tests for swift_lsp_diagnostics tool
"""

from swiftlens.tools.swift_lsp_diagnostics import swift_lsp_diagnostics


class TestSwiftLSPDiagnostics:
    """Test suite for unified LSP diagnostics tool."""

    def test_basic_diagnostics(self):
        """Test basic diagnostics without project path."""
        result = swift_lsp_diagnostics()

        assert isinstance(result, dict)
        assert "success" in result
        assert "environment" in result
        assert "lsp_server" in result
        assert "health" in result
        assert "stats" in result
        assert "recommendations" in result

        # Check environment structure
        env = result["environment"]
        assert "has_swift" in env
        assert "swift_version" in env
        assert "has_xcode" in env
        assert "sourcekit_lsp_path" in env

        # Check LSP server structure
        lsp = result["lsp_server"]
        assert "exists" in lsp
        assert "path" in lsp
        assert "version" in lsp

    def test_with_project_path(self, swift_project):
        """Test diagnostics with a project path."""
        project_dir, _, _ = swift_project  # Unpack tuple (root, sources, helper)
        result = swift_lsp_diagnostics(project_path=project_dir)

        assert result["success"] is True
        assert result["project_setup"] is not None

        setup = result["project_setup"]
        assert setup["exists"] is True
        assert setup["has_swift_files"] is True
        assert "swift_file_count" in setup
        assert setup["swift_file_count"] > 0

    def test_with_nonexistent_project(self):
        """Test diagnostics with nonexistent project path."""
        result = swift_lsp_diagnostics(project_path="/nonexistent/path")

        # Tool should fail with validation error for nonexistent path
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"
        assert "not found" in result["error"]

    def test_without_recommendations(self):
        """Test diagnostics without recommendations."""
        result = swift_lsp_diagnostics(include_recommendations=False)

        assert result["success"] is True
        assert result["recommendations"] == []

    def test_recommendations_generated(self):
        """Test that recommendations are generated based on issues."""
        result = swift_lsp_diagnostics(include_recommendations=True)

        # If environment is missing components, we should get recommendations
        if not result["environment"]["has_swift"]:
            assert any("Install Swift" in rec for rec in result["recommendations"])

        if not result["lsp_server"]["exists"]:
            assert any("sourcekit-lsp" in rec for rec in result["recommendations"])

    def test_project_type_detection(self, swift_project):
        """Test diagnostics detects project type correctly."""
        project_dir, _, _ = swift_project  # Unpack tuple (root, sources, helper)
        result = swift_lsp_diagnostics(project_path=project_dir)

        assert result["success"] is True
        setup = result["project_setup"]

        # Check that project type detection fields exist
        assert "has_package_swift" in setup
        assert "has_xcodeproj" in setup

        # At least one project type should be detected
        assert setup["has_package_swift"] or setup["has_xcodeproj"]

    def test_path_traversal_attack(self):
        """Test that path traversal attacks are blocked."""
        # Test relative path traversal
        result = swift_lsp_diagnostics(project_path="../../../etc/passwd")
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"

        # Test absolute path traversal
        result = swift_lsp_diagnostics(project_path="/../../../etc/passwd")
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"

    def test_null_byte_injection(self):
        """Test that null byte injection is blocked."""
        result = swift_lsp_diagnostics(project_path="test\0.swift")
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"
        assert "Invalid" in result["error"]

    def test_empty_and_invalid_paths(self):
        """Test handling of empty and invalid project paths."""
        # Test empty string
        result = swift_lsp_diagnostics(project_path="")
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"

        # Test None (should work - it's optional)
        result = swift_lsp_diagnostics(project_path=None)
        assert result["success"] is True
        assert result["project_setup"] is None

    def test_path_validation_uses_existing_helpers(self):
        """Test that path validation uses the centralized validation helpers."""
        # Test with a very long path (should be rejected by validation)
        long_path = "a" * 5000
        result = swift_lsp_diagnostics(project_path=long_path)
        assert result["success"] is False
        assert "error" in result
        assert result["error_type"] == "VALIDATION_ERROR"
