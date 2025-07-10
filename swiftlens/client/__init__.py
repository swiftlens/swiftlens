"""
Client-side dashboard components for SwiftLens MCP Server

This module provides client-side dashboard functionality that allows developers
to monitor MCP server interactions locally without exposing web interfaces
in production environments.

Key Components:
- DashboardProxy: Local web server for dashboard interface
- MCPClientWithDashboard: MCP client with integrated dashboard
- MCPConnectionState: Connection state tracking
- Launcher: Command-line interface for testing and demos
"""

from .connection_state import MCPConnectionState
from .dashboard_proxy import DashboardProxy
from .mcp_client import MCPClientManager, MCPClientWithDashboard

__all__ = [
    "MCPConnectionState",
    "DashboardProxy",
    "MCPClientWithDashboard",
    "MCPClientManager",
]
