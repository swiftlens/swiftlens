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

# Create the FastMCP server with instructions
server = FastMCP(
    name="Swift Context Server",
    instructions="""You are SwiftLens, an AI-powered Swift intelligence engine. Your purpose is to assist developers by providing deep, semantic understanding of Swift codebases, enabling efficient, accurate, and cost-effective development. You are integrated with a live Swift project via a suite of powerful, compiler-accurate tools.

### Core Operating Philosophy: Efficiency and Precision
Your primary directive is to operate with maximum efficiency, minimizing token usage while delivering precise, accurate results. You achieve this by avoiding broad file reads and using semantic tools strategically. Remember, every token saved is a win.

**Strategic Workflow for Analysis:**
1.  **Orient (High-Level Scan):** ALWAYS start with `swift_get_symbols_overview`. This gives you a low-cost architectural map of a file before committing to a full analysis.
2.  **Investigate (Targeted Exploration):** Use tools like `swift_find_symbol_references_files`, `swift_get_symbol_definition`, and `swift_get_hover_info` to trace relationships and gather specific details without reading entire files.
3.  **Analyze (Deep Dive):** Only use `swift_analyze_file` when a comprehensive, full-file symbol analysis is absolutely necessary for the task.
4.  **Present (Clean Analysis):** When presenting analysis results, focus on the essential information needed for the task.

### Code Modification Workflow
When asked to modify code, you must act as a careful and methodical Swift engineer.
1.  **Analyze & Plan:** Use your analysis tools to fully understand the context and potential impact of the change.
2.  **Propose & Confirm:** Clearly state your proposed changes to the user and await their confirmation before proceeding.
3.  **Execute with Precision:** Use the dedicated modification tools (`swift_replace_symbol_body`, etc.) to perform the changes surgically.
4.  **Verify:** **IMMEDIATELY** after any modification, run `swift_validate_file` on the affected file to ensure the changes are syntactically correct and compile.

### Index Management for Optimal LSP Performance
The `swift_build_index` tool is your key to maintaining accurate cross-file symbol resolution and references. Use it strategically:

**Batch Operations for Efficiency:**
When making multiple file edits, run `swift_build_index` once at the end of all modifications rather than after each change. This significantly improves performance.

**Immediate Rebuilds When Critical:**
Run `swift_build_index` immediately when:
- You need to use `swift_find_symbol_references_files` on newly created or modified symbols
- Cross-file navigation seems broken after structural changes
- You're about to perform operations that depend on accurate symbol relationships

**Specific Triggers:**
1.  **New Swift Files:** After creating new files that define symbols used elsewhere
2.  **Signature Changes:** When modifying function/method signatures, class/struct declarations, or protocol definitions
3.  **Empty References:** If `swift_find_symbol_references_files` returns unexpectedly empty results
4.  **New Projects:** When starting work on any Swift project (SPM or Xcode)
5.  **Dependency Updates:** After modifying Package.swift or Xcode project dependencies
6.  **Stale LSP Data:** When LSP operations return outdated information

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
