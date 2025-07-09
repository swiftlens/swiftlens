# Swift Context MCP - Makefile for testing and development
# 
# This Makefile provides convenient commands for running tests and development tasks.
# Virtual environment is automatically created and activated for all commands.

.PHONY: test test-unit test-lsp test-references install-dev format lint help clean clean-venv

# Default target
help:
	@echo "Swift Context MCP - Available Commands:"
	@echo ""
	@echo "Testing:"
	@echo "  make test        - Run all unit + tools/test_swift_*.py + utils + lsp tests"
	@echo "  make test-unit   - Run unit tests only (no LSP dependencies)"
	@echo "  make test-lsp    - Run all test_swift_*.py LSP tests"
	@echo "  make test-references - Run comprehensive reference tests with IndexStoreDB"
	@echo ""
	@echo "Development:"
	@echo "  make install-dev - Install development dependencies"
	@echo "  make format      - Format code with black and isort"
	@echo "  make lint        - Run linting with ruff and mypy"
	@echo ""
	@echo "Environment:"
	@echo "  make check-env   - Check if LSP environment is properly configured"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove cache files"
	@echo "  make clean-venv  - Remove virtual environment"

# Virtual environment setup - automatically creates .venv if it doesn't exist
.venv:
	@echo "📦 Creating virtual environment..."
	python3 -m venv .venv
	@echo "📦 Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo "✅ Virtual environment ready at .venv/"

# All tests - runs unit + tools/test_swift_*.py + utils + lsp tests
test: .venv
	@echo "🔍 Checking SourceKit-LSP environment..."
	@if ! xcrun --find sourcekit-lsp > /dev/null 2>&1; then \
		echo "❌ Error: SourceKit-LSP not found."; \
		echo "   Please ensure you have a full Xcode installation (not just Command Line Tools)."; \
		echo "   Run 'sudo xcode-select -s /Applications/Xcode.app/Contents/Developer' if needed."; \
		echo "   Falling back to unit tests only..."; \
		\$\(MAKE\) test-unit; \
	else \
		echo "✅ SourceKit-LSP environment detected"; \
		echo "🧪 Running all unit + tools/utils/lsp tests (no slow/malformed)..."; \
		source .venv/bin/activate && PYTHONPATH=$$PWD:$$PYTHONPATH pytest -m "not slow and not malformed" -v; \
	fi

# Unit tests - runs without LSP requirements (safe for all contributors)
test-unit: .venv
	@echo "🧪 Running unit tests only (no LSP, no slow, no malformed)..."
	@source .venv/bin/activate && PYTHONPATH=$$PWD:$$PYTHONPATH pytest -m "not lsp and not slow and not malformed" -v

# LSP tests - runs all test_swift_*.py LSP tests
test-lsp: .venv
	@echo "🔍 Checking SourceKit-LSP environment..."
	@if ! xcrun --find sourcekit-lsp > /dev/null 2>&1; then \
		echo "❌ Error: SourceKit-LSP not found."; \
		echo "   Please ensure you have a full Xcode installation (not just Command Line Tools)."; \
		echo "   Run 'sudo xcode-select -s /Applications/Xcode.app/Contents/Developer' if needed."; \
		exit 1; \
	fi
	@echo "✅ SourceKit-LSP environment detected"
	@echo "🧪 Running all test_swift_*.py LSP tests..."
	@source .venv/bin/activate && PYTHONPATH=$$PWD:$$PYTHONPATH pytest test/tools/test_swift_*.py -m lsp -v

# Comprehensive reference tests - runs build-based tests with IndexStoreDB
test-references: .venv
	@echo "🔍 Checking SourceKit-LSP environment..."
	@if ! xcrun --find sourcekit-lsp > /dev/null 2>&1; then \
		echo "❌ Error: SourceKit-LSP not found."; \
		echo "   Please ensure you have a full Xcode installation (not just Command Line Tools)."; \
		echo "   Run 'sudo xcode-select -s /Applications/Xcode.app/Contents/Developer' if needed."; \
		exit 1; \
	fi
	@echo "✅ SourceKit-LSP environment detected"
	@echo "🏗️  Running comprehensive reference tests with IndexStoreDB..."
	@echo "   Note: This will build Swift test projects and may take longer"
	@source .venv/bin/activate && PYTHONPATH=$$PWD:$$PYTHONPATH pytest test/tools/test_swift_find_symbol_references.py -m "lsp_comprehensive" -v


# Development setup - now just ensures .venv exists
install-dev: .venv
	@echo "✅ Development dependencies already installed in .venv/"

# Code formatting
format: .venv
	@echo "🎨 Formatting code..."
	@source .venv/bin/activate && black .
	@source .venv/bin/activate && isort .

# Linting
lint: .venv
	@echo "🔍 Running linters..."
	@source .venv/bin/activate && ruff check .
	@source .venv/bin/activate && mypy src/

# Environment check
check-env: .venv
	@echo "🔍 Checking Swift development environment..."
	@source .venv/bin/activate && python3 -c "import sys; sys.path.insert(0, 'src'); from tools.swift_check_environment import swift_check_environment; print(swift_check_environment())"

# Clean up cache files
clean:
	@echo "🧹 Cleaning up cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name "*.pyc" -delete

# Clean up virtual environment
clean-venv:
	@echo "🧹 Removing virtual environment..."
	rm -rf .venv