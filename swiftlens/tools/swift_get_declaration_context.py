"""Tool for getting fully-qualified declaration contexts of Swift symbols."""

import os
from typing import Any

from lsp.managed_client import find_swift_project_root, managed_lsp_client

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.analysis.symbol_analyzer import SymbolAnalyzer
from swiftlens.model.models import DeclarationContextResponse, ErrorType


def swift_get_declaration_context(file_path: str) -> dict[str, Any]:
    """Get fully-qualified declaration contexts for all symbols in a Swift file.

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        DeclarationContextResponse as dict with success status, contexts, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return DeclarationContextResponse(
            success=False,
            file_path=file_path,
            declarations=[],
            declaration_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return DeclarationContextResponse(
            success=False,
            file_path=file_path,
            declarations=[],
            declaration_count=0,
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
                if result_dict["symbols"]:
                    contexts = SymbolAnalyzer.get_all_declaration_contexts(result_dict["symbols"])
                    contexts.sort(key=lambda x: x["qualified_name"])

                    # Convert to string format for JSON response (matching original output)
                    formatted_declarations = []
                    for context in contexts:
                        qualified_name = context["qualified_name"]
                        kind_name = context["kind_name"]
                        formatted_declarations.append(f"{qualified_name} ({kind_name})")

                    return DeclarationContextResponse(
                        success=True,
                        file_path=file_path,
                        declarations=formatted_declarations,
                        declaration_count=len(formatted_declarations),
                    ).model_dump()
                else:
                    return DeclarationContextResponse(
                        success=True,
                        file_path=file_path,
                        declarations=[],
                        declaration_count=0,
                    ).model_dump()
            else:
                return DeclarationContextResponse(
                    success=False,
                    file_path=file_path,
                    declarations=[],
                    declaration_count=0,
                    error=result_dict.get("error_message", "LSP operation failed"),
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except Exception as e:
        return DeclarationContextResponse(
            success=False,
            file_path=file_path,
            declarations=[],
            declaration_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
