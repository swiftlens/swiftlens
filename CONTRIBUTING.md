# Contributing to SwiftLens

Thank you for your interest in contributing to SwiftLens! This guide will help you get started.

## Development Requirements

### Prerequisites

- **macOS** (required for SourceKit-LSP)
- **Python 3.13** (specific version requirement)
- **Xcode** (full installation from App Store, not just Command Line Tools)

### Setting Up Your Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/swiftlens/swiftlens.git
   cd swiftlens
   ```

2. **Create a Python 3.13 virtual environment:**
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify your setup:**
   ```bash
   make check-env
   ```

## Running Tests

### Test Commands

```bash
# Run all tests
make test

# Run unit tests only (no LSP required)
make test-unit

# Run LSP tests only
make test-lsp

# Run specific test file
pytest test/tools/test_swift_analyze_file.py -v
```

### Writing Tests

- Mark LSP-dependent tests with `@pytest.mark.lsp`
- Test both success and failure cases
- Include edge cases and malformed inputs
- Use fixtures from `conftest.py`

## Code Style

We maintain zero linting violations:

```bash
# Format code
./format.sh

# Check formatting without changes
./format.sh check

# Force aggressive formatting
./format.sh --force
```

**Always run formatting before submitting a PR.**

## Submitting Pull Requests

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and test:**
   ```bash
   make test
   ./format.sh
   ```

3. **Commit with descriptive messages:**
   ```bash
   git commit -m "Add feature: description"
   ```

4. **Push and create PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

### PR Checklist

- [ ] Tests pass locally (`make test`)
- [ ] Code is formatted (`./format.sh`)
- [ ] New features have tests
- [ ] Documentation is updated if needed

## Areas for Contribution

We especially welcome contributions in:

- 🐛 Bug fixes
- 📝 Documentation improvements
- 🧪 Test coverage expansion
- 🔧 New Swift analysis tools
- 🎨 Token optimization for AI efficiency

## Development Tips

### Token Optimization

When adding features, prioritize minimal token usage:

```python
# ❌ Bad - Verbose output
return {"success": True, "message": "Found 5 symbols!", "symbols": [...]}

# ✅ Good - Minimal output
return {"success": True, "symbols": [...], "count": 5}
```

### Error Handling

Use structured error types:

```python
from swiftlens.model.models import ErrorType

return {
    "success": False,
    "error": "File not found",
    "error_type": ErrorType.FILE_NOT_FOUND
}
```

## Getting Help

- Check existing [GitHub Issues](https://github.com/swiftlens/swiftlens/issues)
- Review the [detailed contributing guide](swiftlens/CONTRIBUTING.md) for more information
- Run `make check-env` for environment issues

Thank you for contributing to SwiftLens!