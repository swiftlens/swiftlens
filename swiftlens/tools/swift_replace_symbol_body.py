"""Tool for replacing the body content of a specific Swift symbol.

Provides precise symbol body replacement using SourceKit-LSP for accurate boundary detection
and atomic file operations to safely replace symbol bodies while preserving declarations.
"""

from pathlib import Path

from lsp.managed_client import find_swift_project_root, managed_lsp_client
from lsp.operations.symbol_position import SymbolPositionOperation
from lsp.timeouts import LSPTimeouts

from swiftlens.model.models import ErrorType, OperationType, ReplaceOperationResponse
from swiftlens.utils.file_operations import SwiftFileModifier
from swiftlens.utils.validation import validate_swift_file_path_for_writing

# File validation is now handled by shared utility in utils.validation


def swift_replace_symbol_body(file_path, symbol_name, new_body):
    """Replace the body content of a specified Swift symbol while preserving the declaration.

    Uses SourceKit-LSP for precise symbol boundary detection and atomic file operations
    to safely replace symbol bodies with sophisticated brace matching for Swift syntax.

    Args:
        file_path: Path to the Swift file to modify
        symbol_name: Name of the symbol to replace body for (supports dotted paths like "Class.method")
        new_body: New body content to replace the existing body with

    Returns:
        ReplaceOperationResponse as dict with success status, operation details, and metadata
    """

    # Validate and sanitize the file path using shared utility
    is_valid, validated_path, error_msg = validate_swift_file_path_for_writing(file_path)
    if not is_valid:
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error=error_msg,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Use the validated path for all subsequent operations
    file_path = validated_path

    # Validate symbol name
    if not symbol_name or not isinstance(symbol_name, str):
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error="Symbol name must be a non-empty string",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if len(symbol_name) > 200:
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error="Symbol name too long",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Validate new body content
    if not isinstance(new_body, str):
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error="Body content must be a string",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not new_body.strip():
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error="Body content must be a non-empty string",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    try:
        # Use atomic file operations to safely read file and replace symbol body
        with SwiftFileModifier(file_path) as modifier:
            # Read file content safely
            file_content = modifier._read_file_content()

            # Initialize LSP client with resource limits and symbol positioning
            # Find Swift project root for proper LSP initialization
            project_root = find_swift_project_root(file_path)
            if project_root is None:
                # Fallback for test environments or isolated files - use file's directory
                # This handles cases where Swift files are in temporary directories during testing
                import os

                project_root = os.path.dirname(os.path.abspath(file_path))

            with managed_lsp_client(
                project_root=project_root,
                timeout=LSPTimeouts.DEFAULT,
            ) as client:
                symbol_position_op = SymbolPositionOperation(client)

                # Convert file path to URI safely
                file_uri = Path(file_path).as_uri()

                # Normalize symbol name by removing parentheses for functions/methods
                # This allows users to specify either "functionName" or "functionName()"
                normalized_symbol_name = symbol_name.replace("()", "")

                # Find the symbol and get body boundaries using safe file content
                body_boundaries = symbol_position_op.calculate_body_boundaries(
                    file_uri, normalized_symbol_name, file_content
                )

                if not body_boundaries:
                    # Check for multiple symbols with the same name
                    insertion_points = symbol_position_op.find_multiple_symbols(
                        file_uri, normalized_symbol_name
                    )

                    if insertion_points:
                        # Multiple symbols found - provide disambiguation
                        symbol_list = []
                        for symbol_info in insertion_points:
                            disambiguation = (
                                symbol_info.disambiguation_info or symbol_info.symbol_name
                            )
                            symbol_list.append(f"{disambiguation} ({symbol_info.symbol_kind})")

                        symbols_str = ", ".join(symbol_list)
                        return ReplaceOperationResponse(
                            success=False,
                            file_path=file_path,
                            symbol_name=symbol_name,
                            operation=OperationType.REPLACE_BODY,
                            lines_removed=0,
                            lines_added=0,
                            start_line=1,
                            end_line=1,
                            error=f"Multiple symbols found: {symbols_str}",
                            error_type=ErrorType.SYMBOL_AMBIGUOUS,
                        ).model_dump()
                    else:
                        return ReplaceOperationResponse(
                            success=False,
                            file_path=file_path,
                            symbol_name=symbol_name,
                            operation=OperationType.REPLACE_BODY,
                            lines_removed=0,
                            lines_added=0,
                            start_line=1,
                            end_line=1,
                            error=f"Symbol not found or has no replaceable body: {symbol_name}",
                            error_type=ErrorType.SYMBOL_NOT_FOUND,
                        ).model_dump()

                # Replace symbol body
                result = modifier.replace_symbol_body(
                    body_boundaries.body_start_line,
                    body_boundaries.body_end_line,
                    new_body,
                    preserve_indentation=True,
                    body_start_char=body_boundaries.body_start_char,
                    body_end_char=body_boundaries.body_end_char,
                )

                if result.success:
                    # Calculate lines for the response
                    lines_removed = (
                        body_boundaries.body_end_line - body_boundaries.body_start_line + 1
                    )
                    lines_added = len(new_body.split("\n"))

                    return ReplaceOperationResponse(
                        success=True,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        operation=OperationType.REPLACE_BODY,
                        lines_removed=lines_removed,
                        lines_added=lines_added,
                        start_line=body_boundaries.body_start_line,
                        end_line=body_boundaries.body_end_line,
                    ).model_dump()
                else:
                    return ReplaceOperationResponse(
                        success=False,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        operation=OperationType.REPLACE_BODY,
                        lines_removed=0,
                        lines_added=0,
                        start_line=1,
                        end_line=1,
                        error=result.message,
                        error_type=ErrorType.OPERATION_ERROR,
                    ).model_dump()

    except (OSError, ValueError, ConnectionError, TimeoutError, RuntimeError) as e:
        # Handle known errors gracefully (including LSP timeouts)
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
    except Exception:
        # Log unexpected errors for debugging while returning safe message
        # In production, this should use proper logging
        import traceback

        traceback.print_exc()
        return ReplaceOperationResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            operation=OperationType.REPLACE_BODY,
            lines_removed=0,
            lines_added=0,
            start_line=1,
            end_line=1,
            error="Unexpected error during symbol body replacement",
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()


# swift_replace_symbol_body_basic function removed to eliminate code duplication
# and ensure all tests use the production function with comprehensive validation
