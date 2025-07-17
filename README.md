[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/swiftlens-swiftlens-badge.png)](https://mseep.ai/app/swiftlens-swiftlens)

# SwiftLens: First MCP Server that provides Semantic-Lelvel Analysis for iOS/Swift Development

**SwiftLens** is a Model Context Protocol (MCP) server that provides deep, semantic-level analysis of Swift codebases to AI agents. By integrating directly with Apple's SourceKit-LSP, SwiftLens enables AI models to understand Swift code with compiler-grade accuracy.

## Features

SwiftLens bridges AI models and Swift development through:

```
AI Agent (Claude/GPT) → MCP Protocol → SwiftLens → SourceKit-LSP → Swift Code
```

### Core Capabilities

- **LSP-Powered Semantic Analysis**: Leverages SourceKit-LSP for Xcode-grade accuracy
- **Token-Optimized Output**: Minimizes token usage for AI interactions
- **Real-time Code Understanding**: Analyzes Swift files with full language feature support
- **Cross-file Navigation**: Symbol references, definitions, and project-wide analysis
- **Code Modification Tools**: Safe, atomic file operations for AI-driven refactoring
- **Zero Configuration**: Works out-of-the-box with standard Swift projects

### Supported Swift Features

- Modern Swift syntax (actors, async/await, property wrappers, result builders)
- Generic types and protocols
- Swift Package Manager and Xcode projects
- Unicode identifiers and symbols
- Complex nested types and extensions

## Installation

### Prerequisites

- **macOS** (required for SourceKit-LSP)
- **Python 3.10+**
- **Xcode** (full installation from App Store, not just Command Line Tools)

## Quick Start

### Configure for Claude Code / Gemini CLI

Add to your json configuration file mcpServers section:

```json
{
  "mcpServers": {
    "swiftlens": {
      "command": "uvx",
      "args": ["swiftlens"]
    }
  }
}
```

## SourceKit LSP Index

SwiftLens will need proper sourcekit-lsp index in order to work properly you can either

### Ask AI to build your index

```bash
"hey claude, run swift_build_index tool"
```

### Building Your Project Index Manually

SwiftLens requires an index store for cross-file analysis. Build it with:

```bash
# Navigate to your Swift project
cd /path/to/your/swift/project

# Build with index store
swift build -Xswiftc -index-store-path -Xswiftc .build/index/store
```

**Important**: Rebuilding of the index is required when you:

- Add new Swift files
- Change public interfaces
- Notice missing symbol references

### Available Tools

SwiftLens provides 15 tools for Swift code analysis:

#### Single-File Analysis (No Index Required)

- `swift_analyze_file` - Analyze structure and symbols in a Swift file
- `swift_analyze_multiple_files` - Batch analyze multiple files
- `swift_summarize_file` - Get symbol counts and file summary
- `swift_get_symbols_overview` - Extract top-level type declarations
- `swift_get_declaration_context` - Get fully-qualified symbol paths
- `swift_get_file_imports` - Extract import statements
- `swift_validate_file` - Validate syntax and types with swiftc
- `swift_check_environment` - Verify Swift development setup
- `swift_build_index` - Build index store db of current project for sourcekit-lsp

#### Cross-File Analysis (Requires Index)

- `swift_find_symbol_references` - Find all references to a symbol
- `swift_get_symbol_definition` - Jump to symbol definition
- `swift_get_hover_info` - Get type info and documentation

#### Code Modification

- `swift_replace_symbol_body` - Replace function/type body

#### Utilities

- `swift_search_pattern` - Search with regex patterns
- `get_tool_help` - Get help for any tool

### Example Usage

Ask your AI agent:

```
"Analyze the UserManager.swift file and find all references to the login() method"
```

The AI will use SwiftLens tools to:

1. Analyze the file structure
2. Locate the login method
3. Find all project-wide references
4. Provide insights based on the analysis

## Real-time Dashboard (CURRENT NOT WORKING, REWORK IMPLEMENTATION PLANNED)

SwiftLens includes a web dashboard for monitoring AI interactions:

- **URL**: http://localhost:53729 (when server is running)
- **Features**: Live tool execution logs, usage analytics, session tracking
- **Security**: Localhost-only access, no external connections

## Troubleshooting

### "Symbol not found" or "No references found"

Rebuild your index:

```bash
swift build -Xswiftc -index-store-path -Xswiftc .build/index/store
```

### New files not recognized

New files need to be indexed:

```bash
swift build -Xswiftc -index-store-path -Xswiftc .build/index/store
```

### SourceKit-LSP not found

Ensure Xcode is properly installed:

```bash
xcode-select -p  # Should show Xcode path
xcrun sourcekit-lsp --help  # Should show help text
```

## SourceKit-LSP Limitations

### Known SourceKit-LSP Limitations

The SwiftLens MCP Server accurately reflects SourceKit-LSP's capabilities. The following are known limitations of SourceKit-LSP itself, not bugs in this tool:

#### Hover Information
- **Limited support for local variables**: Hover info may not be available for local variables within function bodies
- **Property access issues**: Expressions like `object.property` often don't provide hover information when inside functions
- **Method call limitations**: Hover on method calls with parameters may return incorrect or no information
- **Success rate**: Hover typically works well for type declarations, method signatures, and top-level symbols, but has approximately 44% success rate for expressions within function bodies

These limitations exist because SourceKit-LSP:
- Does not perform background indexing
- May skip function body analysis in certain configurations
- Is still in early development with acknowledged "rough edges"

For the most up-to-date status, see the [SourceKit-LSP repository](https://github.com/swiftlang/sourcekit-lsp).

## Development

### Running Tests

```bash
# All tests
make test

# Unit tests only (fast, no LSP required)
make test-unit

# LSP integration tests
make test-lsp

# Check environment
make check-env
```

### Code Quality

```bash
# Format code
./format.sh

# Check formatting
./format.sh check
```

## License - FULLY AVAILABLE TO YOU FOR FREE (PERSONAL USE ONLY UNDER LICENSE)

- ✅ Free for personal use and evaluation
- ⚠️ Commercial use requires a license

See [LICENSE.md](./LICENSE.md) for details.

## Contributing

We welcome contributions! Areas where you can help:

- 🐛 Bug reports and fixes
- 📝 Documentation improvements
- 🧪 Test coverage expansion
- 🔧 New analysis capabilities

## Support

- **Issues**: [GitHub Issues](https://github.com/swiftlens/swiftlens/issues)

---

SwiftLens - Bringing compiler-grade Swift understanding to AI development
