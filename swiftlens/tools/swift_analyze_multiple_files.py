"""Tool for analyzing multiple Swift files."""

import os
from typing import Any

from analysis.file_analyzer import FileAnalyzer
from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts
from model.models import (
    ErrorType,
    FileAnalysisResponse,
    MultiFileAnalysisResponse,
    SwiftSymbolInfo,
    SymbolKind,
)
from pydantic import ValidationError


def swift_analyze_multiple_files(file_paths: list[str]) -> dict[str, Any]:
    """Analyze multiple Swift files and extract their symbol structures.

    Args:
        file_paths: List of Swift file paths to analyze

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

    file_results = {}
    total_symbols = 0

    try:
        # Find Swift project root for proper LSP initialization
        # Use the first file path to determine project root
        project_root = find_swift_project_root(file_paths[0]) if file_paths else None

        # Initialize LSP client with project root and longer timeout for indexing
        with managed_lsp_client(
            project_root=project_root, timeout=LSPTimeouts.HEAVY_OPERATION
        ) as client:
            analyzer = FileAnalyzer(client)

            for file_path in file_paths:
                # Convert to absolute path if relative
                if not os.path.isabs(file_path):
                    file_path = os.path.join(os.getcwd(), file_path)

                # Early validation for each file
                if not file_path.endswith(".swift"):
                    file_results[file_path] = FileAnalysisResponse(
                        success=False,
                        file_path=file_path,
                        symbols=[],
                        symbol_count=0,
                        error="File must be a Swift file (.swift extension)",
                        error_type=ErrorType.VALIDATION_ERROR,
                    )
                    continue

                if not os.path.exists(file_path):
                    file_results[file_path] = FileAnalysisResponse(
                        success=False,
                        file_path=file_path,
                        symbols=[],
                        symbol_count=0,
                        error=f"File not found: {file_path}",
                        error_type=ErrorType.FILE_NOT_FOUND,
                    )
                    continue

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

                    file_results[file_path] = FileAnalysisResponse(
                        success=True,
                        file_path=file_path,
                        symbols=symbols,
                        symbol_count=len(symbols),
                    )
                    total_symbols += len(symbols)
                else:
                    # LSP error for this file
                    file_results[file_path] = FileAnalysisResponse(
                        success=False,
                        file_path=file_path,
                        symbols=[],
                        symbol_count=0,
                        error=result_dict["error_message"],
                        error_type=ErrorType.LSP_ERROR,
                    )

        return MultiFileAnalysisResponse(
            success=True,
            files=file_results,
            total_files=len(file_paths),
            total_symbols=total_symbols,
        ).model_dump()

    except Exception as e:
        return MultiFileAnalysisResponse(
            success=False,
            files={},
            total_files=len(file_paths),
            total_symbols=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()


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
