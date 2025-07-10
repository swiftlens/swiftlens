"""Tool for summarizing Swift file symbol counts."""

import os

# from collections import defaultdict  # No longer needed
from typing import Any

from lsp.constants import SymbolKind
from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import ErrorType, FileSummaryResponse


def swift_summarize_file(file_path: str) -> dict[str, Any]:
    """Summarize a Swift file by counting symbol types.

    Returns token-optimized counts of classes, functions, enums, etc.

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        FileSummaryResponse as dict with success status, symbol counts, and metadata
    """
    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return FileSummaryResponse(
            success=False,
            file_path=file_path,
            symbol_counts={},
            total_symbols=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return FileSummaryResponse(
            success=False,
            file_path=file_path,
            symbol_counts={},
            total_symbols=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    try:
        # Find Swift project root for proper LSP initialization
        project_root = find_swift_project_root(file_path)

        # Use managed LSP client for efficient reuse
        with managed_lsp_client(
            project_root=project_root, timeout=LSPTimeouts.HEAVY_OPERATION
        ) as client:
            analyzer = FileAnalyzer(client)
            result_dict = analyzer.analyze_file_symbols(file_path)

            if result_dict["success"]:
                if result_dict["symbols"]:
                    # Count symbol types
                    symbol_counts = {}
                    _count_symbols_by_type(result_dict["symbols"], symbol_counts)

                    # Explicitly convert to regular dict to ensure pydantic validation passes
                    symbol_counts_dict = dict(symbol_counts)
                    total_symbols = sum(symbol_counts_dict.values())

                    return FileSummaryResponse(
                        success=True,
                        file_path=file_path,
                        symbol_counts=symbol_counts_dict,
                        total_symbols=total_symbols,
                    ).model_dump()
                else:
                    return FileSummaryResponse(
                        success=True,
                        file_path=file_path,
                        symbol_counts={},
                        total_symbols=0,
                    ).model_dump()
            else:
                error_msg = result_dict.get("error_message", "LSP operation failed")
                return FileSummaryResponse(
                    success=False,
                    file_path=file_path,
                    symbol_counts={},
                    total_symbols=0,
                    error=error_msg,
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except Exception as e:
        import traceback

        error_details = f"{str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        return FileSummaryResponse(
            success=False,
            file_path=file_path,
            symbol_counts={},
            total_symbols=0,
            error=error_details,
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()


def _count_symbols_by_type(symbols: list, counts, depth: int = 0) -> None:
    """Recursively count symbols by their kind with depth limit."""
    # Prevent stack overflow from deeply nested symbols
    MAX_RECURSION_DEPTH = 50
    if depth > MAX_RECURSION_DEPTH:
        return

    for symbol in symbols:
        kind = symbol.get("kind", 0)
        kind_name = SymbolKind.get_name(kind)

        # Log unknown symbol kinds for maintainability
        if kind_name.startswith("Kind"):
            # Note: In production, consider using proper logging
            # import logging; logging.warning(f"Unknown symbol kind '{kind}' encountered")
            pass

        counts[kind_name] = counts.get(kind_name, 0) + 1

        # Recursively count children with incremented depth
        children = symbol.get("children", [])
        if children:
            _count_symbols_by_type(children, counts, depth + 1)


def _format_symbol_counts(counts: dict) -> str:
    """Format symbol counts in token-optimized format."""
    if not counts:
        return "No symbols"

    # Sort by count (descending) then by name for consistent output
    sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))

    # Format as "Type: count" pairs, newline separated
    formatted_lines = []
    for symbol_type, count in sorted_counts:
        formatted_lines.append(f"{symbol_type}: {count}")

    return "\n".join(formatted_lines)
