#!/bin/bash

# SwiftLens MCP Server Wrapper Script
# This script ensures the virtual environment is activated before running the server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/.venv"
SERVER_PATH="$SCRIPT_DIR/src/server.py"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found. Creating one..." >&2
    python3 -m venv "$VENV_PATH"
    
    # Activate and install dependencies
    source "$VENV_PATH/bin/activate"
    pip install -r "$SCRIPT_DIR/requirements.txt" >&2
else
    # Just activate the existing environment
    source "$VENV_PATH/bin/activate"
    
    # Check if dependencies are installed, install if missing
    if ! python -c "import mcp, pydantic" 2>/dev/null; then
        echo "Installing missing dependencies..." >&2
        pip install -r "$SCRIPT_DIR/requirements.txt" >&2
    fi
fi

# Run the MCP server
exec python3 "$SERVER_PATH" "$@" 

echo "✅ SwiftLens MCP server is now running..."