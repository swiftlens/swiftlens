# SwiftLens: MCP Server for Swift Code Sementic Analysis

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

### Quick Start

```bash
{
  "mcpServers": {
    "swiftlens": {
      "command": "uvx",
      "args":[ "swiftlens" ]
    }
  }
}
```

### First Time Running?

SwiftLens automatically installs its required `swiftlens-core` dependency on first run. If you see:

```
📦 swiftlens-core not found. Installing from TestPyPI...
✅ swiftlens-core installed successfully
⚠️  Please restart the MCP server for changes to take effect
```

Simply restart the MCP server and everything will work seamlessly.

### Configure for Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "swiftlens": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--index-url",
        "https://test.pypi.org/simple/",
        "--extra-index-url",
        "https://pypi.org/simple",
        "swiftlens"
      ]
    }
  }
}
```

Note: The `--index-url` and `--extra-index-url` arguments ensure SwiftLens is installed from TestPyPI with its dependencies.

## Usage

### Quick Start with Slash Command

Once SwiftLens is configured in Claude Code, you can quickly get started by using the built-in slash command:

```
/swiftlens_initial_prompt
```

This command provides a comprehensive guide to all SwiftLens tools, including:

- Overview of available tools organized by category
- Best practices for efficient token usage
- Step-by-step workflows for common tasks
- Natural language usage examples
- Performance optimization tips

The slash command is the fastest way to onboard your AI agent with SwiftLens capabilities.

### Building Your Project Index

SwiftLens requires an index store for cross-file analysis. Build it with:

```bash
# Navigate to your Swift project
cd /path/to/your/swift/project

# Build with index store
swift build -Xswiftc -index-store-path -Xswiftc .build/index/store
```

**Important**: Rebuild the index when you:

- Add new Swift files
- Change public interfaces
- Notice missing symbol references

### Available Tools

SwiftLens provides 14 tools for Swift code analysis:

#### Single-File Analysis (No Index Required)

- `swift_analyze_file` - Analyze structure and symbols in a Swift file
- `swift_analyze_multiple_files` - Batch analyze multiple files
- `swift_summarize_file` - Get symbol counts and file summary
- `swift_get_symbols_overview` - Extract top-level type declarations
- `swift_get_declaration_context` - Get fully-qualified symbol paths
- `swift_get_file_imports` - Extract import statements
- `swift_validate_file` - Validate syntax and types with swiftc
- `swift_check_environment` - Verify Swift development setup

#### Cross-File Analysis (Requires Index)

- `swift_find_symbol_references_files` - Find all references to a symbol for given files
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

## License - FULLY AVAILABLE TO YOU FOR FREE (PERSONAL USE ONLY UNDER ELASTIC 2.0 LICENSE)

SwiftLens is licensed under the Elastic License 2.0:

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
