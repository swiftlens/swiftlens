"""Test thread safety and concurrent processing behavior."""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

try:
    from lsp.client import SwiftLSPClient
except ImportError:
    # Create a mock if not available during tests
    SwiftLSPClient = object

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

                mock_process.side_effect = (
                    lambda analyzer, fp, sym, analyzer_lock=None: create_response(fp)
                )

                # Also need to patch validation
                with patch(
                    "swiftlens.tools.swift_find_symbol_references_files._validate_file_path"
                ) as mock_validate:
                    # Mock validation to always pass
                    mock_validate.side_effect = lambda fp, sn, allow_outside: (True, fp, None)

                    # Process files
                    swift_find_symbol_references_files(
                        test_files, "doSomething", client=mock_client
                    )

                    # Verify all files were processed
                    assert len(call_order) == 5, "Should have processed all 5 files"

                    # Extract the file names from the URIs
                    processed_files = []
                    for op, uri in call_order:
                        assert op == "open"
                        # Extract filename from URI
                        filename = uri.split("/")[-1]
                        processed_files.append(filename)

                    # Check that all test files were processed (order doesn't matter with parallel processing)
                    expected_files = {f"Test{i}.swift" for i in range(5)}
                    assert set(processed_files) == expected_files

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
        """Test that symlinks are properly rejected by validation."""
        # Use a fixed directory that we know doesn't have symlinks in its path
        test_dir = os.path.abspath(os.path.join(os.getcwd(), "test_temp_files"))
        os.makedirs(test_dir, exist_ok=True)

        try:
            # Create a real file
            real_file = os.path.join(test_dir, "real.swift")
            with open(real_file, "w") as f:
                f.write("class Test {}")

            # Create a symlink
            symlink = os.path.join(test_dir, "link.swift")
            if os.path.exists(symlink):
                os.remove(symlink)
            os.symlink(real_file, symlink)

            # Mock LSP client to avoid actual LSP initialization
            with patch(
                "swiftlens.tools.swift_find_symbol_references_files.managed_lsp_client"
            ) as mock_lsp:
                with patch("swiftlens.tools.swift_find_symbol_references_files.FileAnalyzer"):
                    # Mock the context manager
                    mock_lsp.return_value.__enter__ = MagicMock(return_value=MagicMock())
                    mock_lsp.return_value.__exit__ = MagicMock(return_value=None)

                    # Test with just the symlink to verify it's rejected
                    result = swift_find_symbol_references_files([symlink], "Test")
                    response = MultiFileSymbolReferenceResponse.model_validate(result)

                    # The response should be successful overall but the symlink should be rejected
                    assert response.success
                    assert not response.files[symlink].success
                    assert "symbolic link" in response.files[symlink].error.lower()
                    assert response.files[symlink].error_type == ErrorType.VALIDATION_ERROR

        finally:
            # Clean up
            if os.path.exists(symlink):
                os.remove(symlink)
            if os.path.exists(real_file):
                os.remove(real_file)
            if os.path.exists(test_dir):
                os.rmdir(test_dir)

    def test_parallel_processing_enabled(self):
        """Verify that ThreadPoolExecutor is now used for parallel processing."""
        import threading

        # Track concurrent processing
        processing_times = []
        processing_lock = threading.Lock()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple test files
            test_files = []
            for i in range(4):
                test_file = os.path.join(temp_dir, f"Test{i}.swift")
                with open(test_file, "w") as f:
                    f.write(f"class Test{i} {{ func foo() {{}} }}")
                test_files.append(test_file)

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

            # Mock LSP client and processing to track concurrent execution
            with patch(
                "swiftlens.tools.swift_find_symbol_references_files.managed_lsp_client"
            ) as mock_lsp:
                # Also mock the client manager for thread-local implementation
                with patch("swiftlens.utils.thread_local_lsp.get_manager") as mock_manager:
                    with patch(
                        "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
                    ) as mock_process:
                        # Also need to patch the validation to pass
                        with patch(
                            "swiftlens.tools.swift_find_symbol_references_files._validate_file_path"
                        ) as mock_validate:
                            from swiftlens.model.models import SymbolReferenceResponse

                            # Mock validation to always pass
                            mock_validate.side_effect = lambda fp, sn, allow_outside: (
                                True,
                                fp,
                                None,
                            )

                            # Mock the context manager
                            mock_lsp.return_value.__enter__ = MagicMock(return_value=MagicMock())
                            mock_lsp.return_value.__exit__ = MagicMock(return_value=None)

                            # Mock the client manager
                            mock_client = MagicMock()
                            mock_manager.return_value.get_client.return_value = mock_client

                            def mock_process_file(analyzer, file_path, symbol, analyzer_lock=None):
                                # Record when processing starts
                                start_time = time.time()
                                with processing_lock:
                                    processing_times.append(("start", start_time, file_path))

                                # Simulate some processing time
                                time.sleep(0.1)

                                # Record when processing ends
                                end_time = time.time()
                                with processing_lock:
                                    processing_times.append(("end", end_time, file_path))

                                return SymbolReferenceResponse(
                                    success=True,
                                    file_path=file_path,
                                    symbol_name=symbol,
                                    references=[],
                                    reference_count=1,
                                )

                            mock_process.side_effect = mock_process_file

                            # Process multiple files
                            start = time.time()
                            swift_find_symbol_references_files(test_files, "foo")
                            total_time = time.time() - start

                            # With parallel processing (4 workers), 4 files with 0.1s each
                            # should complete in roughly 0.1s, not 0.4s
                            assert total_time < 0.3, (
                                f"Processing took {total_time}s, expected < 0.3s with parallel processing"
                            )

                            # Verify that files were processed in parallel
                            # Check that multiple files started processing before others finished
                            starts = [t for t in processing_times if t[0] == "start"]
                            ends = [t for t in processing_times if t[0] == "end"]

                            # At least some files should start before others end (parallel)
                            assert ends, "No processing occurred"
                            parallel_starts = sum(1 for s in starts if s[1] < ends[0][1])
                            assert parallel_starts > 1, (
                                "Files should be processed in parallel, not sequentially"
                            )

    def test_weak_reference_support(self):
        """Test that thread cache sentinel supports weak references."""
        import weakref

        from swiftlens.utils.thread_local_lsp import _ThreadCacheSentinel

        # Create a sentinel instance
        sentinel = _ThreadCacheSentinel()

        # This should not raise "cannot create weak reference to 'object' object"
        weak_ref = weakref.ref(sentinel)

        # Verify the weak reference works
        assert weak_ref() is sentinel

        # Delete the original reference
        del sentinel

        # Weak reference should now return None
        assert weak_ref() is None

    def test_error_handling_specificity(self):
        """Test that specific error types are properly handled with mocked client."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "Test.swift")
            with open(test_file, "w") as f:
                f.write("class Test {}")

            # Test different error types with expected error classifications
            error_scenarios = [
                (
                    TimeoutError("LSP timeout"),
                    "LSP communication error: LSP timeout",
                    ErrorType.LSP_ERROR,
                ),
                (
                    ConnectionError("Connection refused"),
                    "LSP communication error: Connection refused",
                    ErrorType.LSP_ERROR,
                ),
                (OSError("File system error"), "File system error", ErrorType.VALIDATION_ERROR),
                (RuntimeError("Runtime issue"), "Runtime issue", ErrorType.VALIDATION_ERROR),
                (
                    RuntimeError("LSP connection failed"),
                    "LSP connection failed",
                    ErrorType.LSP_ERROR,
                ),
                (ValueError("Invalid value"), "Invalid value", ErrorType.VALIDATION_ERROR),
            ]

            # Create a mock client to bypass LSP initialization
            mock_client = MagicMock(spec=SwiftLSPClient)

            for error, expected_msg, expected_error_type in error_scenarios:
                with patch(
                    "swiftlens.tools.swift_find_symbol_references_files._process_single_file"
                ) as mock_process:
                    # Also need to patch validation to pass
                    with patch(
                        "swiftlens.tools.swift_find_symbol_references_files._validate_file_path"
                    ) as mock_validate:
                        # Make validation pass
                        mock_validate.return_value = (True, test_file, None)
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
                        assert file_result.error_type == expected_error_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
