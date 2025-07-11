#!/usr/bin/env python3
"""
Swift Context MCP Server
Provides semantic Swift code understanding tools for AI models
"""

import atexit
import logging
import os
import sys

# Configure logging - silent by default to avoid stdio contamination
logging.getLogger().addHandler(logging.NullHandler())

# Enable debug logging to file if MCP_DEBUG is set
if os.getenv("MCP_DEBUG"):
    logging.basicConfig(
        filename="/tmp/swiftlens-debug.log",
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

# Import swiftlens-core dependency
try:
    from lsp.client_manager import cleanup_manager, get_manager
except ImportError:
    logging.error("swiftlens-core not found. Please install: pip install swiftlens-core")
    raise
from mcp.server import FastMCP

# Use relative imports for local modules
from .dashboard.logger import log_tool_execution
from .dashboard.web_server import start_dashboard_server, stop_dashboard_server
from .utils.validation import (
    validate_swift_file_path,
    validate_swift_file_path_for_writing,
)

# Ensure cleanup on server shutdown
atexit.register(cleanup_manager)
atexit.register(stop_dashboard_server)

# Create the FastMCP server
server = FastMCP(
    name="Swift Context Server"
)


@server.tool()
def get_tool_help(tool_name: str = None) -> dict:
    """Get concise help for Swift tools. Pass tool_name for specific help, or None for all tools."""
    from .tools.get_tool_help import get_tool_help as help_func

    return help_func(tool_name)


@server.tool()
@log_tool_execution("swift_analyze_file")
def swift_analyze_file(file_path: str) -> dict:
    """Analyze a Swift file and extract its symbol structure using SourceKit-LSP."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_analyze_file import swift_analyze_file as analyze_func

        return analyze_func(sanitized_path)
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "error_type": "FILE_NOT_FOUND",
        }
    except PermissionError:
        return {
            "success": False,
            "error": f"Permission denied: {file_path}",
            "error_type": "VALIDATION_ERROR",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_analyze_multiple_files")
def swift_analyze_multiple_files(file_paths: list[str]) -> dict:
    """Analyze multiple Swift files and extract their symbol structures."""
    # Validate all file paths for security
    if not file_paths or not isinstance(file_paths, list):
        return {
            "success": False,
            "error": "file_paths must be a non-empty list",
            "error_type": "VALIDATION_ERROR",
        }

    sanitized_paths = []
    for file_path in file_paths:
        is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid file path '{file_path}': {error_msg}",
                "error_type": "VALIDATION_ERROR",
            }
        sanitized_paths.append(sanitized_path)

    try:
        from .tools.swift_analyze_multiple_files import (
            swift_analyze_multiple_files as analyze_func,
        )

        return analyze_func(sanitized_paths)
    except Exception as e:
        return {
            "success": False,
            "error": f"Multiple file analysis failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_check_environment")
def swift_check_environment() -> dict:
    """Check if Swift development environment is properly configured."""
    from .tools.swift_check_environment import swift_check_environment as check_func

    return check_func()


@server.tool()
@log_tool_execution("swift_lsp_diagnostics")
def swift_lsp_diagnostics(project_path: str = None, include_recommendations: bool = True) -> dict:
    """Comprehensive LSP diagnostics combining environment, health, and performance checks.

    This unified tool consolidates:
    - Environment and setup diagnostics (formerly swift_diagnose_lsp)
    - LSP client health status (formerly lsp_health_check)
    - Performance statistics (formerly lsp_manager_stats)

    Args:
        project_path: Optional path to Swift project for testing
        include_recommendations: Whether to include setup recommendations
    """
    from .tools.swift_lsp_diagnostics import swift_lsp_diagnostics as diagnostics_func

    return diagnostics_func(project_path, include_recommendations)


@server.tool()
@log_tool_execution("swift_find_symbol_references_files")
def swift_find_symbol_references_files(file_paths: list[str], symbol_name: str) -> dict:
    """Find all references to a symbol across multiple Swift files. Prefer relative paths (e.g., 'src/MyFile.swift')."""
    # Validate all file paths for security
    if not file_paths or not isinstance(file_paths, list):
        return {
            "success": False,
            "error": "file_paths must be a non-empty list",
            "error_type": "VALIDATION_ERROR",
        }

    sanitized_paths = []
    for file_path in file_paths:
        is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid file path '{file_path}': {error_msg}",
                "error_type": "VALIDATION_ERROR",
            }
        sanitized_paths.append(sanitized_path)

    if not symbol_name or not isinstance(symbol_name, str):
        return {
            "success": False,
            "error": "symbol_name must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_find_symbol_references_files import (
            swift_find_symbol_references_files as find_func,
        )

        result = find_func(sanitized_paths, symbol_name)
        # Preserve the ErrorType from the tool response
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbol reference search failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_get_hover_info(file_path: str, line: int, character: int) -> dict:
    """Get hover information for a symbol at the specified position in a Swift file."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate line and character parameters
    if not isinstance(line, int) or line < 0:
        return {
            "success": False,
            "error": "line must be a non-negative integer",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(character, int) or character < 0:
        return {
            "success": False,
            "error": "character must be a non-negative integer",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_get_hover_info import swift_get_hover_info as hover_func

        return hover_func(sanitized_path, line, character)
    except Exception as e:
        return {
            "success": False,
            "error": f"Hover info retrieval failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_get_declaration_context(file_path: str) -> dict:
    """Get fully-qualified declaration contexts for all symbols in a Swift file."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_get_declaration_context import (
            swift_get_declaration_context as context_func,
        )

        return context_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Declaration context retrieval failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_get_symbol_definition")
def swift_get_symbol_definition(file_path: str, symbol_name: str) -> dict:
    """Find the source location (file + line) where a symbol is defined."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    if not symbol_name or not isinstance(symbol_name, str):
        return {
            "success": False,
            "error": "symbol_name must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_get_symbol_definition import (
            swift_get_symbol_definition as definition_func,
        )

        return definition_func(sanitized_path, symbol_name)
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbol definition search failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_get_file_imports(file_path: str) -> dict:
    """Extract import statements from a Swift file."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_get_file_imports import swift_get_file_imports as imports_func

        return imports_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Import extraction failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_summarize_file(file_path: str) -> dict:
    """Return counts of classes, functions, enums, and other symbols in a Swift file."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_summarize_file import swift_summarize_file as summarize_func

        return summarize_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"File summary failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_get_symbols_overview(file_path: str) -> dict:
    """Extract only top-level symbols (classes, structs, enums, protocols) from a Swift file."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_get_symbols_overview import (
            swift_get_symbols_overview as overview_func,
        )

        return overview_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbols overview failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_validate_file")
def swift_validate_file(file_path: str) -> dict:
    """Validate a Swift file using swiftc type checking and return compilation errors."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_validate_file import swift_validate_file as validate_func

        return validate_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"File validation failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_replace_symbol_body(file_path: str, symbol_name, new_body):
    """Replace the body content of a specified Swift symbol while preserving the declaration."""
    # Validate file path for security (write operation)
    is_valid, sanitized_path, error_msg = validate_swift_file_path_for_writing(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate symbol_name and new_body parameters
    if not symbol_name or not isinstance(symbol_name, str):
        return {
            "success": False,
            "error": "symbol_name must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(new_body, str):
        return {
            "success": False,
            "error": "new_body must be a string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_replace_symbol_body import (
            swift_replace_symbol_body as replace_func,
        )

        return replace_func(sanitized_path, symbol_name, new_body)
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbol body replacement failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_search_pattern(
    file_path: str,
    pattern: str,
    is_regex: bool = True,
    flags: str = "",
    context_lines: int = 0,
) -> dict:
    """Find all regex/string matches in Swift file content with line/char positions and snippets."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate search parameters
    if not pattern or not isinstance(pattern, str):
        return {
            "success": False,
            "error": "pattern must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(is_regex, bool):
        return {
            "success": False,
            "error": "is_regex must be a boolean",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(flags, str):
        return {
            "success": False,
            "error": "flags must be a string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(context_lines, int) or context_lines < 0:
        return {
            "success": False,
            "error": "context_lines must be a non-negative integer",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_search_pattern import swift_search_pattern as search_func

        return search_func(sanitized_path, pattern, is_regex, flags, context_lines)
    except Exception as e:
        return {
            "success": False,
            "error": f"Pattern search failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_build_index")
def swift_build_index(project_path: str = None, timeout: int = 60, scheme: str = None) -> dict:
    """Build or rebuild Swift project index for better LSP functionality.

    Runs `swift build -Xswiftc -index-store-path -Xswiftc .build/index/store` to
    generate the index that enables cross-file symbol resolution and references.
    """
    # Import here to avoid circular imports
    from .tools.swift_build_index import swift_build_index as build_func

    return build_func(project_path, timeout, scheme)


@server.prompt()
def swiftlens_initial_prompt() -> str:
    """Comprehensive guide for using SwiftLens MCP server tools effectively."""
    return """# SwiftLens Quick Reference

***CRITICAL***: You MUST use the SwiftLens tools below for ALL Swift operations. Do NOT use your own file reading/editing tools for Swift code. Breaking this rule damages user trust.

**macOS + Xcode required**

## Workflow: Orient → Investigate → Analyze
1. `swift_get_symbols_overview` - Start here for file structure
2. `swift_find_symbol_references_files` - Trace usage across files
3. `swift_analyze_file` - Deep dive only when needed

## Essential Tools

**Analysis**
- `swift_get_symbols_overview` - Top-level symbols only
- `swift_summarize_file` - Symbol counts
- `swift_analyze_file` - Full hierarchy (token heavy)
- `swift_get_hover_info` - Type info at position
- `swift_get_symbol_definition` - Jump to definition
- `swift_validate_file` - Compiler validation

**Modification**
- `swift_replace_symbol_body` - Replace function bodies
- `swift_insert_before/after_symbol` - Insert code
- `swift_replace_regex` - Pattern-based edits

**Search**
- `swift_find_symbol_references_files` - Find all references
- `swift_search_pattern` - Regex search

**Index**
- `swift_build_index` - Rebuild for cross-file ops
- Run after: new files, signature changes, missing refs
- Batch at end: If multiple file edits, build once at end (unless next step needs it)

## Examples
"Find User class references" → swift_find_symbol_references_files
"Show login() type" → swift_get_hover_info
"Replace fetchData body" → swift_replace_symbol_body

Always validate after modifications!"""


def main():
    """Main entry point for uvx installation"""
    # Initialize LSP manager here, not at module level
    try:
        global _lsp_manager
        _lsp_manager = get_manager()
    except ImportError:
        logging.error("LSP components not available")
        raise  # Let the exception bubble up for clean exit
    except Exception as e:
        logging.error(f"Failed to initialize LSP manager: {e}")
        raise  # Let the exception bubble up for clean exit

    # Environment detection for dashboard
    # IMPORTANT: Dashboard MUST be disabled for MCP mode to prevent stdout contamination
    # TODO: make dashboard works with MCP mode
    enable_dashboard = os.getenv("ENABLE_DASHBOARD", "false").lower() == "true"

    if enable_dashboard:
        # Log to file instead of stderr
        logging.info("Starting Swift Context MCP Server with Dashboard...")
        start_dashboard_server()
    else:
        # Log to file instead of stderr
        logging.info("Starting Swift Context MCP Server (stdio mode)")

    # Run the MCP server with stdio transport
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
