"""Tool for formatting Swift context for AI models."""

import os
from typing import Any

from analysis.file_analyzer import FileAnalyzer
from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts
from model.models import ErrorType, FormattedContextResponse


def swift_format_context(file_path: str) -> dict[str, Any]:
    """Analyze a Swift file and return formatted context string optimized for AI models.

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        FormattedContextResponse as dict with success status, formatted context, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return FormattedContextResponse(
            success=False,
            file_path=file_path,
            formatted_context="",
            token_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return FormattedContextResponse(
            success=False,
            file_path=file_path,
            formatted_context="",
            token_count=0,
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

        if not result_dict["success"]:
            return FormattedContextResponse(
                success=False,
                file_path=file_path,
                formatted_context="",
                token_count=0,
                error=result_dict["error_message"],
                error_type=ErrorType.LSP_ERROR,
            ).model_dump()

        if not result_dict["symbols"]:
            formatted_context = "No symbols found"
            return FormattedContextResponse(
                success=True,
                file_path=file_path,
                formatted_context=formatted_context,
                token_count=_estimate_token_count(formatted_context),
            ).model_dump()

    except Exception as e:
        return FormattedContextResponse(
            success=False,
            file_path=file_path,
            formatted_context="",
            token_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()

    def format_symbol_tree(symbol, indent=0):
        indent_str = "  " * indent
        name = symbol["name"]
        kind_name = symbol["kind_name"]
        lines = [f"{indent_str}{name} ({kind_name})"]
        for child in symbol["children"]:
            lines.extend(format_symbol_tree(child, indent + 1))
        return lines

    output = []
    for symbol in result_dict["symbols"]:
        output.extend(format_symbol_tree(symbol))

    formatted_context = "\n".join(output)
    return FormattedContextResponse(
        success=True,
        file_path=file_path,
        formatted_context=formatted_context,
        token_count=_estimate_token_count(formatted_context),
    ).model_dump()


def _estimate_token_count(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    if not text:
        return 0
    # Rough approximation: ~4 characters per token on average
    return max(1, len(text) // 4)
