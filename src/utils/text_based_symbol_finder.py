"""Text-based symbol finding fallback when LSP is unavailable or symbols aren't indexed."""

import re
from dataclasses import dataclass


@dataclass
class TextBasedSymbolInfo:
    """Symbol information found through text parsing."""

    symbol_name: str
    symbol_type: str  # class, struct, func, etc.
    start_line: int  # 1-based
    end_line: int  # 1-based
    indentation: str


def find_symbol_text_based(file_content: str, symbol_name: str) -> TextBasedSymbolInfo | None:
    """Find symbol using text-based parsing as LSP fallback.

    Args:
        file_content: Content of the Swift file
        symbol_name: Name of symbol to find

    Returns:
        TextBasedSymbolInfo if found, None otherwise
    """
    lines = file_content.split("\n")

    # Patterns for Swift symbols
    patterns = [
        (
            r"^\s*(class|struct|enum|protocol)\s+" + re.escape(symbol_name) + r"\b",
            "type",
        ),
        (r"^\s*func\s+" + re.escape(symbol_name) + r"\b", "func"),
        (r"^\s*(var|let)\s+" + re.escape(symbol_name) + r"\b", "property"),
        (
            r"^\s*init\s*\(" if symbol_name == "init" else r"^\s*init\s+" + re.escape(symbol_name),
            "init",
        ),
    ]

    for line_idx, line in enumerate(lines):
        for pattern, symbol_type in patterns:
            match = re.search(pattern, line)
            if match:
                # Found the symbol, now find its boundaries
                indentation = _get_line_indentation(line)
                start_line = line_idx + 1  # Convert to 1-based

                # Find the end of this symbol
                if symbol_type == "type":
                    end_line = _find_type_end_line(lines, line_idx, indentation)
                elif symbol_type == "func":
                    end_line = _find_function_end_line(lines, line_idx, indentation)
                else:
                    end_line = _find_simple_symbol_end_line(lines, line_idx, indentation)

                return TextBasedSymbolInfo(
                    symbol_name=symbol_name,
                    symbol_type=symbol_type,
                    start_line=start_line,
                    end_line=end_line,
                    indentation=indentation,
                )

    return None


def _get_line_indentation(line: str) -> str:
    """Get the indentation (whitespace prefix) of a line."""
    match = re.match(r"^(\s*)", line)
    return match.group(1) if match else ""


def _find_type_end_line(lines: list[str], start_line_idx: int, base_indentation: str) -> int:
    """Find the end line of a type (class, struct, enum) by finding matching brace."""
    brace_count = 0
    in_string = False

    for line_idx in range(start_line_idx, len(lines)):
        line = lines[line_idx]

        # Skip string content
        for char in line:
            if char == '"' and not in_string:
                in_string = True
            elif char == '"' and in_string:
                in_string = False
            elif not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        return line_idx + 1  # Convert to 1-based

    # If no closing brace found, return the last line
    return len(lines)


def _find_function_end_line(lines: list[str], start_line_idx: int, base_indentation: str) -> int:
    """Find the end line of a function."""
    # Check if it's a single-line function
    start_line = lines[start_line_idx]
    if "{" in start_line and "}" in start_line:
        return start_line_idx + 1  # Single line function

    # Multi-line function - find matching brace
    return _find_type_end_line(lines, start_line_idx, base_indentation)


def _find_simple_symbol_end_line(
    lines: list[str], start_line_idx: int, base_indentation: str
) -> int:
    """Find the end line of a simple symbol (property, etc)."""
    start_line = lines[start_line_idx]

    # If it's a single line, return it
    if start_line.strip().endswith(";") or "=" in start_line:
        return start_line_idx + 1

    # Multi-line property with getter/setter
    return _find_type_end_line(lines, start_line_idx, base_indentation)


def get_text_based_insertion_points(file_content: str, symbol_name: str) -> tuple[int, int] | None:
    """Get insertion points (before_line, after_line) using text-based parsing.

    Args:
        file_content: Content of the Swift file
        symbol_name: Name of symbol to find

    Returns:
        Tuple of (before_line, after_line) in 1-based indexing, or None if not found
    """
    symbol_info = find_symbol_text_based(file_content, symbol_name)
    if not symbol_info:
        return None

    return symbol_info.start_line, symbol_info.end_line
