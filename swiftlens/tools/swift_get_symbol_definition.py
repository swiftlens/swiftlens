"""Tool for finding the definition location of a specific symbol in a Swift file."""

import os
from typing import Any

from lsp.managed_client import find_swift_project_root, managed_lsp_client

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import ErrorType, SymbolDefinitionResponse


def swift_get_symbol_definition(file_path: str, symbol_name: str) -> dict[str, Any]:
    """Find the definition location for a symbol in the given Swift file.

    Args:
        file_path: Path to the Swift file to analyze
        symbol_name: Name of the symbol to find definition for

    Returns:
        SymbolDefinitionResponse as dict with success status, definitions, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return SymbolDefinitionResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            definitions=[],
            definition_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return SymbolDefinitionResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            definitions=[],
            definition_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    if not symbol_name.strip():
        return SymbolDefinitionResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            definitions=[],
            definition_count=0,
            error="Symbol name cannot be empty",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    try:
        # Find Swift project root for proper LSP initialization
        project_root = find_swift_project_root(file_path)

        # Note: IndexStoreDB path would be at project_root/.build/index if needed

        # Initialize LSP client with project root and proper timeout
        with managed_lsp_client(project_root=project_root, timeout=10.0) as client:
            analyzer = FileAnalyzer(client)
            result_dict = analyzer.get_symbol_definition(file_path, symbol_name)

            if result_dict["success"]:
                if result_dict["definitions"]:
                    # Convert definitions to the expected SymbolDefinition format
                    formatted_definitions = []
                    for definition in result_dict["definitions"]:
                        from swiftlens.model.models import SymbolDefinition

                        symbol_def = SymbolDefinition(
                            file_path=definition["file_path"],
                            line=definition["line"],
                            character=definition["character"],
                            context=definition.get("context", ""),
                        )
                        formatted_definitions.append(symbol_def)

                    return SymbolDefinitionResponse(
                        success=True,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        definitions=formatted_definitions,
                        definition_count=len(formatted_definitions),
                    ).model_dump()
                else:
                    return SymbolDefinitionResponse(
                        success=True,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        definitions=[],
                        definition_count=0,
                    ).model_dump()
            else:
                # LSP error
                return SymbolDefinitionResponse(
                    success=False,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    definitions=[],
                    definition_count=0,
                    error=result_dict.get("error_message", "LSP operation failed"),
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except Exception as e:
        return SymbolDefinitionResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            definitions=[],
            definition_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
