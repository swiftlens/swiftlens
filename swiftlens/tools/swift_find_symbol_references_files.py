"""Tool for finding references to a specific symbol across multiple Swift files."""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
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
    MultiFileSymbolReferenceResponse,
    SymbolReference,
    SymbolReferenceResponse,
)
from swiftlens.utils.environment import get_max_files, get_max_workers
from swiftlens.utils.thread_local_lsp import get_thread_local_analyzer

# Setup debug logger
logger = logging.getLogger(__name__)
debug_enabled = os.environ.get("MCP_DEBUG", "").lower() in ["true", "1", "yes"]

# Configure module-specific logging with dedicated handler when debug is enabled
if debug_enabled and not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# Constants
MAX_FILES = get_max_files(default=500)
# Thread pool configuration
MAX_WORKERS = get_max_workers(default=4)


def swift_find_symbol_references_files(
    file_paths: list[str], symbol_name: str, client=None, allow_outside_cwd: bool = False
) -> dict[str, Any]:
    """Find all references to a symbol across multiple Swift files.

    Args:
        file_paths: List of Swift file paths to search
        symbol_name: Name of the symbol to find references for
        client: Optional pre-initialized SwiftLSPClient for performance optimization
        allow_outside_cwd: Allow processing files outside the current working directory

    Returns:
        MultiFileSymbolReferenceResponse as dict with success status, per-file results, and metadata
    """

    if not file_paths:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=0,
            total_references=0,
            error="No files provided",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Check file count limit
    if len(file_paths) > MAX_FILES:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=len(file_paths),
            total_references=0,
            error=f"Too many files: {len(file_paths)}. Maximum allowed is {MAX_FILES}",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Normalize and deduplicate file paths
    # Keep original paths for result keys but use resolved paths for deduplication
    unique_paths = []
    seen_resolved = set()

    for path in file_paths:
        try:
            # Use Path.resolve() for deduplication check
            resolved = Path(path).resolve(strict=False)
            resolved_str = str(resolved)

            if resolved_str not in seen_resolved:
                seen_resolved.add(resolved_str)
                # Keep the original path format for consistency
                unique_paths.append(path)
        except (OSError, ValueError) as e:
            # Handle invalid paths gracefully
            logger.debug(f"Failed to resolve path {path}: {e}")
            # Fall back to simple normalization for deduplication
            normalized = os.path.abspath(path) if not os.path.isabs(path) else path
            normalized = os.path.normpath(normalized)
            if normalized not in seen_resolved:
                seen_resolved.add(normalized)
                unique_paths.append(path)

    file_paths = unique_paths

    if not symbol_name or (isinstance(symbol_name, str) and not symbol_name.strip()):
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name or "",
            files={},
            total_files=len(file_paths),
            total_references=0,
            error="Symbol name cannot be empty",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    file_results = {}
    total_references = 0
    # Lock for thread-safe accumulator updates
    accumulator_lock = threading.Lock()

    try:
        if client:
            # Use provided client (performance optimization for tests)
            analyzer = FileAnalyzer(client)

            # Process all files - when client is provided, use sequential processing
            # to ensure the provided client is used for all files
            file_results, total_references = _process_all_files(
                file_paths,
                symbol_name,
                analyzer,
                accumulator_lock,
                allow_outside_cwd,
                use_provided_analyzer=True,
            )
        else:
            # Find Swift project root for proper LSP initialization
            # Use the first file path to determine project root
            project_root = find_swift_project_root(file_paths[0]) if file_paths else None
            if project_root is None and file_paths:
                # Fallback for test environments or isolated files - use file's directory
                # This handles cases where Swift files are in temporary directories during testing
                project_root = os.path.dirname(os.path.abspath(file_paths[0]))

            # Initialize LSP client with project root and longer timeout for references
            with managed_lsp_client(
                project_root=project_root, timeout=LSPTimeouts.HEAVY_OPERATION
            ) as new_client:
                analyzer = FileAnalyzer(new_client)

                # Process all files with a single thread pool
                file_results, total_references = _process_all_files(
                    file_paths, symbol_name, analyzer, accumulator_lock, allow_outside_cwd
                )

        return MultiFileSymbolReferenceResponse(
            success=True,
            symbol_name=symbol_name,
            files=file_results,
            total_files=len(file_paths),
            total_references=total_references,
        ).model_dump()

    except (TimeoutError, ConnectionError) as e:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=len(file_paths),
            total_references=0,
            error=f"LSP communication error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
    except OSError as e:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=len(file_paths),
            total_references=0,
            error=str(e),
            error_type=ErrorType.FILE_NOT_FOUND
            if "No such file" in str(e)
            else ErrorType.VALIDATION_ERROR,
        ).model_dump()
    except RuntimeError as e:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=len(file_paths),
            total_references=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR if "LSP" in str(e) else ErrorType.VALIDATION_ERROR,
        ).model_dump()


def _validate_file_path(
    file_path: str, symbol_name: str, allow_outside_cwd: bool = False
) -> tuple[bool, str, SymbolReferenceResponse]:
    """Pre-validate a file path before processing.

    Args:
        file_path: Path to validate
        symbol_name: Symbol name for error responses
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
            SymbolReferenceResponse(
                success=False,
                file_path=file_path,
                symbol_name=symbol_name,
                references=[],
                reference_count=0,
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
                SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error="File must be a Swift file (.swift extension)",
                    error_type=ErrorType.VALIDATION_ERROR,
                ),
            )
        return (
            False,
            file_path,
            SymbolReferenceResponse(
                success=False,
                file_path=file_path,
                symbol_name=symbol_name,
                references=[],
                reference_count=0,
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
                    SymbolReferenceResponse(
                        success=False,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        references=[],
                        reference_count=0,
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
                SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=f"File is outside current working directory: {file_path}",
                    error_type=ErrorType.VALIDATION_ERROR,
                ),
            )

    # Check file extension (case-insensitive to support .SWIFT on macOS)
    if not file_path.lower().endswith(".swift"):
        return (
            False,
            file_path,
            SymbolReferenceResponse(
                success=False,
                file_path=file_path,
                symbol_name=symbol_name,
                references=[],
                reference_count=0,
                error="File must be a Swift file (.swift extension)",
                error_type=ErrorType.VALIDATION_ERROR,
            ),
        )

    return True, file_path, None


def _process_all_files(
    file_paths: list[str],
    symbol_name: str,
    analyzer: FileAnalyzer,
    accumulator_lock: threading.Lock,
    allow_outside_cwd: bool = False,
    use_provided_analyzer: bool = False,
) -> tuple[dict[str, SymbolReferenceResponse], int]:
    """Process all files using a single thread pool executor.

    Args:
        file_paths: List of file paths to process
        symbol_name: Symbol name to search for
        analyzer: FileAnalyzer instance (used for sequential processing or when client is provided)
        accumulator_lock: Lock for thread-safe accumulator updates
        allow_outside_cwd: Allow processing files outside the current working directory
        use_provided_analyzer: Force sequential processing with provided analyzer (for tests)

    Returns:
        Tuple of (file_results dict, total_references count)
    """
    file_results = {}
    total_references = 0

    # Pre-validate all files
    valid_files = []
    for file_path in file_paths:
        is_valid, resolved_path, error_response = _validate_file_path(
            file_path, symbol_name, allow_outside_cwd
        )
        if is_valid:
            valid_files.append(resolved_path)
        else:
            file_results[file_path] = error_response

    # Find project root for LSP initialization (used by all threads)
    project_root = find_swift_project_root(valid_files[0]) if valid_files else None
    if project_root is None and valid_files:
        # Fallback for test environments or isolated files
        project_root = os.path.dirname(os.path.abspath(valid_files[0]))

    # Process sequentially if:
    # 1. We have a provided analyzer (test mode/specific client)
    # 2. Small file count (performance optimization)
    if use_provided_analyzer or len(valid_files) <= 2:
        for file_path in valid_files:
            try:
                result = _process_single_file(analyzer, file_path, symbol_name, None)
                file_results[file_path] = result
                if result.success:
                    with accumulator_lock:
                        total_references += result.reference_count
            except (TimeoutError, ConnectionError) as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=f"LSP communication error: {str(e)}",
                    error_type=ErrorType.LSP_ERROR,
                )
            except OSError as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=str(e),
                    error_type=ErrorType.FILE_NOT_FOUND
                    if "No such file" in str(e)
                    else ErrorType.VALIDATION_ERROR,
                )
            except (RuntimeError, ValueError) as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=str(e),
                    error_type=ErrorType.LSP_ERROR
                    if "LSP" in str(e)
                    else ErrorType.VALIDATION_ERROR,
                )
        return file_results, total_references

    # Use a thread pool for parallel processing
    # Each thread will create its own LSP client to avoid thread safety issues
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks only for valid files
        future_to_file = {
            executor.submit(
                _process_single_file_with_new_client,
                file_path,
                symbol_name,
                project_root,
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
                        total_references += result.reference_count
            except (TimeoutError, ConnectionError) as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=f"LSP communication error: {str(e)}",
                    error_type=ErrorType.LSP_ERROR,
                )
            except OSError as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=str(e),
                    error_type=ErrorType.FILE_NOT_FOUND
                    if "No such file" in str(e)
                    else ErrorType.VALIDATION_ERROR,
                )
            except (RuntimeError, ValueError) as e:
                file_results[file_path] = SymbolReferenceResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    references=[],
                    reference_count=0,
                    error=str(e),
                    error_type=ErrorType.LSP_ERROR
                    if "LSP" in str(e)
                    else ErrorType.VALIDATION_ERROR,
                )

    return file_results, total_references


def _process_single_file_with_new_client(
    file_path: str,
    symbol_name: str,
    project_root: str,
) -> SymbolReferenceResponse:
    """Process a single file using thread-local LSP client for optimal performance.

    Uses thread-local storage to reuse LSP clients across files in the same thread,
    avoiding the 2-second initialization overhead while maintaining thread safety.

    Args:
        file_path: Path to the Swift file to analyze
        symbol_name: Name of the symbol to find references for
        project_root: Project root for LSP initialization

    Returns:
        SymbolReferenceResponse for this specific file
    """
    try:
        # Get thread-local analyzer (reuses LSP client within same thread)
        analyzer = get_thread_local_analyzer(project_root)
        return _process_single_file(analyzer, file_path, symbol_name, None)
    except Exception as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=f"LSP error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        )


def _process_single_file(
    analyzer: FileAnalyzer,
    file_path: str,
    symbol_name: str,
    analyzer_lock: threading.RLock = None,
) -> SymbolReferenceResponse:
    """Process a single file for symbol references.

    Note: File validation is done in _validate_file_path before submission to thread pool.

    Args:
        analyzer: FileAnalyzer instance with LSP client
        file_path: Path to the Swift file to analyze (already validated)
        symbol_name: Name of the symbol to find references for
        analyzer_lock: Optional lock for thread-safe analyzer access

    Returns:
        SymbolReferenceResponse for this specific file
    """

    try:
        # Use lock for thread-safe analyzer access if provided
        if analyzer_lock:
            with analyzer_lock:
                result_dict = analyzer.find_symbol_references(file_path, symbol_name)
        else:
            result_dict = analyzer.find_symbol_references(file_path, symbol_name)

        if result_dict["success"]:
            # Convert references to Pydantic models
            references = []
            for ref in result_dict["references"]:
                try:
                    symbol_ref = SymbolReference(
                        file_path=ref.get("file_path", file_path),
                        line=ref["line"],
                        character=ref["character"],
                        context=ref["context_line"].strip() if ref["context_line"] else "",
                    )
                    references.append(symbol_ref)
                except ValidationError as e:
                    # Skip invalid references but continue processing
                    if debug_enabled:
                        logger.debug(
                            f"Skipping invalid reference in {file_path}: {e}, Reference data: {ref}"
                        )
                    continue

            response = SymbolReferenceResponse(
                success=True,
                file_path=file_path,
                symbol_name=symbol_name,
                references=references,
                reference_count=len(references),
            )

            # Return response directly without building unnecessary diagnostics
            return response
        else:
            # LSP error for this file
            return SymbolReferenceResponse(
                success=False,
                file_path=file_path,
                symbol_name=symbol_name,
                references=[],
                reference_count=0,
                error=result_dict["error_message"],
                error_type=ErrorType.LSP_ERROR,
            )

    except (TimeoutError, ConnectionError) as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=f"LSP communication error: {str(e)}",
            error_type=ErrorType.LSP_ERROR,
        )
    except OSError as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=str(e),
            error_type=ErrorType.FILE_NOT_FOUND
            if "No such file" in str(e)
            else ErrorType.VALIDATION_ERROR,
        )
    except (RuntimeError, ValueError) as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR if "LSP" in str(e) else ErrorType.VALIDATION_ERROR,
        )
