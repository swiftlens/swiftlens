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
    validate_config_options,
    validate_project_path,
    validate_swift_file_path,
    validate_swift_file_path_for_writing,
)

# Ensure cleanup on server shutdown
atexit.register(cleanup_manager)
atexit.register(stop_dashboard_server)

# Global LSP manager - initialized in main()
_lsp_manager = None

# Create the FastMCP server with instructions
server = FastMCP(
    name="Swift Context Server",
    instructions="""You are SwiftLens, an AI-powered Swift intelligence engine. Your purpose is to assist developers by providing deep, semantic understanding of Swift codebases, enabling efficient, accurate, and cost-effective development. You are integrated with a live Swift project via a suite of powerful, compiler-accurate tools.

### Core Operating Philosophy: Efficiency and Precision
Your primary directive is to operate with maximum efficiency, minimizing token usage while delivering precise, accurate results. You achieve this by avoiding broad file reads and using semantic tools strategically. Remember, every token saved is a win.

**Strategic Workflow for Analysis:**
1.  **Orient (High-Level Scan):** ALWAYS start with `swift_get_symbols_overview`. This gives you a low-cost architectural map of a file before committing to a full analysis.
2.  **Investigate (Targeted Exploration):** Use tools like `swift_find_symbol_references`, `swift_get_symbol_definition`, and `swift_get_hover_info` to trace relationships and gather specific details without reading entire files.
3.  **Analyze (Deep Dive):** Only use `swift_analyze_file` when a comprehensive, full-file symbol analysis is absolutely necessary for the task.
4.  **Present (Optimized Context):** When you need to present code context to the user or for your own reasoning, use `swift_format_context` to create a token-optimized representation.

### Code Modification Workflow
When asked to modify code, you must act as a careful and methodical Swift engineer.
1.  **Analyze & Plan:** Use your analysis tools to fully understand the context and potential impact of the change.
2.  **Propose & Confirm:** Clearly state your proposed changes to the user and await their confirmation before proceeding.
3.  **Execute with Precision:** Use the dedicated modification tools (`swift_insert_before_symbol`, `swift_replace_symbol_body`, etc.) to perform the changes surgically.
4.  **Verify:** **IMMEDIATELY** after any modification, run `swift_validate_file` on the affected file to ensure the changes are syntactically correct and compile.

### Your Knowledge Base
Your effectiveness depends on your deep knowledge of the Swift ecosystem:
-   **Language Fundamentals:** Swift's type system, protocols, generics, and memory management (ARC).
-   **Modern Concurrency:** `async/await`, Actors, and Structured Concurrency.
-   **Apple Frameworks:** Patterns in SwiftUI, UIKit, and Foundation.
-   **Project Structure:** Swift Package Manager (SPM) conventions.

You are an interactive partner. Ask clarifying questions, manage complex tasks in steps, and always prioritize safe, accurate, and efficient Swift development.
""",
)


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
@log_tool_execution("swift_format_context")
def swift_format_context(file_path: str) -> dict:
    """Analyze a Swift file and return formatted context string optimized for AI models."""
    # Validate file path for security
    is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    try:
        from .tools.swift_format_context import swift_format_context as format_func

        return format_func(sanitized_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Context formatting failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
@log_tool_execution("swift_check_environment")
def swift_check_environment() -> dict:
    """Check if Swift development environment is properly configured."""
    from .tools.swift_check_environment import swift_check_environment as check_func

    return check_func()


@server.tool()
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
@log_tool_execution("swift_find_symbol_references")
def swift_find_symbol_references(file_path: str, symbol_name: str) -> dict:
    """Find all references to a symbol in the given Swift file."""
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
        from .tools.swift_find_symbol_references import (
            swift_find_symbol_references as find_func,
        )

        return find_func(sanitized_path, symbol_name)
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
def swift_insert_before_symbol(file_path: str, symbol_name, content):
    """Insert code directly before a specified Swift symbol using LSP positioning."""
    # Validate file path for security (write operation)
    is_valid, sanitized_path, error_msg = validate_swift_file_path_for_writing(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate symbol_name and content parameters
    if not symbol_name or not isinstance(symbol_name, str):
        return {
            "success": False,
            "error": "symbol_name must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(content, str):
        return {
            "success": False,
            "error": "content must be a string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_insert_before_symbol import (
            swift_insert_before_symbol as insert_func,
        )

        return insert_func(sanitized_path, symbol_name, content)
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbol insertion failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def swift_insert_after_symbol(file_path: str, symbol_name, content):
    """Insert code directly after a specified Swift symbol using LSP positioning."""
    # Validate file path for security (write operation)
    is_valid, sanitized_path, error_msg = validate_swift_file_path_for_writing(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate symbol_name and content parameters
    if not symbol_name or not isinstance(symbol_name, str):
        return {
            "success": False,
            "error": "symbol_name must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(content, str):
        return {
            "success": False,
            "error": "content must be a string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_insert_after_symbol import (
            swift_insert_after_symbol as insert_func,
        )

        return insert_func(sanitized_path, symbol_name, content)
    except Exception as e:
        return {
            "success": False,
            "error": f"Symbol insertion failed: {str(e)}",
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
def swift_replace_regex(
    file_path: str, regex_pattern: str, replacement: str, flags: str = ""
) -> dict:
    """Apply regex replacements in Swift file content with atomic file operations."""
    # Validate file path for security (write operation)
    is_valid, sanitized_path, error_msg = validate_swift_file_path_for_writing(file_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate regex parameters
    if not regex_pattern or not isinstance(regex_pattern, str):
        return {
            "success": False,
            "error": "regex_pattern must be a non-empty string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(replacement, str):
        return {
            "success": False,
            "error": "replacement must be a string",
            "error_type": "VALIDATION_ERROR",
        }
    if not isinstance(flags, str):
        return {
            "success": False,
            "error": "flags must be a string",
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swift_replace_regex import swift_replace_regex as replace_func

        return replace_func(sanitized_path, regex_pattern, replacement, flags)
    except Exception as e:
        return {
            "success": False,
            "error": f"Regex replacement failed: {str(e)}",
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
def swiftlens_initialize_project(project_path: str = ".", config_options: dict = None) -> dict:
    """Initialize SwiftLens capabilities for an existing Swift project to enhance AI-assisted development.

    Args:
        project_path: Path to the existing Swift project (default: current directory)
        config_options: Optional configuration settings for SwiftLens setup

    Returns:
        JSON response with initialization status and project analysis
    """
    # Validate project path for security
    is_valid, sanitized_path, error_msg = validate_project_path(project_path)
    if not is_valid:
        return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}

    # Validate and sanitize config options
    is_config_valid, sanitized_config, config_error = validate_config_options(config_options)
    if not is_config_valid:
        return {
            "success": False,
            "error": config_error,
            "error_type": "VALIDATION_ERROR",
        }

    try:
        from .tools.swiftlens_initialize_project import (
            swiftlens_initialize_project as init_func,
        )

        return init_func(sanitized_path, sanitized_config)
    except Exception as e:
        return {
            "success": False,
            "error": f"Project initialization failed: {str(e)}",
            "error_type": "LSP_ERROR",
        }


@server.tool()
def get_tool_help(tool_name: str = None) -> dict:
    """Get concise help for Swift tools. Pass tool_name for specific help, or None for all tools."""
    from .tools.get_tool_help import get_tool_help as help_func

    return help_func(tool_name)


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
