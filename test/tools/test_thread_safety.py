"""Test thread safety and concurrent processing behavior."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from lsp.client import SwiftLSPClient

from swiftlens.model.models import ErrorType, MultiFileSymbolReferenceResponse
from swiftlens.tools.swift_find_symbol_references_files import (
    swift_find_symbol_references_files,
)


class TestThreadSafety:
    """Test suite for thread safety and concurrent processing."""

    def test_sequential_processing_with_client(self):
        """Test that files are processed sequentially when client is provided."""
        # Create test files
        with tempfile.TemporaryDirectory() as temp_dir:
            test_files = []
            for i in range(5):
                file_path = os.path.join(temp_dir, f"Test{i}.swift")
                with open(file_path, "w") as f:
                    f.write(f"""
                    class Test{i} {{
                        func doSomething() {{
                            print("Test{i}")
                        }}
                    }}
                    """)
                test_files.append(file_path)

            # Mock client to track call order
            mock_client = MagicMock(spec=SwiftLSPClient)
            call_order = []

            def track_open_document(file_uri, content):
                call_order.append(("open", file_uri))

            mock_client.open_document.side_effect = track_open_document

            # Mock _process_single_file to return valid results
            with patch(
                "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
            ) as mock_process:
                # Create proper return values
                def create_response(file_path):
                    from swiftlens.model.models import SymbolReferenceResponse

                    # Track the open document call
                    track_open_document(f"file://{file_path}", "")
                    return SymbolReferenceResponse(
                        success=True,
                        file_path=file_path,
                        symbol_name="doSomething",
                        references=[],
                        reference_count=0,
                    )

                mock_process.side_effect = lambda analyzer, fp, sym: create_response(fp)

                # Process files
                swift_find_symbol_references_files(test_files, "doSomething", client=mock_client)

                # Verify sequential processing
                assert len(call_order) == 5, "Should have processed all 5 files"
                # Verify files were processed in order (sequential, not parallel)
                for i, (op, uri) in enumerate(call_order):
                    assert op == "open"
                    assert f"Test{i}.swift" in uri

    def test_max_files_limit(self):
        """Test that max files limit is enforced."""
        # Create more files than the limit
        file_paths = [f"/tmp/file{i}.swift" for i in range(600)]

        result = swift_find_symbol_references_files(file_paths, "testSymbol")

        # Convert to model to verify
        response = MultiFileSymbolReferenceResponse.model_validate(result)
        assert not response.success
        assert response.error_type == ErrorType.VALIDATION_ERROR
        assert "Too many files: 600" in response.error
        assert "Maximum allowed is 500" in response.error

    def test_path_normalization_with_symlinks(self):
        """Test that Path.resolve() properly handles symlinks and normalization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a real file
            real_file = os.path.join(temp_dir, "real.swift")
            with open(real_file, "w") as f:
                f.write("class Test {}")

            # Create a symlink
            symlink = os.path.join(temp_dir, "link.swift")
            os.symlink(real_file, symlink)

            # Create paths with different representations
            paths = [
                real_file,
                symlink,
                os.path.join(temp_dir, ".", "real.swift"),  # With dot
                os.path.join(temp_dir, "subdir", "..", "real.swift"),  # With ..
            ]

            with patch("swiftlens.tools.swift_find_symbol_references_files.FileAnalyzer"):
                with patch("swiftlens.tools.swift_find_symbol_references_files.managed_lsp_client"):
                    # Mock to avoid actual LSP calls
                    with patch(
                        "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
                    ) as mock_process:
                        from swiftlens.model.models import SymbolReferenceResponse

                        mock_process.return_value = SymbolReferenceResponse(
                            success=True,
                            file_path=real_file,  # Use real_file instead of test_file
                            symbol_name="Test",
                            references=[],
                            reference_count=0,
                        )

                        swift_find_symbol_references_files(paths, "Test")

                        # Should only process the file once due to deduplication
                        assert mock_process.call_count == 1

    def test_concurrent_requests_should_not_use_threadpool(self):
        """Verify that even if called from multiple threads, no ThreadPoolExecutor is used internally."""
        import threading

        # Track if ThreadPoolExecutor is imported or used
        threadpool_used = threading.Event()

        import builtins

        original_import = builtins.__import__

        def track_imports(name, *args, **kwargs):
            if "concurrent.futures" in name and "ThreadPoolExecutor" in str(args):
                threadpool_used.set()
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=track_imports):
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create test file
                test_file = os.path.join(temp_dir, "Test.swift")
                with open(test_file, "w") as f:
                    f.write("class Test { func foo() {} }")

                # Create Package.swift to make it a valid Swift project
                package_file = os.path.join(temp_dir, "Package.swift")
                with open(package_file, "w") as f:
                    f.write("""// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "TestProject",
    targets: [
        .target(name: "TestProject", path: ".")
    ]
)
""")

                # Mock the processing to be fast
                with patch(
                    "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
                ) as mock_process:
                    from swiftlens.model.models import SymbolReferenceResponse

                    mock_process.return_value = SymbolReferenceResponse(
                        success=True,
                        file_path=test_file,
                        symbol_name="foo",
                        references=[],
                        reference_count=1,
                    )

                    # Call from multiple threads
                    results = []

                    def call_find_references():
                        result = swift_find_symbol_references_files([test_file], "foo")
                        results.append(result)

                    threads = []
                    for _ in range(3):
                        t = threading.Thread(target=call_find_references)
                        threads.append(t)
                        t.start()

                    for t in threads:
                        t.join()

                    # Verify all calls completed
                    assert len(results) == 3

                    # Verify ThreadPoolExecutor was not used
                    assert not threadpool_used.is_set(), "ThreadPoolExecutor should not be used"

    def test_error_handling_specificity(self):
        """Test that specific error types are properly handled with mocked client."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "Test.swift")
            with open(test_file, "w") as f:
                f.write("class Test {}")

            # Test different error types
            error_scenarios = [
                (TimeoutError("LSP timeout"), "LSP communication error: LSP timeout"),
                (
                    ConnectionError("Connection refused"),
                    "LSP communication error: Connection refused",
                ),
                (OSError("File system error"), "File system error"),
                (RuntimeError("Runtime issue"), "Runtime issue"),
                (ValueError("Invalid value"), "Invalid value"),
            ]

            # Create a mock client to bypass LSP initialization
            mock_client = MagicMock(spec=SwiftLSPClient)

            for error, expected_msg in error_scenarios:
                with patch(
                    "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
                ) as mock_process:
                    mock_process.side_effect = error

                    # Use the mocked client to bypass LSP initialization
                    result = swift_find_symbol_references_files(
                        [test_file], "Test", client=mock_client
                    )
                    response = MultiFileSymbolReferenceResponse.model_validate(result)

                    # Should still return success=True for the overall operation
                    assert response.success
                    # But the individual file should have failed
                    file_result = response.files[test_file]
                    assert not file_result.success
                    assert expected_msg in file_result.error
                    assert file_result.error_type == ErrorType.LSP_ERROR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
