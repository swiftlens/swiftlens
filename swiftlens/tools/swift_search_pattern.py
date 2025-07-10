"""
Swift Search Pattern Tool

Find all regex/string matches in Swift file content with precise line/character positions
and optional context snippets. Token-optimized output for AI agents.
"""

import re
from typing import Any

from swiftlens.model.models import ErrorType, PatternMatch, PatternSearchResponse
from swiftlens.utils.validation import validate_swift_file_path

# File validation is now handled by shared utility in utils.validation


def _validate_pattern(pattern: str, is_regex: bool) -> tuple[bool, str]:
    """Validate search pattern.

    Args:
        pattern: Pattern to search for
        is_regex: Whether the pattern is a regex

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not pattern or not isinstance(pattern, str):
        return False, "Error: Pattern must be a non-empty string"

    if len(pattern) > 1000:
        return False, "Error: Pattern too long"

    # For regex patterns, validate by attempting to compile
    if is_regex:
        try:
            re.compile(pattern)
            return True, ""
        except re.error as e:
            return False, f"Error: Invalid regex pattern: {str(e)}"

    return True, ""


def _parse_flags(flags: str) -> tuple[int, str]:
    """Parse flags string into re module flags.

    Args:
        flags: String containing flags (i, m, s)

    Returns:
        Tuple of (compiled_flags, error_message)
    """
    if not isinstance(flags, str):
        return 0, "Error: Flags must be a string"

    compiled_flags = 0
    valid_flags = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}

    for flag in flags.lower():
        if flag not in valid_flags:
            return 0, f"Error: Invalid flag '{flag}'. Supported: i, m, s"
        compiled_flags |= valid_flags[flag]

    return compiled_flags, ""


def _get_line_number_and_char(content: str, match_start: int) -> tuple[int, int]:
    """Get line number and character position for a match.

    Args:
        content: Full file content
        match_start: Starting position of the match

    Returns:
        Tuple of (line_number, character_position) (both 1-based)
    """
    lines_before = content[:match_start].count("\n")
    line_number = lines_before + 1

    # Find start of current line
    line_start = content.rfind("\n", 0, match_start)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1

    character_position = match_start - line_start + 1
    return line_number, character_position


def _get_context_lines(
    content: str,
    match_start: int,
    match_end: int,
    context_lines: int,
    separator: str = "\n",
) -> str:
    """Get context lines around a match with configurable separator for token optimization.

    Args:
        content: Full file content
        match_start: Starting position of the match
        match_end: Ending position of the match
        context_lines: Number of lines before and after to include
        separator: String to join context lines (use "\\n" for token-optimized multi-line)

    Returns:
        Context string with the match and surrounding lines
    """
    if context_lines <= 0:
        # Just return the line containing the match
        line_start = content.rfind("\n", 0, match_start)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1

        line_end = content.find("\n", match_end)
        if line_end == -1:
            line_end = len(content)

        return content[line_start:line_end].strip()

    # Split content into lines
    lines = content.split("\n")
    total_lines = len(lines)

    # Find which line contains the match
    lines_before_match = content[:match_start].count("\n")
    match_line = lines_before_match

    # Calculate context range
    start_line = max(0, match_line - context_lines)
    end_line = min(total_lines - 1, match_line + context_lines)

    # Extract context lines and join with specified separator
    context_lines_list = lines[start_line : end_line + 1]
    return separator.join(context_lines_list)


def swift_search_pattern(
    file_path: str,
    pattern: str,
    is_regex: bool = True,
    flags: str = "",
    context_lines: int = 0,
) -> dict[str, Any]:
    """Find all regex/string matches in Swift file content with positions and context.

    Uses efficient pattern matching to find all occurrences and returns line/character
    positions with optional context snippets in token-optimized format.

    Includes file size limits (10MB), comprehensive security validation, and memory
    protection to prevent resource exhaustion attacks.

    Args:
        file_path: Path to the Swift file to search
        pattern: Regular expression or literal string to search for
        is_regex: Whether to treat pattern as regex (True) or literal string (False)
        flags: Optional regex flags - "i" (ignore case), "m" (multiline), "s" (dotall)
        context_lines: Number of lines before/after match to include (0 = match line only)

    Returns:
        PatternSearchResponse as dict with success status, matches list, and metadata

    Example:
        >>> swift_search_pattern(
        ...     "MyClass.swift",
        ...     pattern=r"func \\w+",
        ...     is_regex=True
        ... )
        {'success': True, 'matches': [{'line': 15, 'character': 5, 'snippet': 'func viewDidLoad()'}], ...}
    """
    # Validate and sanitize the file path using shared utility
    is_valid, validated_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error=error_msg,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Use the validated path for all subsequent operations
    file_path = validated_path

    # Validate pattern
    is_valid_pattern, pattern_error = _validate_pattern(pattern, is_regex)
    if not is_valid_pattern:
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error=pattern_error,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Validate context_lines parameter
    if not isinstance(context_lines, int) or context_lines < 0:
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error="context_lines must be a non-negative integer",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if context_lines > 50:
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error="context_lines too large (max 50)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Parse and validate flags
    compiled_flags, flags_error = _parse_flags(flags)
    if flags_error:
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error=flags_error,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    try:
        # Read file content safely
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Handle empty file
        if not content:
            return PatternSearchResponse(
                success=True,
                file_path=file_path,
                pattern=pattern,
                is_regex=is_regex,
                matches=[],
                match_count=0,
            ).model_dump()

        # Prepare search pattern
        if is_regex:
            try:
                pattern_obj = re.compile(pattern, compiled_flags)
            except re.error as e:
                return PatternSearchResponse(
                    success=False,
                    file_path=file_path,
                    pattern=pattern,
                    is_regex=is_regex,
                    matches=[],
                    match_count=0,
                    error=f"Regex compilation failed: {str(e)}",
                    error_type=ErrorType.VALIDATION_ERROR,
                ).model_dump()
        else:
            # For literal string search, escape special regex characters
            escaped_pattern = re.escape(pattern)
            pattern_obj = re.compile(escaped_pattern, compiled_flags)

        # Find all matches
        matches = list(pattern_obj.finditer(content))

        if not matches:
            return PatternSearchResponse(
                success=True,
                file_path=file_path,
                pattern=pattern,
                is_regex=is_regex,
                matches=[],
                match_count=0,
            ).model_dump()

        # Process matches and build results
        match_results = []
        for match in matches:
            match_start = match.start()
            match_end = match.end()

            # Get line and character position
            line_num, char_pos = _get_line_number_and_char(content, match_start)

            # Get context with token-optimized separator
            if context_lines > 0:
                context = _get_context_lines(content, match_start, match_end, context_lines, "\\n")
            else:
                context = _get_context_lines(content, match_start, match_end, 0)

            # Create PatternMatch object
            pattern_match = PatternMatch(
                line=line_num,
                character=char_pos,
                match_text=match.group(),
                context=context,
            )
            match_results.append(pattern_match)

        return PatternSearchResponse(
            success=True,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=match_results,
            match_count=len(match_results),
        ).model_dump()

    except (OSError, ValueError) as e:
        # Handle known errors gracefully
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error=str(e),
            error_type=ErrorType.OPERATION_ERROR,
        ).model_dump()
    except Exception:
        # Log unexpected errors for debugging while returning safe message
        import traceback

        traceback.print_exc()
        return PatternSearchResponse(
            success=False,
            file_path=file_path,
            pattern=pattern,
            is_regex=is_regex,
            matches=[],
            match_count=0,
            error="Unexpected error during pattern search",
            error_type=ErrorType.OPERATION_ERROR,
        ).model_dump()


# swift_search_pattern_basic function removed to eliminate code duplication
# and ensure all tests use the production function with comprehensive validation
