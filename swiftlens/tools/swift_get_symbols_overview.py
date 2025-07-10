"""Tool for extracting top-level symbols overview from Swift files."""

import os
from typing import Any

from lsp.constants import SymbolKind as LSPSymbolKind
from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import ErrorType, SwiftSymbolInfo, SymbolKind, SymbolsOverviewResponse


def _convert_lsp_symbol_kind_to_string(kind: int) -> str:
    """Convert LSP symbol kind integer to SymbolKind enum string value.

    Args:
        kind: LSP symbol kind integer

    Returns:
        String value suitable for SymbolKind enum
    """
    kind_map = {
        LSPSymbolKind.FILE: "File",
        LSPSymbolKind.MODULE: "Module",
        LSPSymbolKind.NAMESPACE: "Namespace",
        LSPSymbolKind.PACKAGE: "Package",
        LSPSymbolKind.CLASS: "Class",
        LSPSymbolKind.METHOD: "Method",
        LSPSymbolKind.PROPERTY: "Property",
        LSPSymbolKind.FIELD: "Field",
        LSPSymbolKind.CONSTRUCTOR: "Constructor",
        LSPSymbolKind.ENUM: "Enum",
        LSPSymbolKind.INTERFACE: "Interface",
        LSPSymbolKind.FUNCTION: "Function",
        LSPSymbolKind.VARIABLE: "Variable",
        LSPSymbolKind.CONSTANT: "Constant",
    }

    return kind_map.get(kind, "Unknown")


def swift_get_symbols_overview(file_path: str) -> dict[str, Any]:
    """Extract only top-level symbols (classes, structs, enums, protocols) from a Swift file.

    Returns token-optimized format showing only root-level type declarations.

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        SymbolsOverviewResponse as dict with success status, top-level symbols, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return SymbolsOverviewResponse(
            success=False,
            file_path=file_path,
            top_level_symbols=[],
            symbol_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return SymbolsOverviewResponse(
            success=False,
            file_path=file_path,
            top_level_symbols=[],
            symbol_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    try:
        # Find Swift project root for proper LSP initialization
        project_root = find_swift_project_root(file_path)

        # Initialize LSP client with project root and longer timeout for indexing
        with managed_lsp_client(project_root=project_root, timeout=LSPTimeouts.DEFAULT) as client:
            analyzer = FileAnalyzer(client)
            result_dict = analyzer.analyze_file_symbols(file_path)

            if result_dict["success"]:
                if result_dict["symbols"]:
                    top_level_symbols = _extract_top_level_symbols(result_dict["symbols"])

                    # Convert to SwiftSymbolInfo objects
                    symbol_infos = []
                    for symbol in top_level_symbols:
                        # Convert to SwiftSymbolInfo format
                        # Convert LSP symbol kind integer to string
                        symbol_kind_int = symbol.get("kind", 1)  # Default to FILE
                        symbol_kind_str = _convert_lsp_symbol_kind_to_string(symbol_kind_int)

                        symbol_info = SwiftSymbolInfo(
                            name=symbol["name"],
                            kind=SymbolKind(symbol_kind_str),
                            line=symbol.get("line", 1),
                            character=symbol.get("character", 0),
                            children=[],  # Top-level symbols don't need children for overview
                        )
                        symbol_infos.append(symbol_info)

                    return SymbolsOverviewResponse(
                        success=True,
                        file_path=file_path,
                        top_level_symbols=symbol_infos,
                        symbol_count=len(symbol_infos),
                    ).model_dump()
                else:
                    return SymbolsOverviewResponse(
                        success=True,
                        file_path=file_path,
                        top_level_symbols=[],
                        symbol_count=0,
                    ).model_dump()
            else:
                return SymbolsOverviewResponse(
                    success=False,
                    file_path=file_path,
                    top_level_symbols=[],
                    symbol_count=0,
                    error=result_dict.get("error_message", "LSP operation failed"),
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except TimeoutError as e:
        # Specific handling for timeout errors - these are usually LSP environment issues
        error_msg = f"lsp_error - {str(e)}"
        return SymbolsOverviewResponse(
            success=False,
            file_path=file_path,
            top_level_symbols=[],
            symbol_count=0,
            error=error_msg,
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()

    except RuntimeError as e:
        # Runtime errors often indicate LSP client issues
        error_msg = str(e)
        if any(
            keyword in error_msg.lower() for keyword in ["lsp", "sourcekit", "generator", "timeout"]
        ):
            # LSP-related runtime error
            error_msg = f"lsp_error - {error_msg}"
            error_type = ErrorType.LSP_ERROR
        else:
            # Generic runtime error
            error_type = ErrorType.TOOL_ERROR

        return SymbolsOverviewResponse(
            success=False,
            file_path=file_path,
            top_level_symbols=[],
            symbol_count=0,
            error=error_msg,
            error_type=error_type,
        ).model_dump()

    except Exception as e:
        # Catch-all for other exceptions with improved classification
        error_msg = str(e)

        # Check for generator-related errors
        if "generator" in error_msg.lower():
            error_msg = f"lsp_error - generator error: {error_msg}"
            error_type = ErrorType.LSP_ERROR
        # Check for other LSP-related errors
        elif any(
            keyword in error_msg.lower() for keyword in ["lsp", "sourcekit", "timeout", "pipe"]
        ):
            error_msg = f"lsp_error - {error_msg}"
            error_type = ErrorType.LSP_ERROR
        else:
            # Generic tool error
            error_type = ErrorType.TOOL_ERROR

        return SymbolsOverviewResponse(
            success=False,
            file_path=file_path,
            top_level_symbols=[],
            symbol_count=0,
            error=error_msg,
            error_type=error_type,
        ).model_dump()


def _extract_top_level_symbols(symbols: list) -> list:
    """Filter symbols to extract only top-level type declarations.

    Top-level symbols are those at depth 0 that represent type declarations:
    - Classes
    - Structs
    - Enums
    - Protocols (Interfaces)
    - Extensions (if present)

    Excludes:
    - Functions at file level
    - Variables/Constants at file level
    - Imports
    - Other non-type symbols

    Args:
        symbols: List of symbol dictionaries from FileAnalyzer

    Returns:
        Filtered list containing only top-level type symbols
    """
    top_level_types = []

    # Symbol kinds that represent type declarations
    TYPE_SYMBOL_KINDS = {
        "Class",
        "Struct",
        "Enum",
        "Interface",
        "Protocol",
        "Extension",  # Extension might appear as different kind
    }

    for symbol in symbols:
        kind_name = symbol.get("kind_name", "")

        # Only include symbols that are type declarations
        if kind_name in TYPE_SYMBOL_KINDS:
            top_level_types.append(symbol)

    return top_level_types
