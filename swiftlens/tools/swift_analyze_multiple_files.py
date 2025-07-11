"""Tool for analyzing multiple Swift files."""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

try:
    from lsp.managed_client import find_swift_project_root, managed_lsp_client
    from lsp.timeouts import LSPTimeouts
except ImportError as e:
    raise ImportError(
        "swiftlens-core package is required but not installed. "
        "Please install it with: pip install swiftlens-core"
    ) from e

from pydantic import ValidationError

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import (
    ErrorType,
    FileAnalysisResponse,
    MultiFileAnalysisResponse,
    SwiftSymbolInfo,
    SymbolKind,
)
from swiftlens.utils.environment import get_max_files, get_max_workers
from swiftlens.utils.thread_local_lsp import get_thread_local_analyzer

# Setup logger
logger = logging.getLogger(__name__)

# Thread pool configuration
MAX_WORKERS = get_max_workers(default=4)
MAX_FILES = get_max_files(default=500)


def swift_analyze_multiple_files(
    file_paths: list[str], allow_outside_cwd: bool = False
) -> dict[str, Any]:
    """Analyze multiple Swift files and extract their symbol structures.

    Args:
        file_paths: List of Swift file paths to analyze
        allow_outside_cwd: Allow processing files outside the current working directory

    Returns:
        MultiFileAnalysisResponse as dict with success status, file results, and metadata
    """

    if not file_paths:
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=0,
            total_symbols=0,
            error="No files provided",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if len(file_paths) > MAX_FILES:
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=f"Too many files provided: {len(file_paths)}. Maximum allowed: {MAX_FILES}",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    file_results = {}
    total_symbols = 0
    # Lock for thread-safe accumulator updates
    accumulator_lock = threading.Lock()

    try:
        # Find Swift project root for proper LSP initialization
        # Use the first file path to determine project root
        project_root = find_swift_project_root(file_paths[0]) if file_paths else None
        if project_root is None and file_paths:
            # Fallback for test environments or isolated files
            project_root = os.path.dirname(os.path.abspath(file_paths[0]))

        # Initialize LSP client with project root and longer timeout for indexing
        with managed_lsp_client(
            project_root=project_root, timeout=LSPTimeouts.HEAVY_OPERATION
        ) as client:
            analyzer = FileAnalyzer(client)

            # Process all files with a single thread pool
            file_results, total_symbols = _process_all_files(
                file_paths, analyzer, accumulator_lock, allow_outside_cwd, project_root
            )

        return MultiFileAnalysisResponse(
            success=True,
            files=file_results,
            total_files=len(file_paths),
            total_symbols=total_symbols,
        ).model_dump()

    except (TimeoutError, ConnectionError) as e:
        # Handle LSP communication errors
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=f"LSP communication error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
    except OSError as e:
        # Handle file system errors
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=f"File system error: {str(e)}",
            error_type=ErrorType.FILE_NOT_FOUND
            if "No such file" in str(e)
            else ErrorType.VALIDATION_ERROR,
        ).model_dump()
    except (RuntimeError, ValueError) as e:
        # Handle runtime and validation errors
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=f"Processing error: {str(e)}",
            error_type=ErrorType.LSP_ERROR if "LSP" in str(e) else ErrorType.VALIDATION_ERROR,
        ).model_dump()
    except KeyboardInterrupt:
        # Don't catch user interrupts
        raise
    except Exception as e:
        # Log unexpected errors for debugging
        logger.exception("Unexpected error in file analysis")
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=f"Unexpected error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()


def _validate_file_path(
    file_path: str, allow_outside_cwd: bool = False
) -> tuple[bool, str, FileAnalysisResponse]:
    """Pre-validate a file path before processing.

    Args:
        file_path: Path to validate
        allow_outside_cwd: Allow processing files outside the current working directory

    Returns:
        Tuple of (is_valid, resolved_path, error_response if invalid)
    """
    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)

    # Check file existence first
    if not os.path.exists(file_path):
        return (
            False,
            file_path,
            FileAnalysisResponse(
                success=False,
                file_path=file_path,
                symbols=[],
                symbol_count=0,
                error=f"File not found: {file_path}",
                error_type=ErrorType.FILE_NOT_FOUND,
            ),
        )

    # Security validation: check for symbolic links
    real_path = os.path.realpath(file_path)
    if real_path != file_path:
        # For non-Swift files in symlinks, check extension first
        if not file_path.lower().endswith(".swift"):
            return (
                False,
                file_path,
                FileAnalysisResponse(
                    success=False,
                    file_path=file_path,
                    symbols=[],
                    symbol_count=0,
                    error="File must be a Swift file (.swift extension)",
                    error_type=ErrorType.VALIDATION_ERROR,
                ),
            )
        return (
            False,
            file_path,
            FileAnalysisResponse(
                success=False,
                file_path=file_path,
                symbols=[],
                symbol_count=0,
                error=f"Symbolic links are not allowed for security reasons. File: {file_path} resolves to: {real_path}",
                error_type=ErrorType.VALIDATION_ERROR,
            ),
        )

    # Ensure the resolved path is within or below the current working directory
    cwd = os.path.abspath(os.getcwd())
    # Use os.path.commonpath for secure path containment check
    try:
        common_path = os.path.commonpath([cwd, real_path])
        if common_path != cwd:
            if not allow_outside_cwd:
                return (
                    False,
                    file_path,
                    FileAnalysisResponse(
                        success=False,
                        file_path=file_path,
                        symbols=[],
                        symbol_count=0,
                        error=f"File is outside current working directory: {file_path}",
                        error_type=ErrorType.VALIDATION_ERROR,
                    ),
                )
    except ValueError:
        # os.path.commonpath raises ValueError if paths are on different drives (Windows)
        if not allow_outside_cwd:
            return (
                False,
                file_path,
                FileAnalysisResponse(
                    success=False,
                    file_path=file_path,
                    symbols=[],
                    symbol_count=0,
                    error=f"File is outside current working directory: {file_path}",
                    error_type=ErrorType.VALIDATION_ERROR,
                ),
            )

    # Check file extension (case-insensitive to support .SWIFT on macOS)
    if not file_path.lower().endswith(".swift"):
        return (
            False,
            file_path,
            FileAnalysisResponse(
                success=False,
                file_path=file_path,
                symbols=[],
                symbol_count=0,
                error="File must be a Swift file (.swift extension)",
                error_type=ErrorType.VALIDATION_ERROR,
            ),
        )

    return True, file_path, None


def _process_all_files(
    file_paths: list[str],
    analyzer: FileAnalyzer,
    accumulator_lock: threading.Lock,
    allow_outside_cwd: bool = False,
    project_root: str = None,
) -> tuple[dict[str, FileAnalysisResponse], int]:
    """Process all files using a single thread pool executor.

    Args:
        file_paths: List of file paths to process
        analyzer: FileAnalyzer instance (only used for sequential processing)
        accumulator_lock: Lock for thread-safe accumulator updates
        allow_outside_cwd: Allow processing files outside the current working directory
        project_root: Project root for LSP initialization

    Returns:
        Tuple of (file_results dict, total_symbols count)
    """
    file_results = {}
    total_symbols = 0

    # Pre-validate all files
    valid_files = []
    for file_path in file_paths:
        is_valid, resolved_path, error_response = _validate_file_path(file_path, allow_outside_cwd)
        if is_valid:
            valid_files.append(resolved_path)
        else:
            file_results[file_path] = error_response

    # Performance optimization: process small file counts sequentially
    # to avoid thread pool overhead (~30ms startup cost)
    if len(valid_files) <= 2:
        for file_path in valid_files:
            result = _process_single_file(analyzer, file_path, None)
            file_results[file_path] = result
            if result.success:
                with accumulator_lock:
                    total_symbols += result.symbol_count
        return file_results, total_symbols

    # Use a thread pool for parallel processing
    # Each thread will create its own LSP client to avoid thread safety issues
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks only for valid files
        future_to_file = {
            executor.submit(
                _process_single_file_with_new_client, file_path, project_root
            ): file_path
            for file_path in valid_files
        }

        # Collect results as they complete
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                result = future.result()
                file_results[file_path] = result
                if result.success:
                    with accumulator_lock:
                        total_symbols += result.symbol_count
            except Exception as e:
                file_results[file_path] = FileAnalysisResponse(
                    success=False,
                    file_path=file_path,
                    symbols=[],
                    symbol_count=0,
                    error=str(e),
                    error_type=ErrorType.LSP_ERROR,
                )

    return file_results, total_symbols


def _process_single_file_with_new_client(
    file_path: str,
    project_root: str,
) -> FileAnalysisResponse:
    """Process a single file using thread-local LSP client for optimal performance.

    Uses thread-local storage to reuse LSP clients across files in the same thread,
    avoiding the 2-second initialization overhead while maintaining thread safety.

    Args:
        file_path: Path to the Swift file to analyze
        project_root: Project root for LSP initialization

    Returns:
        FileAnalysisResponse for this specific file
    """
    try:
        # Get thread-local analyzer (reuses LSP client within same thread)
        analyzer = get_thread_local_analyzer(project_root)
        return _process_single_file(analyzer, file_path, None)
    except Exception as e:
        return FileAnalysisResponse(
            success=False,
            file_path=file_path,
            symbols=[],
            symbol_count=0,
            error=f"LSP error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        )


def _process_single_file(
    analyzer: FileAnalyzer,
    file_path: str,
    analyzer_lock: threading.RLock = None,
) -> FileAnalysisResponse:
    """Process a single file for symbol analysis.

    Note: File validation is done in _validate_file_path before submission to thread pool.

    Args:
        analyzer: FileAnalyzer instance with LSP client
        file_path: Path to the Swift file to analyze (already validated)
        analyzer_lock: Optional lock for thread-safe analyzer access

    Returns:
        FileAnalysisResponse for this specific file
    """

    # Use lock for thread-safe analyzer access if provided
    if analyzer_lock:
        with analyzer_lock:
            result_dict = analyzer.analyze_file_symbols(file_path)
    else:
        result_dict = analyzer.analyze_file_symbols(file_path)

    if result_dict["success"]:
        # Convert symbols to Pydantic models
        symbols = []
        for symbol in result_dict["symbols"]:
            try:
                swift_symbol = _convert_symbol_to_model(symbol)
                symbols.append(swift_symbol)
            except ValidationError:
                # Skip invalid symbols but continue processing
                continue

        return FileAnalysisResponse(
            success=True,
            file_path=file_path,
            symbols=symbols,
            symbol_count=len(symbols),
        )
    else:
        # LSP error for this file
        return FileAnalysisResponse(
            success=False,
            file_path=file_path,
            symbols=[],
            symbol_count=0,
            error=result_dict.get("error_message", result_dict.get("error", "Unknown error")),
            error_type=ErrorType.LSP_ERROR,
        )


def _convert_symbol_to_model(symbol: dict) -> SwiftSymbolInfo:
    """Convert raw symbol dict to SwiftSymbolInfo model."""
    # Map LSP symbol kind names to our enum
    kind_name = symbol.get("kind_name", "").strip()
    try:
        symbol_kind = SymbolKind(kind_name)
    except ValueError:
        # Default to a generic symbol kind if not recognized
        symbol_kind = (
            SymbolKind.FUNCTION if "function" in kind_name.lower() else SymbolKind.VARIABLE
        )

    # Convert children recursively
    children = []
    for child in symbol.get("children", []):
        try:
            child_symbol = _convert_symbol_to_model(child)
            children.append(child_symbol)
        except ValidationError:
            # Skip invalid children but continue
            continue

    return SwiftSymbolInfo(
        name=symbol["name"],
        kind=symbol_kind,
        line=symbol.get("range", {}).get("start", {}).get("line", 1),
        character=symbol.get("range", {}).get("start", {}).get("character", 0),
        children=children,
    )
