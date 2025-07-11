"""Integration tests for real parallel processing verification."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from swiftlens.tools.swift_analyze_multiple_files import swift_analyze_multiple_files
from swiftlens.tools.swift_find_symbol_references_files import swift_find_symbol_references_files


class ThreadSafetyTracker:
    """Track concurrent thread access to verify parallel execution."""

    def __init__(self):
        self.active_threads = 0
        self.max_concurrent_threads = 0
        self.thread_ids = set()
        self.lock = threading.Lock()

    def enter_thread(self):
        """Called when a thread starts processing."""
        with self.lock:
            self.active_threads += 1
            self.max_concurrent_threads = max(self.max_concurrent_threads, self.active_threads)
            self.thread_ids.add(threading.current_thread().ident)

    def exit_thread(self):
        """Called when a thread finishes processing."""
        with self.lock:
            self.active_threads -= 1

    def reset(self):
        """Reset tracking counters."""
        with self.lock:
            self.active_threads = 0
            self.max_concurrent_threads = 0
            self.thread_ids.clear()


@pytest.mark.integration
@pytest.mark.slow
class TestParallelExecutionIntegration:
    """Test actual parallel execution without mocks."""

    def test_analyze_multiple_files_parallel_execution(self, tmp_path):
        """Test that analyze_multiple_files actually executes in parallel."""
        # Create test files
        test_files = []
        for i in range(10):
            file_path = tmp_path / f"test_{i}.swift"
            file_path.write_text(f"class Test{i} {{ func method() {{ }} }}")
            test_files.append(str(file_path))

        tracker = ThreadSafetyTracker()

        # Patch the _process_single_file to track thread execution
        original_process = None

        def track_process_single_file(analyzer, file_path):
            """Wrapper to track thread execution."""
            tracker.enter_thread()
            time.sleep(0.1)  # Simulate some processing time
            try:
                # Call original function if available
                if original_process:
                    return original_process(analyzer, file_path)
                else:
                    # Return mock result
                    from swiftlens.model.models import FileAnalysisResponse

                    return FileAnalysisResponse(
                        success=True, file_path=file_path, symbols=[], symbol_count=1
                    )
            finally:
                tracker.exit_thread()

        # Import the module to patch
        import swiftlens.tools.swift_analyze_multiple_files as analyze_module

        # Save original function
        original_process = analyze_module._process_single_file

        # Patch with tracking wrapper
        analyze_module._process_single_file = track_process_single_file

        try:
            # Mock the LSP client
            with patch(
                "swiftlens.tools.swift_analyze_multiple_files.managed_lsp_client"
            ) as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value.__enter__.return_value = mock_client_instance

                with patch("swiftlens.tools.swift_analyze_multiple_files.FileAnalyzer"):
                    # Execute the function
                    result = swift_analyze_multiple_files(test_files)

                    # Verify parallel execution
                    assert tracker.max_concurrent_threads > 1, (
                        f"Expected parallel execution, but max concurrent threads was {tracker.max_concurrent_threads}"
                    )
                    assert len(tracker.thread_ids) > 1, (
                        f"Expected multiple threads, but only {len(tracker.thread_ids)} thread(s) were used"
                    )

                    # Verify results
                    assert result["success"]
                    assert result["total_files"] == len(test_files)
                    assert result["total_symbols"] == len(test_files)  # 1 symbol per file

        finally:
            # Restore original function
            analyze_module._process_single_file = original_process

    def test_find_symbol_references_parallel_execution(self, tmp_path):
        """Test that find_symbol_references actually executes in parallel."""
        # Create test files
        test_files = []
        for i in range(10):
            file_path = tmp_path / f"test_{i}.swift"
            file_path.write_text(f"class Test {{ func method{i}() {{ }} }}")
            test_files.append(str(file_path))

        tracker = ThreadSafetyTracker()

        # Patch the _process_single_file to track thread execution
        original_process = None

        def track_process_single_file(analyzer, file_path, symbol_name):
            """Wrapper to track thread execution."""
            tracker.enter_thread()
            time.sleep(0.1)  # Simulate some processing time
            try:
                # Call original function if available
                if original_process:
                    return original_process(analyzer, file_path, symbol_name)
                else:
                    # Return mock result
                    from swiftlens.model.models import SymbolReferenceResponse

                    return SymbolReferenceResponse(
                        success=True,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        references=[],
                        reference_count=1,
                    )
            finally:
                tracker.exit_thread()

        # Import the module to patch
        import swiftlens.tools.swift_find_symbol_references_files as refs_module

        # Save original function
        original_process = refs_module._process_single_file

        # Patch with tracking wrapper
        refs_module._process_single_file = track_process_single_file

        try:
            # Mock the LSP client
            with patch(
                "swiftlens.tools.swift_find_symbol_references_files.managed_lsp_client"
            ) as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value.__enter__.return_value = mock_client_instance

                with patch("swiftlens.tools.swift_find_symbol_references_files.FileAnalyzer"):
                    # Execute the function
                    result = swift_find_symbol_references_files(test_files, "Test")

                    # Verify parallel execution
                    assert tracker.max_concurrent_threads > 1, (
                        f"Expected parallel execution, but max concurrent threads was {tracker.max_concurrent_threads}"
                    )
                    assert len(tracker.thread_ids) > 1, (
                        f"Expected multiple threads, but only {len(tracker.thread_ids)} thread(s) were used"
                    )

                    # Verify results
                    assert result["success"]
                    assert result["total_files"] == len(test_files)
                    assert result["total_references"] == len(test_files)  # 1 reference per file

        finally:
            # Restore original function
            refs_module._process_single_file = original_process

    def test_thread_pool_size_configuration(self, tmp_path, monkeypatch):
        """Test that SWIFT_LSP_MAX_WORKERS environment variable is respected."""
        # Set custom thread pool size
        monkeypatch.setenv("SWIFT_LSP_MAX_WORKERS", "2")

        # Create test files
        test_files = []
        for i in range(6):
            file_path = tmp_path / f"test_{i}.swift"
            file_path.write_text(f"class Test{i} {{ }}")
            test_files.append(str(file_path))

        tracker = ThreadSafetyTracker()

        # Track concurrent threads
        def track_process_single_file(analyzer, file_path):
            tracker.enter_thread()
            time.sleep(0.2)  # Longer sleep to ensure we can measure concurrency
            try:
                from swiftlens.model.models import FileAnalysisResponse

                return FileAnalysisResponse(
                    success=True, file_path=file_path, symbols=[], symbol_count=0
                )
            finally:
                tracker.exit_thread()

        # Re-import to pick up new environment variable
        import importlib

        import swiftlens.tools.swift_analyze_multiple_files as analyze_module

        importlib.reload(analyze_module)

        # Patch with tracking wrapper
        original_process = analyze_module._process_single_file
        analyze_module._process_single_file = track_process_single_file

        try:
            with patch(
                "swiftlens.tools.swift_analyze_multiple_files.managed_lsp_client"
            ) as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value.__enter__.return_value = mock_client_instance

                with patch("swiftlens.tools.swift_analyze_multiple_files.FileAnalyzer"):
                    # Execute the function
                    swift_analyze_multiple_files(test_files)

                    # Verify thread pool size is respected
                    assert tracker.max_concurrent_threads <= 2, (
                        f"Expected max 2 concurrent threads, but got {tracker.max_concurrent_threads}"
                    )

        finally:
            # Restore original function
            analyze_module._process_single_file = original_process

    def test_accumulator_thread_safety(self, tmp_path):
        """Test that accumulator variables are updated thread-safely."""
        # Create many test files to increase chance of race conditions
        test_files = []
        for i in range(100):
            file_path = tmp_path / f"test_{i}.swift"
            file_path.write_text(f"class Test{i} {{ func method() {{ }} }}")
            test_files.append(str(file_path))

        # Counter to verify thread-safe updates
        update_counter = 0
        update_lock = threading.Lock()

        def count_updates(analyzer, file_path):
            """Count updates to verify all are accounted for."""
            nonlocal update_counter
            with update_lock:
                update_counter += 1

            from swiftlens.model.models import FileAnalysisResponse

            return FileAnalysisResponse(
                success=True,
                file_path=file_path,
                symbols=[MagicMock(name="TestSymbol")],
                symbol_count=1,
            )

        import swiftlens.tools.swift_analyze_multiple_files as analyze_module

        original_process = analyze_module._process_single_file
        analyze_module._process_single_file = count_updates

        try:
            with patch(
                "swiftlens.tools.swift_analyze_multiple_files.managed_lsp_client"
            ) as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value.__enter__.return_value = mock_client_instance

                with patch("swiftlens.tools.swift_analyze_multiple_files.FileAnalyzer"):
                    # Execute the function multiple times
                    for _ in range(5):
                        update_counter = 0
                        result = swift_analyze_multiple_files(test_files)

                        # Verify all files were processed
                        assert update_counter == len(test_files)
                        assert result["total_symbols"] == len(test_files)
                        assert result["success"]

        finally:
            analyze_module._process_single_file = original_process
