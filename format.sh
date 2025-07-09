#!/bin/bash

# Swift Context MCP - Code Formatting Script
# Usage: ./format.sh [check|fix|--force] [--force]

set -e

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "🔧 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if ruff is available
if ! command -v ruff &> /dev/null; then
    echo "❌ ruff not found. Installing..."
    python3 -m pip install ruff
fi

# Parse arguments
ACTION=${1:-fix}
FORCE_MODE=false

# Check for --force flag in any position
for arg in "$@"; do
    if [ "$arg" = "--force" ]; then
        FORCE_MODE=true
        break
    fi
done

# If first argument is --force, set action to fix
if [ "$1" = "--force" ]; then
    ACTION="fix"
fi

echo "🚀 Running ruff formatter..."

if [ "$FORCE_MODE" = true ]; then
    echo "⚡ Force mode enabled - using unsafe fixes"
fi

if [ "$ACTION" = "check" ]; then
    echo "📋 Checking code formatting (dry run)..."
    
    # Check formatting without making changes
    echo "Format check:"
    ruff format --check .
    
    echo "Linting check:"
    if [ "$FORCE_MODE" = true ]; then
        ruff check . --unsafe-fixes
    else
        ruff check .
    fi
    
    echo "✅ Format check completed!"
    
elif [ "$ACTION" = "fix" ] || [ "$ACTION" = "format" ]; then
    echo "🔧 Formatting and fixing code..."
    
    # Format code
    echo "Formatting Python files..."
    ruff format .
    
    # Fix linting issues
    echo "Fixing linting issues..."
    if [ "$FORCE_MODE" = true ]; then
        ruff check --fix --unsafe-fixes .
    else
        ruff check --fix .
    fi
    
    echo "✅ Code formatting completed!"
    
else
    echo "❌ Unknown action: $ACTION"
    echo "Usage: $0 [check|fix|--force] [--force]"
    echo "  check  - Check formatting without making changes"
    echo "  fix    - Format and fix issues (default)"
    echo "  --force - Use ruff's unsafe fixes for aggressive formatting"
    echo ""
    echo "Examples:"
    echo "  $0           # Standard format and fix"
    echo "  $0 fix       # Standard format and fix"
    echo "  $0 check     # Check only without fixing"
    echo "  $0 --force   # Aggressive format with unsafe fixes"
    echo "  $0 fix --force # Same as above"
    echo "  $0 check --force # Check with unsafe fixes analysis"
    exit 1
fi

echo "🎉 Done!"