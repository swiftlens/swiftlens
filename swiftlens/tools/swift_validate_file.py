"""Tool for validating Swift files using swiftc type checking."""

from typing import Any

from swiftlens.compiler.error_parser import SwiftErrorParser
from swiftlens.compiler.swift_compiler_client import SwiftCompilerClient
from swiftlens.model.models import ErrorType, FileValidationResponse
from swiftlens.utils.validation import validate_swift_file_path

# File validation is now handled by shared utility in utils.validation


def swift_validate_file(
    file_path: str, use_project_context: bool = True, timeout: int = 30
) -> dict[str, Any]:
    """Validate a Swift file using swiftc type checking.

    Executes `swiftc -typecheck` on the specified Swift file and returns
    any compilation errors, warnings, or notes in a token-optimized format.

    Args:
        file_path: Path to the Swift file to validate
        use_project_context: Whether to attempt project-aware compilation
        timeout: Maximum time in seconds for compilation (default 30, max 60)

    Returns:
        FileValidationResponse as dict with success status, diagnostics, and metadata
    """

    # Validate and sanitize the file path using shared utility
    is_valid, validated_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return FileValidationResponse(
            success=False,
            file_path=file_path,
            validation_result=error_msg,
            has_errors=True,
            error_count=1,
            warning_count=0,
            error=error_msg,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Use the validated path for all subsequent operations
    file_path = validated_path

    try:
        # Initialize compiler client and parser
        client = SwiftCompilerClient(timeout=timeout)
        parser = SwiftErrorParser()

        # Execute type checking
        if use_project_context:
            success, stdout, stderr = client.typecheck_with_project_context(file_path)
        else:
            success, stdout, stderr = client.typecheck_file(file_path)

        # Handle execution failure
        if not success:
            return FileValidationResponse(
                success=False,
                file_path=file_path,
                validation_result=stderr,
                has_errors=True,
                error_count=1,
                warning_count=0,
                error=stderr,
                error_type=ErrorType.COMPILATION_ERROR,
            ).model_dump()

        # Parse diagnostics from stderr
        diagnostics = parser.parse_diagnostics(stderr, file_path)

        # Count diagnostic types
        error_count = sum(1 for d in diagnostics if d.type == "error")
        warning_count = sum(1 for d in diagnostics if d.type == "warning")

        # File has errors if error_count > 0 (warnings/notes are ok)
        has_errors = error_count > 0

        # Format the validation result (use existing parser format)
        formatted_result = parser.format_diagnostics(diagnostics, include_summary=True)

        return FileValidationResponse(
            success=True,
            file_path=file_path,
            validation_result=formatted_result,
            has_errors=has_errors,
            error_count=error_count,
            warning_count=warning_count,
        ).model_dump()

    except Exception as e:
        return FileValidationResponse(
            success=False,
            file_path=file_path,
            validation_result=str(e),
            has_errors=True,
            error_count=1,
            warning_count=0,
            error=str(e),
            error_type=ErrorType.COMPILATION_ERROR,
        ).model_dump()


def swift_validate_file_basic(file_path: str) -> dict[str, Any]:
    """Basic Swift file validation without project context.

    This is a simplified version that only does standalone file validation,
    useful when project context detection might cause issues.

    Args:
        file_path: Path to the Swift file to validate

    Returns:
        FileValidationResponse as dict with validation results
    """
    return swift_validate_file(file_path, use_project_context=False, timeout=20)


def swift_validate_file_fast(file_path: str) -> dict[str, Any]:
    """Fast Swift file validation with shorter timeout.

    Uses a 15-second timeout for quick validation checks.

    Args:
        file_path: Path to the Swift file to validate

    Returns:
        FileValidationResponse as dict with validation results
    """
    return swift_validate_file(file_path, use_project_context=True, timeout=15)
