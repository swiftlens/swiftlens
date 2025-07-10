"""Tool for providing concise help documentation for Swift Context MCP tools."""

from typing import Any

from model.models import ErrorType, ToolHelpInfo, ToolHelpResponse


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
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "symbols": "Hierarchical symbol tree",
                "format": "types and names",
            },
            "examples": [
                "swift_analyze_file('MyClass.swift') -> 'User (struct)\\n  id (property)\\n  validate() (method)'"
            ],
        },
        "swift_analyze_multiple_files": {
            "purpose": "Batch analyze multiple Swift files for symbol structures",
            "use_cases": [
                "Analyze entire modules or directories",
                "Generate project-wide documentation",
                "Understand multi-file architecture",
            ],
            "parameters": {"file_paths": "List of Swift file paths"},
            "output_format": {
                "symbols": "Combined symbol trees",
                "format": "file-by-file breakdown",
            },
            "examples": [
                "swift_analyze_multiple_files(['A.swift', 'B.swift']) -> file-by-file symbol breakdown"
            ],
        },
        "swift_format_context": {
            "purpose": "Generate AI-optimized context string from Swift file analysis",
            "use_cases": [
                "Prepare file context for AI code generation",
                "Create condensed file summaries",
                "Feed structured data to other AI tools",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "context": "Formatted string",
                "format": "optimized for AI consumption",
            },
            "examples": ["swift_format_context('App.swift') -> structured context for AI tools"],
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
        "swift_find_symbol_references": {
            "purpose": "Find all references to a specific symbol in a Swift file",
            "use_cases": [
                "Locate all usages of a variable/function/class",
                "Refactoring impact analysis",
                "Code navigation and exploration",
            ],
            "parameters": {"file_path": "File path", "symbol_name": "Symbol to find"},
            "output_format": {
                "references": "Reference locations",
                "format": "line:character positions",
            },
            "examples": [
                "swift_find_symbol_references('App.swift', 'User') -> '5:10\\n12:4\\n23:15'"
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
                "file_path": "File path",
                "line": "Line number (1-based)",
                "character": "Character position (1-based)",
            },
            "output_format": {
                "type": "Type signature",
                "docs": "Documentation if available",
            },
            "examples": [
                "swift_get_hover_info('App.swift', 10, 5) -> 'var name: String - User's display name'"
            ],
        },
        "swift_get_declaration_context": {
            "purpose": "Get fully-qualified declaration paths for all symbols",
            "use_cases": [
                "Generate qualified symbol names",
                "Create navigation hierarchies",
                "Build symbol indexes with full paths",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "declarations": "Qualified symbol paths",
                "format": "Module.Class.method format",
            },
            "examples": [
                "swift_get_declaration_context('App.swift') -> 'MyApp.User.validateEmail\\nMyApp.UserService.addUser'"
            ],
        },
        "swift_get_symbol_definition": {
            "purpose": "Find definition location for a symbol (supports cross-file)",
            "use_cases": [
                "Jump to symbol definition",
                "Locate symbol source across modules",
                "Code navigation and exploration",
            ],
            "parameters": {"file_path": "File path", "symbol_name": "Symbol to locate"},
            "output_format": {
                "definition": "Definition location",
                "format": "file:line:character",
            },
            "examples": [
                "swift_get_symbol_definition('App.swift', 'User') -> '/path/User.swift:5:12'"
            ],
        },
        "swift_get_file_imports": {
            "purpose": "Extract all import statements from a Swift file",
            "use_cases": [
                "Analyze file dependencies",
                "Generate dependency graphs",
                "Understand module relationships",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "imports": "Import statements",
                "format": "one per line, attributes removed",
            },
            "examples": [
                "swift_get_file_imports('App.swift') -> 'import Foundation\\nimport UIKit\\nimport SwiftUI'"
            ],
        },
        "swift_summarize_file": {
            "purpose": "Count symbol types in a Swift file (classes, functions, enums, etc.)",
            "use_cases": [
                "Get quick file statistics and overview",
                "Analyze code complexity and structure",
                "Generate file metrics for documentation",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "counts": "Symbol counts by type",
                "format": "Class: 3\\nFunction: 12\\nEnum: 2",
            },
            "examples": [
                "swift_summarize_file('MyFile.swift') -> 'Class: 2\\nFunction: 8\\nProperty: 5\\nEnum: 1'"
            ],
        },
        "swift_get_symbols_overview": {
            "purpose": "Extract only top-level symbols (classes, structs, enums, protocols) from a Swift file",
            "use_cases": [
                "Get quick overview of main types in a file",
                "Filter out implementation details and focus on architecture",
                "Generate type-only documentation or navigation",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "symbols": "Top-level type symbols only",
                "format": "SymbolName (Type) format, one per line",
            },
            "examples": [
                "swift_get_symbols_overview('MyFile.swift') -> 'User (Struct)\\nUserService (Class)\\nUserRole (Enum)'"
            ],
        },
        "swift_validate_file": {
            "purpose": "Validate Swift file using swiftc type checking and return compilation errors",
            "use_cases": [
                "Catch syntax and type errors before compilation",
                "Validate code changes for correctness",
                "Get compiler-grade error detection beyond LSP analysis",
            ],
            "parameters": {"file_path": "Path to Swift file"},
            "output_format": {
                "validation": "Validation results",
                "format": "line:col type: message format, with summary",
            },
            "examples": [
                "swift_validate_file('MyFile.swift') -> '10:5 error: cannot find function\\nSummary: 1 error'"
            ],
        },
        "swift_insert_before_symbol": {
            "purpose": "Insert code directly before a specified Swift symbol using LSP positioning",
            "use_cases": [
                "Add documentation comments before functions/classes",
                "Insert code annotations or attributes",
                "Add new properties or methods before existing ones",
            ],
            "parameters": {
                "file_path": "File path",
                "symbol_name": "Symbol name",
                "content": "Code to insert",
            },
            "output_format": {
                "result": "Success message",
                "format": "line count and position, or error description",
            },
            "examples": [
                "swift_insert_before_symbol('App.swift', 'User', '// MARK: - User Model') -> 'Inserted 1 lines before User at line 15'"
            ],
        },
        "swift_insert_after_symbol": {
            "purpose": "Insert code directly after a specified Swift symbol using LSP positioning",
            "use_cases": [
                "Add new methods after existing ones",
                "Insert related functionality after classes/structs",
                "Add test cases after function definitions",
            ],
            "parameters": {
                "file_path": "File path",
                "symbol_name": "Symbol name",
                "content": "Code to insert",
            },
            "output_format": {
                "result": "Success message",
                "format": "line count and position, or error description",
            },
            "examples": [
                "swift_insert_after_symbol('App.swift', 'User', 'extension User { }') -> 'Inserted 1 lines after User at line 25'"
            ],
        },
        "swift_replace_regex": {
            "purpose": "Apply regex replacements with smart auto-escaping for Swift patterns",
            "use_cases": [
                "Rename functions across files (func hello() -> func greetings())",
                "Replace type names with auto-escaping (Helper() -> NewHelper())",
                "Update string literals or file paths safely",
                "Advanced regex replacements with manual escaping",
            ],
            "parameters": {
                "file_path": "File path",
                "regex_pattern": "Pattern to match",
                "replacement": "Replacement text",
                "flags": "Optional regex flags (i,m,s)",
            },
            "output_format": {
                "replacements": "Number of replacements made",
                "format": "count and success status",
            },
            "examples": [
                "swift_replace_regex('App.swift', 'func hello()', 'func greetings()') -> 'Replaced 1 occurrence'"
            ],
        },
        "swift_replace_symbol_body": {
            "purpose": "Replace the body content of a specified Swift symbol while preserving declaration",
            "use_cases": [
                "Update function implementations",
                "Replace class/struct body content",
                "Modify method logic while keeping signature",
            ],
            "parameters": {
                "file_path": "File path",
                "symbol_name": "Symbol name",
                "new_body": "New body content",
            },
            "output_format": {
                "result": "Success message",
                "format": "replacement confirmation or error description",
            },
            "examples": [
                "swift_replace_symbol_body('App.swift', 'calculateTotal', 'return a + b + tax') -> 'Replaced body of calculateTotal'"
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
                "file_path": "File path",
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
                "swift_search_pattern('App.swift', 'func.*calculate') -> '10:4 func calculateTotal()\\n25:8 func calculateTax()'"
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
