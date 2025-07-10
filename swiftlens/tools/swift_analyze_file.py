"""Tool for analyzing a single Swift file."""

import os
from typing import Any

from lsp.managed_client import find_swift_project_root, managed_lsp_client
from pydantic import ValidationError

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import ErrorType, FileAnalysisResponse, SwiftSymbolInfo, SymbolKind


def swift_analyze_file(file_path: str) -> dict[str, Any]:
    """Analyze a Swift file and extract its symbol structure using SourceKit-LSP.

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        FileAnalysisResponse as dict with success status, symbols, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return FileAnalysisResponse(
            success=False,
            file_path=file_path,
            symbols=[],
            symbol_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return FileAnalysisResponse(
            success=False,
            file_path=file_path,
            symbols=[],
            symbol_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    try:
        # Find Swift project root for proper LSP initialization
        project_root = find_swift_project_root(file_path)

        # Initialize LSP client with project root and longer timeout for indexing
        with managed_lsp_client(project_root=project_root, timeout=10.0) as client:
            analyzer = FileAnalyzer(client)
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
                ).model_dump()
            else:
                # LSP error
                return FileAnalysisResponse(
                    success=False,
                    file_path=file_path,
                    symbols=[],
                    symbol_count=0,
                    error=result_dict["error_message"],
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except Exception as e:
        return FileAnalysisResponse(
            success=False,
            file_path=file_path,
            symbols=[],
            symbol_count=0,
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
