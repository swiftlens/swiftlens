"""Tool for finding references to a specific symbol across multiple Swift files."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts
from pydantic import ValidationError

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import (
    ErrorType,
    MultiFileSymbolReferenceResponse,
    SymbolReference,
    SymbolReferenceResponse,
)

# Setup debug logger
logger = logging.getLogger(__name__)
debug_enabled = os.environ.get("MCP_DEBUG", "").lower() in ["true", "1", "yes"]

# Constants
MAX_FILES = 500  # Maximum number of files to process
MAX_WORKERS = min(4, (os.cpu_count() or 1) + 1)  # Dynamic thread count


def swift_find_symbol_references_files(
    file_paths: list[str], symbol_name: str, client=None
) -> dict[str, Any]:
    """Find all references to a symbol across multiple Swift files.

    Args:
        file_paths: List of Swift file paths to search
        symbol_name: Name of the symbol to find references for
        client: Optional pre-initialized SwiftLSPClient for performance optimization

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

    # Normalize and deduplicate file paths using Path.resolve()
    normalized_paths = []
    seen_paths = set()
    for path in file_paths:
        try:
            # Use Path.resolve() for full normalization including symlink resolution
            normalized = Path(path).resolve(strict=False)
            normalized_str = str(normalized)
            
            if normalized_str not in seen_paths:
                seen_paths.add(normalized_str)
                normalized_paths.append(normalized_str)
        except (OSError, ValueError) as e:
            # Handle invalid paths gracefully
            logger.debug(f"Failed to normalize path {path}: {e}")
            # Fall back to simple normalization
            normalized = os.path.abspath(path) if not os.path.isabs(path) else path
            normalized = os.path.normpath(normalized)
            if normalized not in seen_paths:
                seen_paths.add(normalized)
                normalized_paths.append(normalized)
    
    file_paths = normalized_paths

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

    try:
        if client:
            # Use provided client (performance optimization for tests)
            analyzer = FileAnalyzer(client)

            # Process files in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_file = {
                    executor.submit(_process_single_file, analyzer, fp, symbol_name): fp
                    for fp in file_paths
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        file_results[file_path] = result
                        if result.success:
                            total_references += result.reference_count
                    except Exception as e:
                        # Handle errors from individual file processing
                        file_results[file_path] = SymbolReferenceResponse(
                            success=False,
                            file_path=file_path,
                            symbol_name=symbol_name,
                            references=[],
                            reference_count=0,
                            error=str(e),
                            error_type=ErrorType.LSP_ERROR,
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

                # Process files in parallel using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_file = {
                        executor.submit(_process_single_file, analyzer, fp, symbol_name): fp
                        for fp in file_paths
                    }

                    for future in as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            result = future.result()
                            file_results[file_path] = result
                            if result.success:
                                total_references += result.reference_count
                        except Exception as e:
                            # Handle errors from individual file processing
                            file_results[file_path] = SymbolReferenceResponse(
                                success=False,
                                file_path=file_path,
                                symbol_name=symbol_name,
                                references=[],
                                reference_count=0,
                                error=str(e),
                                error_type=ErrorType.LSP_ERROR,
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
    except (OSError, RuntimeError) as e:
        return MultiFileSymbolReferenceResponse(
            success=False,
            symbol_name=symbol_name,
            files={},
            total_files=len(file_paths),
            total_references=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()


def _process_single_file(
    analyzer: FileAnalyzer, file_path: str, symbol_name: str
) -> SymbolReferenceResponse:
    """Process a single file for symbol references.

    Args:
        analyzer: FileAnalyzer instance with LSP client
        file_path: Path to the Swift file to analyze
        symbol_name: Name of the symbol to find references for

    Returns:
        SymbolReferenceResponse for this specific file
    """
    # Convert to absolute path if relative - same pattern as other tools
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation for each file
    if not file_path.endswith(".swift"):
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        )

    if not os.path.exists(file_path):
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        )

    try:
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
    except (OSError, RuntimeError, ValueError) as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        )
