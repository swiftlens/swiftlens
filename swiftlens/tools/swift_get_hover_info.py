"""Tool for getting hover information for a symbol at a specific position in a Swift file."""

import os
from typing import Any

from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.timeouts import LSPTimeouts

from swiftlens.analysis.file_analyzer import FileAnalyzer
from swiftlens.model.models import ErrorType, HoverInfoResponse


def swift_get_hover_info(file_path: str, line: int, character: int) -> dict[str, Any]:
    """Get hover information for a symbol at the specified position in a Swift file.

    Args:
        file_path: Path to the Swift file to analyze
        line: Line number (1-based)
        character: Character position (1-based)

    Returns:
        HoverInfoResponse as dict with success status, hover info, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return HoverInfoResponse(
            success=False,
            file_path=file_path,
            line=line,
            character=character,
            hover_info=None,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return HoverInfoResponse(
            success=False,
            file_path=file_path,
            line=line,
            character=character,
            hover_info=None,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    if line < 1:
        return HoverInfoResponse(
            success=False,
            file_path=file_path,
            line=line,
            character=character,
            hover_info=None,
            error="Line number must be 1-based (>= 1)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if character < 0:
        return HoverInfoResponse(
            success=False,
            file_path=file_path,
            line=line,
            character=character,
            hover_info=None,
            error="Character position must be 0-based (>= 0)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    try:
        # Find Swift project root for proper LSP initialization
        project_root = find_swift_project_root(file_path)

        # Initialize LSP client with project root and longer timeout for indexing
        with managed_lsp_client(
            project_root=project_root, timeout=LSPTimeouts.QUICK_OPERATION
        ) as client:
            analyzer = FileAnalyzer(client)
            result_dict = analyzer.get_hover_info(file_path, line, character)

            # Return structured JSON response
            if result_dict["success"]:
                return HoverInfoResponse(
                    success=True,
                    file_path=file_path,
                    line=line,
                    character=character,
                    hover_info=result_dict["hover_info"],
                ).model_dump()
            else:
                return HoverInfoResponse(
                    success=False,
                    file_path=file_path,
                    line=line,
                    character=character,
                    hover_info=None,
                    error=result_dict.get("error_message", "LSP operation failed"),
                    error_type=ErrorType.LSP_ERROR,
                ).model_dump()

    except Exception as e:
        return HoverInfoResponse(
            success=False,
            file_path=file_path,
            line=line,
            character=character,
            hover_info=None,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
