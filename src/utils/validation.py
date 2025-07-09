"""
Shared validation utilities for Swift Context MCP tools.

Provides centralized file path validation with security checks, file size limits,
and consistent error handling across all tools.
"""

import os


def validate_swift_file_path(file_path: str, max_size_mb: int = 10) -> tuple[bool, str, str]:
    """Validate and sanitize Swift file path with comprehensive security checks.

    Provides centralized validation logic used across all Swift Context MCP tools
    to ensure consistent security, file size limits, and error handling.

    Args:
        file_path: Input file path to validate
        max_size_mb: Maximum file size in megabytes (default: 10MB)

    Returns:
        Tuple of (is_valid, sanitized_path, error_message)
        - is_valid: Boolean indicating if validation passed
        - sanitized_path: Absolute, resolved file path (empty string if invalid)
        - error_message: Token-optimized error description (empty string if valid)

    Example:
        >>> is_valid, path, error = validate_swift_file_path("file.swift")
        >>> if is_valid:
        ...     content = open(path).read()
        ... else:
        ...     return error
    """
    try:
        # Basic input validation
        if not file_path or not isinstance(file_path, str):
            return False, "", "Error: File path must be a non-empty string"

        # Prevent null byte injection attacks
        if "\0" in file_path:
            return False, "", "Error: Invalid file path"

        # Convert to absolute path and resolve symlinks to prevent traversal attacks
        try:
            abs_path = os.path.abspath(file_path)
            real_path = os.path.realpath(abs_path)
        except (OSError, ValueError):
            return False, "", f"Error: Invalid file path: {file_path}"

        # Validate path length to prevent buffer overflow attacks
        if len(real_path) > 4096:
            return False, "", "Error: File path too long"

        # Ensure file exists
        if not os.path.exists(real_path):
            return False, "", f"Error: File not found: {file_path}"

        # Ensure it's a regular file, not a directory or special file
        if not os.path.isfile(real_path):
            return False, "", f"Error: Not a regular file: {file_path}"

        # Validate Swift file extension
        if not real_path.endswith(".swift"):
            return False, "", f"Error: Not a Swift file: {file_path}"

        # Check file size limits to prevent memory exhaustion
        try:
            file_size = os.path.getsize(real_path)
            max_size_bytes = max_size_mb * 1024 * 1024
            if file_size > max_size_bytes:
                size_mb = file_size / (1024 * 1024)
                return (
                    False,
                    "",
                    f"Error: File too large: {size_mb:.1f}MB (limit: {max_size_mb}MB)",
                )
        except OSError:
            return False, "", f"Error: Cannot access file: {file_path}"

        # Check file permissions for read access
        if not os.access(real_path, os.R_OK):
            return False, "", f"Error: Cannot read file: {file_path}"

        return True, real_path, ""

    except Exception:
        # Catch any unexpected errors and return safe message
        return False, "", f"Error: File validation failed: {file_path}"


def validate_swift_file_path_for_writing(
    file_path: str, max_size_mb: int = 10
) -> tuple[bool, str, str]:
    """Validate Swift file path for write operations with additional permission checks.

    Similar to validate_swift_file_path but includes write permission validation
    for tools that modify files.

    Args:
        file_path: Input file path to validate
        max_size_mb: Maximum file size in megabytes (default: 10MB)

    Returns:
        Tuple of (is_valid, sanitized_path, error_message)
    """
    # First run standard validation
    is_valid, sanitized_path, error_message = validate_swift_file_path(file_path, max_size_mb)

    if not is_valid:
        return is_valid, sanitized_path, error_message

    # Additional write permission check
    if not os.access(sanitized_path, os.W_OK):
        return False, "", f"Error: Cannot write to file: {file_path}"

    return True, sanitized_path, ""


def validate_project_path(project_path: str) -> tuple[bool, str, str]:
    """Validate project directory path with security checks for swiftlens_initialize_project.

    Args:
        project_path: Input project directory path to validate

    Returns:
        Tuple of (is_valid, sanitized_path, error_message)
    """
    try:
        # Basic input validation
        if not project_path or not isinstance(project_path, str):
            return False, "", "Error: Project path must be a non-empty string"

        # Prevent null byte injection attacks
        if "\0" in project_path:
            return False, "", "Error: Invalid project path"

        # Convert to absolute path and resolve symlinks to prevent traversal attacks
        try:
            abs_path = os.path.abspath(project_path)
            real_path = os.path.realpath(abs_path)
        except (OSError, ValueError):
            return False, "", f"Error: Invalid project path: {project_path}"

        # Validate path length to prevent buffer overflow attacks
        if len(real_path) > 4096:
            return False, "", "Error: Project path too long"

        # Ensure directory exists
        if not os.path.exists(real_path):
            return False, "", f"Error: Project directory not found: {project_path}"

        # Ensure it's a directory, not a file
        if not os.path.isdir(real_path):
            return False, "", f"Error: Not a directory: {project_path}"

        # Check directory permissions for read access
        if not os.access(real_path, os.R_OK):
            return False, "", f"Error: Cannot read directory: {project_path}"

        # Check write permissions for creating config files
        if not os.access(real_path, os.W_OK):
            return False, "", f"Error: Cannot write to directory: {project_path}"

        return True, real_path, ""

    except Exception:
        # Catch any unexpected errors and return safe message
        return False, "", f"Error: Project path validation failed: {project_path}"


def validate_config_options(config_options: dict) -> tuple[bool, dict, str]:
    """Validate and sanitize configuration options for swiftlens_initialize_project.

    Args:
        config_options: Dictionary of configuration options to validate

    Returns:
        Tuple of (is_valid, sanitized_config, error_message)
    """
    try:
        if config_options is None:
            return True, {}, ""

        if not isinstance(config_options, dict):
            return False, {}, "Error: config_options must be a dictionary"

        sanitized = {}

        # Validate max_file_size
        if "max_file_size" in config_options:
            max_size = config_options["max_file_size"]
            if not isinstance(max_size, int) or max_size <= 0 or max_size > 100000:
                return (
                    False,
                    {},
                    "Error: max_file_size must be an integer between 1 and 100000",
                )
            sanitized["max_file_size"] = max_size

        # Validate enable_cross_file
        if "enable_cross_file" in config_options:
            cross_file = config_options["enable_cross_file"]
            if not isinstance(cross_file, bool):
                return False, {}, "Error: enable_cross_file must be a boolean"
            sanitized["enable_cross_file"] = cross_file

        # Validate auto_validate
        if "auto_validate" in config_options:
            auto_validate = config_options["auto_validate"]
            if not isinstance(auto_validate, bool):
                return False, {}, "Error: auto_validate must be a boolean"
            sanitized["auto_validate"] = auto_validate

        return True, sanitized, ""

    except Exception:
        return False, {}, "Error: Configuration validation failed"
