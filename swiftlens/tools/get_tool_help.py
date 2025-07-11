"""Tool for providing concise help documentation for Swift Context MCP tools."""

from typing import Any

from swiftlens.model.models import ErrorType, ToolHelpInfo, ToolHelpResponse


def get_tool_help(tool_name: str = None) -> dict[str, Any]:
    """Get concise help for Swift tools. Pass tool_name for specific help, or None for all tools."""

    # Tool data structured to build ToolHelpInfo objects
    tools_data = {
        "swift_analyze_file": {
            "purpose": "Extract symbol structure from a Swift file using SourceKit-LSP",
            "use_cases": [
                "Get overview of classes, structs, functions in a file",
                "Understand file structure before editing",
                "Generate code documentation or navigation",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "symbols": "Hierarchical symbol tree",
                "format": "types and names",
            },
            "examples": [
                "swift_analyze_file('src/MyClass.swift') -> 'User (struct)\\n  id (property)\\n  validate() (method)'"
            ],
        },
        "swift_analyze_multiple_files": {
            "purpose": "Batch analyze multiple Swift files for symbol structures",
            "use_cases": [
                "Analyze entire modules or directories",
                "Generate project-wide documentation",
                "Understand multi-file architecture",
            ],
            "parameters": {
                "file_paths": "List of Swift file paths (prefer relative paths like ['src/A.swift', 'src/B.swift'])"
            },
            "output_format": {
                "symbols": "Combined symbol trees",
                "format": "file-by-file breakdown",
            },
            "examples": [
                "swift_analyze_multiple_files(['src/A.swift', 'src/B.swift']) -> file-by-file symbol breakdown"
            ],
        },
        "swift_check_environment": {
            "purpose": "Validate Swift development environment setup",
            "use_cases": [
                "Troubleshoot SourceKit-LSP issues",
                "Verify Xcode/toolchain installation",
                "Debug tool connectivity problems",
            ],
            "parameters": {},
            "output_format": {
                "status": "Environment status",
                "recommendations": "Setup advice",
            },
            "examples": [
                "swift_check_environment() -> 'Xcode: ✓ | SourceKit-LSP: ✓ | Recommendations: none'"
            ],
        },
        "swift_find_symbol_references_files": {
            "purpose": "Find all references to a specific symbol across multiple Swift files",
            "use_cases": [
                "Locate all usages of a variable/function/class across specified files",
                "Multi-file refactoring impact analysis",
                "Code navigation and exploration across file boundaries",
            ],
            "parameters": {
                "file_paths": "List of file paths (prefer relative paths like 'src/App.swift')",
                "symbol_name": "Symbol to find",
            },
            "output_format": {
                "references": "Reference locations per file",
                "format": "file-by-file breakdown with line:character positions",
            },
            "examples": [
                "swift_find_symbol_references_files(['src/App.swift', 'src/User.swift'], 'User') -> per-file reference breakdown"
            ],
        },
        "swift_get_hover_info": {
            "purpose": "Get type and documentation info for symbol at specific position",
            "use_cases": [
                "Get symbol type information",
                "Display documentation on hover",
                "Understand symbol context at cursor",
            ],
            "parameters": {
                "file_path": "File path (prefer relative paths like 'src/App.swift')",
                "line": "Line number (1-based)",
                "character": "Character position (1-based)",
            },
            "output_format": {
                "type": "Type signature",
                "docs": "Documentation if available",
            },
            "examples": [
                "swift_get_hover_info('src/App.swift', 10, 5) -> 'var name: String - User's display name'"
            ],
        },
        "swift_get_declaration_context": {
            "purpose": "Get fully-qualified declaration paths for all symbols",
            "use_cases": [
                "Generate qualified symbol names",
                "Create navigation hierarchies",
                "Build symbol indexes with full paths",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "declarations": "Qualified symbol paths",
                "format": "Module.Class.method format",
            },
            "examples": [
                "swift_get_declaration_context('src/App.swift') -> 'MyApp.User.validateEmail\\nMyApp.UserService.addUser'"
            ],
        },
        "swift_get_symbol_definition": {
            "purpose": "Find definition location for a symbol (supports cross-file)",
            "use_cases": [
                "Jump to symbol definition",
                "Locate symbol source across modules",
                "Code navigation and exploration",
            ],
            "parameters": {
                "file_path": "File path (prefer relative paths like 'src/App.swift')",
                "symbol_name": "Symbol to locate",
            },
            "output_format": {
                "definition": "Definition location",
                "format": "file:line:character",
            },
            "examples": [
                "swift_get_symbol_definition('src/App.swift', 'User') -> '/path/User.swift:5:12'"
            ],
        },
        "swift_get_file_imports": {
            "purpose": "Extract all import statements from a Swift file",
            "use_cases": [
                "Analyze file dependencies",
                "Generate dependency graphs",
                "Understand module relationships",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "imports": "Import statements",
                "format": "one per line, attributes removed",
            },
            "examples": [
                "swift_get_file_imports('src/App.swift') -> 'import Foundation\\nimport UIKit\\nimport SwiftUI'"
            ],
        },
        "swift_summarize_file": {
            "purpose": "Count symbol types in a Swift file (classes, functions, enums, etc.)",
            "use_cases": [
                "Get quick file statistics and overview",
                "Analyze code complexity and structure",
                "Generate file metrics for documentation",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "counts": "Symbol counts by type",
                "format": "Class: 3\\nFunction: 12\\nEnum: 2",
            },
            "examples": [
                "swift_summarize_file('src/MyFile.swift') -> 'Class: 2\\nFunction: 8\\nProperty: 5\\nEnum: 1'"
            ],
        },
        "swift_get_symbols_overview": {
            "purpose": "Extract only top-level symbols (classes, structs, enums, protocols) from a Swift file",
            "use_cases": [
                "Get quick overview of main types in a file",
                "Filter out implementation details and focus on architecture",
                "Generate type-only documentation or navigation",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "symbols": "Top-level type symbols only",
                "format": "SymbolName (Type) format, one per line",
            },
            "examples": [
                "swift_get_symbols_overview('src/MyFile.swift') -> 'User (Struct)\\nUserService (Class)\\nUserRole (Enum)'"
            ],
        },
        "swift_validate_file": {
            "purpose": "Validate Swift file using swiftc type checking and return compilation errors",
            "use_cases": [
                "Catch syntax and type errors before compilation",
                "Validate code changes for correctness",
                "Get compiler-grade error detection beyond LSP analysis",
            ],
            "parameters": {
                "file_path": "Path to Swift file (prefer relative paths like 'src/MyFile.swift')"
            },
            "output_format": {
                "validation": "Validation results",
                "format": "line:col type: message format, with summary",
            },
            "examples": [
                "swift_validate_file('src/MyFile.swift') -> '10:5 error: cannot find function\\nSummary: 1 error'"
            ],
        },
        "swift_replace_symbol_body": {
            "purpose": "Replace the body content of a specified Swift symbol while preserving declaration",
            "use_cases": [
                "Update function/method implementations",
                "Replace class/struct body content",
                "Modify method logic while keeping signature",
                "Refactor implementation without changing interface",
            ],
            "parameters": {
                "file_path": "File path (prefer relative paths like 'src/App.swift')",
                "symbol_name": "Symbol name WITH FULL SIGNATURE - CRITICAL: For methods, include parameter labels (e.g., 'add(_:)' not 'add')",
                "new_body": "New body content (without braces - just the code inside)",
            },
            "output_format": {
                "result": "Success message with replaced symbol",
                "format": "replacement confirmation or error description",
            },
            "examples": [
                "swift_replace_symbol_body('src/App.swift', 'calculateTotal', 'return items.reduce(0, +)') -> 'Replaced body of calculateTotal'",
                "swift_replace_symbol_body('src/User.swift', 'add(_:)', 'users.append(user)\\nnotifyObservers()') -> 'Replaced body of add(_:)'",
                "swift_replace_symbol_body('src/Service.swift', 'fetch(id:completion:)', 'guard let url = buildURL(id) else { return }\\n// implementation') -> 'Replaced body of fetch(id:completion:)'",
                "IMPORTANT: For methods with parameters, ALWAYS use full signature: validate() for no params, validate(_:) for one unlabeled param, validate(email:) for labeled param",
            ],
        },
        "swift_search_pattern": {
            "purpose": "Find regex/string matches with precise line/character positions and context",
            "use_cases": [
                "Search for specific code patterns",
                "Find all occurrences of function calls or variables",
                "Locate text with context lines for review",
            ],
            "parameters": {
                "file_path": "File path (prefer relative paths like 'src/App.swift')",
                "pattern": "Search pattern",
                "is_regex": "Use regex (default true)",
                "flags": "Regex flags",
                "context_lines": "Context lines around matches",
            },
            "output_format": {
                "matches": "Match locations",
                "format": "line:char positions with optional context",
            },
            "examples": [
                "swift_search_pattern('src/App.swift', 'func.*calculate') -> '10:4 func calculateTotal()\\n25:8 func calculateTax()'"
            ],
        },
        "swift_lsp_diagnostics": {
            "purpose": "Comprehensive LSP diagnostics combining environment, health, and performance checks",
            "use_cases": [
                "Diagnose SourceKit-LSP setup issues",
                "Check Swift development environment",
                "Monitor LSP client health and performance",
                "Validate project configuration for LSP",
            ],
            "parameters": {
                "project_path": "Optional path to Swift project",
                "include_recommendations": "Whether to include setup recommendations (default true)",
            },
            "output_format": {
                "diagnostics": "Environment, health, stats, and recommendations",
                "format": "comprehensive JSON with all diagnostic data",
            },
            "examples": [
                "swift_lsp_diagnostics() -> full environment and LSP diagnostics",
                "swift_lsp_diagnostics('/path/to/project') -> project-specific diagnostics",
            ],
        },
        "swift_build_index": {
            "purpose": "Build or rebuild Swift project index for better LSP functionality",
            "use_cases": [
                "Fix stale symbol references after code changes",
                "Enable cross-file navigation in new projects",
                "Update index after adding/modifying Swift files",
                "Resolve empty reference results from LSP",
                "Refresh index after dependency updates",
            ],
            "parameters": {
                "project_path": "Path to Swift project (optional, defaults to current directory)",
                "timeout": "Build timeout in seconds (default 60, max 300)",
                "scheme": "For Xcode projects, specific scheme to build (optional, auto-detected if not provided)",
            },
            "output_format": {
                "status": "Build success/failure",
                "index_path": "Location of generated index",
                "build_output": "Swift build command output",
                "project_type": "Detected project type (SPM or Xcode)",
            },
            "examples": [
                "swift_build_index() -> builds index in current directory",
                "swift_build_index('/path/to/project', 120) -> builds with 2-minute timeout",
                "swift_build_index('/path/to/project', 60, 'MyApp') -> builds Xcode project with specific scheme",
            ],
        },
    }

    # Build available_tools list
    available_tools = list(tools_data.keys())

    if tool_name:
        if tool_name in tools_data:
            # Return specific tool help
            tool_data = tools_data[tool_name]
            tool_help_info = ToolHelpInfo(
                name=tool_name,
                purpose=tool_data["purpose"],
                parameters=tool_data["parameters"],
                use_cases=tool_data["use_cases"],
                output_format=tool_data["output_format"],
                examples=tool_data["examples"],
            )

            return ToolHelpResponse(
                success=True,
                tool_name=tool_name,
                tools=tool_help_info,
                available_tools=available_tools,
            ).model_dump()
        else:
            # Tool not found error
            error_msg = (
                f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}"
            )

            return ToolHelpResponse(
                success=False,
                tool_name=tool_name,
                tools=[],  # Empty list for error case
                available_tools=available_tools,
                error=error_msg,
                error_type=ErrorType.VALIDATION_ERROR,
            ).model_dump()
    else:
        # Return help for all tools
        all_tools_help = []
        for name, data in tools_data.items():
            tool_help_info = ToolHelpInfo(
                name=name,
                purpose=data["purpose"],
                parameters=data["parameters"],
                use_cases=data["use_cases"],
                output_format=data["output_format"],
                examples=data["examples"],
            )
            all_tools_help.append(tool_help_info)

        return ToolHelpResponse(
            success=True,
            tool_name=None,
            tools=all_tools_help,
            available_tools=available_tools,
        ).model_dump()
