# Contributing to SwiftLens

Thank you for your interest in contributing to SwiftLens MCP Server! This guide will help you get started with development and testing.

## Development Setup

### Prerequisites

- **macOS** (SourceKit-LSP dependency)
- **Python 3.13** (with pip included)
- **Git** (for cloning repository)
- **Bash** (for running setup scripts)
- **Full Xcode installation** (required to run LSP integration tests)

### Zero-Configuration Getting Started

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd swiftlens-mcp
   chmod +x run_swiftlens.sh
   ```

2. **Automated setup (creates venv and installs all dependencies):**

   ```bash
   # Option 1: Use the automated setup script
   ./run_swiftlens.sh
   # Script automatically creates .venv and installs all dependencies

   # Option 2: Use make command (also creates .venv automatically)
   make install-dev
   ```

3. **Verify your setup:**
   ```bash
   make check-env  # Comprehensive environment validation
   make test-unit  # Quick functionality test
   ```

## Project Structure

```
swiftlens/
├── server.py           # MCP server with tool registrations
├── tools/             # Main MCP tools (swift_analyze_file, etc.)
├── utils/             # Shared utilities (validation, file ops, etc.)
├── analysis/          # Symbol and file analyzers
├── compiler/          # Swift compiler integration
├── model/             # Data models (Pydantic schemas)
├── dashboard/         # Web dashboard (optional feature)
└── client/            # MCP client components

test/
├── conftest.py        # Pytest configuration and fixtures
├── tools/            # Tool-specific tests
└── utils/            # Utility tests
```

## Adding New Tools

### Step 1: Create the Tool Implementation

Create a new file in `swiftlens/tools/` directory:

```python
# swiftlens/tools/swift_your_tool.py
"""Tool for [brief description]."""

from typing import Any
from swiftlens.model.models import YourResponseModel, ErrorType
from swiftlens.utils.validation import validate_swift_file_path

def swift_your_tool(param1: str, param2: list[str] = None) -> dict[str, Any]:
    """Your tool's main function.

    Args:
        param1: Description of parameter 1
        param2: Optional parameter description

    Returns:
        YourResponseModel as dict with success status and results
    """
    # 1. Validate inputs
    if not param1:
        return YourResponseModel(
            success=False,
            error="param1 is required",
            error_type=ErrorType.VALIDATION_ERROR
        ).model_dump()

    # For file paths, use the validation utility
    is_valid, sanitized_path, error_msg = validate_swift_file_path(param1)
    if not is_valid:
        return YourResponseModel(
            success=False,
            error=error_msg,
            error_type=ErrorType.VALIDATION_ERROR
        ).model_dump()

    try:
        # 2. Implement your tool logic
        # Use LSP client if needed:
        from lsp.managed_client import find_swift_project_root, managed_lsp_client

        project_root = find_swift_project_root(sanitized_path)
        with managed_lsp_client(project_root=project_root) as client:
            # Use client for LSP operations
            pass

        # 3. Return success response
        return YourResponseModel(
            success=True,
            # ... your response fields
        ).model_dump()

    except Exception as e:
        return YourResponseModel(
            success=False,
            error=str(e),
            error_type=ErrorType.LSP_ERROR
        ).model_dump()
```

### Step 2: Define Response Model

Add your response model to `swiftlens/model/models.py`:

```python
class YourResponseModel(BaseModel):
    """Response model for your_tool operation."""

    success: bool
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None
    # Add your specific fields here
    results: Optional[list[YourResultType]] = None

    class Config:
        extra = "forbid"  # Strict validation
```

### Step 3: Register with MCP Server

Add your tool to `swiftlens/server.py`:

```python
@server.tool()
@log_tool_execution("swift_your_tool")
def swift_your_tool(param1: str, param2: list[str] = None) -> dict:
    """Brief description for MCP tool listing."""
    # Validate inputs with security checks
    if param1:
        is_valid, sanitized_param, error_msg = validate_swift_file_path(param1)
        if not is_valid:
            return {"success": False, "error": error_msg, "error_type": "VALIDATION_ERROR"}
        param1 = sanitized_param

    try:
        from .tools.swift_your_tool import swift_your_tool as tool_func
        return tool_func(param1, param2)
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool failed: {str(e)}",
            "error_type": "LSP_ERROR"
        }
```

### Step 4: Write Comprehensive Tests

Create `test/tools/test_swift_your_tool.py`:

```python
#!/usr/bin/env python3
"""Tests for swift_your_tool."""

import pytest
from swiftlens.tools.swift_your_tool import swift_your_tool
from .test_helpers import handle_tool_result

@pytest.fixture
def sample_swift_file(built_swift_environment):
    """Create test Swift file."""
    _, _, create_swift_file = built_swift_environment

    content = """
    // Your test Swift code
    """
    return create_swift_file(content, "TestFile.swift")

@pytest.mark.lsp  # Mark if requires LSP
def test_your_tool_success(sample_swift_file):
    """Test successful operation."""
    result = swift_your_tool(sample_swift_file)

    # Validate response structure
    assert isinstance(result, dict)
    assert "success" in result

    # Use helper for consistent error handling
    handle_tool_result(result)

    # Validate specific results
    assert result["success"] is True
    # Add more assertions

def test_your_tool_invalid_input():
    """Test with invalid input."""
    result = swift_your_tool("")

    assert result["success"] is False
    assert result["error_type"] == "VALIDATION_ERROR"
    assert "required" in result["error"].lower()

# Add more test cases for edge cases, errors, etc.
```

### Step 5: Update Documentation

Add your tool to `CLAUDE.md`:

```markdown
### `swift_your_tool(param1: str, param2: List[str] = None)` → JSON

Brief description of what the tool does. Returns `YourResponseModel` with results.
Detailed explanation of parameters, behavior, and example usage.
```

## Adding New Utilities

### Creating Utility Modules

Add utilities to `swiftlens/utils/`:

```python
# swiftlens/utils/your_utility.py
"""Utility for [description]."""

def your_utility_function(param: str) -> str:
    """Brief description.

    Args:
        param: Description

    Returns:
        Description of return value

    Example:
        >>> result = your_utility_function("test")
        >>> print(result)
        "processed: test"
    """
    # Implementation
    return f"processed: {param}"
```

### Testing Utilities

Create `test/utils/test_your_utility.py`:

```python
"""Tests for your_utility module."""

from swiftlens.utils.your_utility import your_utility_function

def test_your_utility_basic():
    """Test basic functionality."""
    result = your_utility_function("test")
    assert result == "processed: test"

def test_your_utility_edge_case():
    """Test edge cases."""
    # Test empty string, None, special chars, etc.
    pass
```

## Testing

Our project uses **pytest** with a **simplified 3-target test infrastructure** designed for efficient development workflows:

### Test Infrastructure Highlights

- ✅ **Pure pytest format** - Modern testing suites using pytest library
- ✅ **Smart environment detection** - LSP tests auto-skip when Xcode unavailable
- ✅ **Gentle LSP timeout handling** - Faster initialization with graceful degradation
- ✅ **SwiftUI compatibility fixes** - Removed problematic SwiftUI dependencies from test fixtures
- ✅ **Robust fixtures** - `swift_project` fixture creates proper SPM structure
- ✅ **Performance optimized** - Fast feedback for development workflow

### 3-Target Test Structure

#### 1. Unit Tests (Always Run)

```bash
# Core functionality without LSP dependencies - Safe for all contributors
make test-unit

# Direct pytest equivalent:
pytest -m "not lsp and not slow and not malformed"
```

**When to run:** Before every commit, during active development.

#### 2. All Tests (Main Pipeline)

```bash
# Unit + tools/test_swift_*.py + utils + lsp tests - Main development pipeline
make test

# Direct pytest equivalent:
pytest -m "not slow and not malformed"
```

**When to run:** Standard development workflow, CI fast feedback. Automatically falls back to unit tests if LSP unavailable.

#### 3. LSP Tests Only (Development)

```bash
# All test_swift_*.py LSP tests - For LSP feature work
make test-lsp

# Direct pytest equivalent:
pytest test/tools/test_swift_*.py -m lsp
```

**When to run:** When working on LSP features, debugging LSP issues. Requires full Xcode installation.

### LSP Environment Setup

If you want to run LSP integration tests:

1. **Install full Xcode** from the Mac App Store (Command Line Tools alone are insufficient)
2. **Configure xcode-select:**
   ```bash
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   ```
3. **Verify SourceKit-LSP is available:**
   ```bash
   xcrun --find sourcekit-lsp
   ```

**Note:** LSP tests are automatically skipped if the environment isn't available. Your contributions are welcome even if you can't run these tests locally - they'll be validated in CI.

## Code Style

We maintain **zero linting violations** with automated formatting and linting:

```bash
# Standard formatting and linting fixes
./format.sh

# Aggressive formatting with unsafe fixes
./format.sh --force

# Check formatting without making changes
./format.sh check
```

**Enhanced format.sh Features:**

- ✅ **ruff-powered** - Fast Python formatter and linter
- ✅ **Force mode** - Uses `--unsafe-fixes` for aggressive cleanup
- ✅ **Flexible usage** - Check, fix, or force mode support
- ✅ **Virtual environment aware** - Automatic activation if `.venv` exists

**Before submitting:** Always run `./format.sh` to ensure consistent code style.

## Best Practices

### 1. Token Optimization (CRITICAL)

The **#1 priority** after correctness is minimizing AI agent token usage:

```python
# ❌ BAD - Verbose output
return {
    "success": True,
    "message": "🎉 Successfully found 5 symbols!",
    "symbols": [...],
    "total_count": 5,
    "footer": "=" * 50
}

# ✅ GOOD - Minimal output
return {
    "success": True,
    "symbols": [...],
    "symbol_count": 5
}
```

### 2. Error Handling

Use structured error types from `model/models.py`:

```python
from swiftlens.model.models import ErrorType

# Use appropriate error types
ErrorType.VALIDATION_ERROR  # Invalid inputs
ErrorType.FILE_NOT_FOUND   # Missing files
ErrorType.LSP_ERROR        # LSP issues
ErrorType.PERMISSION_ERROR # Access denied
```

### 3. File Path Validation

Always validate file paths using utilities:

```python
from swiftlens.utils.validation import validate_swift_file_path

is_valid, sanitized_path, error_msg = validate_swift_file_path(file_path)
if not is_valid:
    return {"success": False, "error": error_msg}
```

### 4. LSP Client Usage

Use the managed client for automatic cleanup:

```python
from lsp.managed_client import managed_lsp_client, find_swift_project_root

project_root = find_swift_project_root(file_path)
with managed_lsp_client(project_root=project_root) as client:
    # Use client for operations
    pass
```

### 5. Test Patterns

- Mark LSP-dependent tests with `@pytest.mark.lsp`
- Use `handle_tool_result()` for consistent error handling
- Test both success and failure cases
- Include edge cases and malformed inputs
- Use fixtures from `conftest.py` for test environments

## Pull Request Guidelines

1. **Run tests locally:**

   ```bash
   # Required (fast feedback)
   make test-unit    # Unit tests only - Safe for all contributors
   make test         # Main pipeline - Recommended for most PRs

   # Optional (if working on LSP features)
   make test-lsp     # LSP tests only (requires full Xcode)
   ```

2. **Format your code:**

   ```bash
   ./format.sh     # Standard formatting
   ./format.sh --force  # Aggressive cleanup if needed
   ```

3. **Write descriptive commit messages:**

   - Use present tense ("Add feature" not "Added feature")
   - Keep the first line under 50 characters
   - Reference issue numbers when applicable

4. **Update tests:** Add tests for new functionality or bug fixes

5. **Update documentation:** Update this file or CLAUDE.md for significant changes

## Common Development Tasks

### Running Individual Tests

```bash
# Run specific test file
pytest test/tools/test_specific_tool.py -v

# Run with detailed output
pytest -v -s

# Run only failed tests
pytest --lf

# Check test collection without running
pytest --collect-only
```

### Debugging LSP Issues

1. Enable debug logging:

   ```bash
   export MCP_DEBUG=1
   tail -f /tmp/swiftlens-debug.log
   ```

2. Check LSP environment:

   ```bash
   make check-env
   ```

3. Test LSP directly:
   ```bash
   xcrun sourcekit-lsp
   ```

### Working with Fixtures

The test suite provides several useful fixtures:

- `built_swift_environment` - Creates a complete Swift project
- `swift_project` - Simple SPM project structure
- `test_swift_file` - Sample Swift file with various symbols
- `disable_dashboard_in_tests` - Prevents dashboard conflicts

## Getting Help

- **Check existing issues** for similar problems or questions
- **Run environment check:** `make check-env` for LSP setup issues
- **Review CLAUDE.md** for tool-specific documentation
- **Check test output** for specific error messages and debugging info

## CI/CD

Our CI runs:

- **Unit tests** on every PR (fast feedback)
- **Comprehensive tests** with LSP integration on macOS runners (full validation)
- **Code formatting and linting checks**

The improved test infrastructure ensures CI pipelines won't hang on LSP issues - tests either pass or skip gracefully. You don't need LSP environment locally - CI will validate LSP functionality.

---

Thank you for contributing! Your efforts help make Swift development more accessible and powerful.
