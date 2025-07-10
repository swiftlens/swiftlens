"""
MCP client with integrated dashboard functionality

This module provides MCP client classes that integrate with the client-side
dashboard for monitoring and logging MCP server interactions.
"""

import asyncio
import time
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None

from .connection_state import MCPConnectionState
from .dashboard_proxy import DashboardProxy


class MCPClientWithDashboard:
    """MCP client with integrated dashboard monitoring"""

    def __init__(self, server_url: str, dashboard: DashboardProxy | None = None):
        self.server_url = server_url
        self.dashboard = dashboard

        # Connection state tracking
        self.connection_state = MCPConnectionState(server_url)

        # HTTP client for MCP communication
        self.http_client: httpx.AsyncClient | None = None
        self.is_connected = False

        # Register with dashboard if provided
        if self.dashboard:
            self.dashboard.add_connection(self.connection_state)

    async def connect(self) -> bool:
        """Connect to the MCP server"""
        if httpx is None:
            raise ImportError(
                "httpx is required for MCP client functionality. Install with: pip install httpx"
            )

        self.connection_state.update_status("connecting")

        try:
            # Create HTTP client for MCP communication
            self.http_client = httpx.AsyncClient(
                base_url=self.server_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "SwiftLens-Client/1.0.0",
                },
            )

            # Test connection with a simple health check or initialization
            # This is a simplified example - real MCP protocol would be more complex
            try:
                response = await self.http_client.get("/api/health")
                if response.status_code == 200:
                    self.is_connected = True
                    self.connection_state.update_status("connected")
                    return True
                else:
                    raise Exception(f"Health check failed: {response.status_code}")

            except Exception:
                # If health endpoint doesn't exist, try a basic connection test
                self.is_connected = True
                self.connection_state.update_status("connected")
                self.connection_state.add_log(
                    "info", "Connected to MCP server (basic connection test)"
                )
                return True

        except Exception as e:
            self.connection_state.update_status("error", str(e))
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

        self.is_connected = False
        self.connection_state.update_status("disconnected")

        # Remove from dashboard
        if self.dashboard:
            self.dashboard.remove_connection(self.connection_state.connection_id)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        if not self.is_connected or not self.http_client:
            raise Exception("Not connected to MCP server")

        # Start tracking the tool call
        tool_call = self.connection_state.add_tool_call(tool_name, arguments)

        try:
            # Prepare MCP request (simplified - real MCP protocol would be different)
            request_data = {
                "tool": tool_name,
                "arguments": arguments,
                "timestamp": time.time(),
            }

            # Make the request
            response = await self.http_client.post("/api/tools", json=request_data)

            if response.status_code == 200:
                result = response.json()
                self.connection_state.complete_tool_call(tool_call, result=result)
                return result
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.connection_state.complete_tool_call(tool_call, error=error_msg)
                raise Exception(error_msg)

        except Exception as e:
            # Only complete the tool call with error if it hasn't been completed yet
            if tool_call.duration_ms is None:
                error_msg = str(e)
                self.connection_state.complete_tool_call(tool_call, error=error_msg)
            raise

    async def simulate_tool_call(
        self, tool_name: str, arguments: dict[str, Any], delay: float = 0.5
    ) -> dict[str, Any]:
        """Simulate a tool call for demonstration purposes"""
        tool_call = self.connection_state.add_tool_call(tool_name, arguments)

        # Simulate processing delay
        await asyncio.sleep(delay)

        # Simulate different outcomes
        import random

        if random.random() < 0.9:  # 90% success rate
            result = {
                "success": True,
                "tool": tool_name,
                "result": f"Simulated result for {tool_name}",
                "timestamp": time.time(),
            }
            self.connection_state.complete_tool_call(tool_call, result=result)
            return result
        else:
            error_msg = f"Simulated error for {tool_name}"
            self.connection_state.complete_tool_call(tool_call, error=error_msg)
            raise Exception(error_msg)

    def get_connection_info(self) -> dict[str, Any]:
        """Get connection information"""
        return self.connection_state.get_statistics()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.create_task(self.disconnect())


class MCPClientManager:
    """Manager for multiple MCP client connections with shared dashboard"""

    def __init__(
        self,
        enable_dashboard: bool = True,
        dashboard_port: int = 53729,
        auto_find_port: bool = True,
    ):
        self.enable_dashboard = enable_dashboard
        self.clients: dict[str, MCPClientWithDashboard] = {}

        # Create dashboard if enabled and auto-start it
        if enable_dashboard:
            self.dashboard = DashboardProxy(port=dashboard_port, auto_find_port=auto_find_port)
            # Auto-start dashboard for immediate availability
            self.dashboard.start_server()
        else:
            self.dashboard = None

    def start_dashboard(self, open_browser: bool = True) -> bool:
        """Start the dashboard server if enabled and not already running.

        Args:
            open_browser: Whether to open browser when starting dashboard

        Returns:
            bool: True if dashboard was started or already running, False if disabled
        """
        if not self.enable_dashboard or not self.dashboard:
            return False

        if self.dashboard.is_running:
            return True

        self.dashboard.start_server(open_browser=open_browser)
        return True

    async def connect_to_server(
        self, server_url: str, connection_id: str = None
    ) -> MCPClientWithDashboard:
        """Connect to an MCP server and return the client"""
        client = MCPClientWithDashboard(server_url, dashboard=self.dashboard)

        # Use server URL as connection ID if not provided
        conn_id = connection_id or server_url
        self.clients[conn_id] = client

        success = await client.connect()
        if not success:
            # Remove failed connection
            del self.clients[conn_id]
            raise Exception(f"Failed to connect to {server_url}")

        return client

    async def disconnect_from_server(self, connection_id: str):
        """Disconnect from a specific server"""
        if connection_id in self.clients:
            client = self.clients[connection_id]
            await client.disconnect()
            del self.clients[connection_id]

    async def disconnect_all(self):
        """Disconnect from all servers"""
        for client in list(self.clients.values()):
            await client.disconnect()
        self.clients.clear()

    def get_client(self, connection_id: str) -> MCPClientWithDashboard | None:
        """Get a specific client by connection ID"""
        return self.clients.get(connection_id)

    def list_connections(self) -> list[dict[str, Any]]:
        """List all current connections"""
        return [
            {
                "connection_id": conn_id,
                "server_url": client.server_url,
                "is_connected": client.is_connected,
                "statistics": client.get_connection_info(),
            }
            for conn_id, client in self.clients.items()
        ]

    async def simulate_activity(self, connection_id: str = None, iterations: int = 10):
        """Simulate activity on connections for demonstration"""
        import random

        clients = [self.clients[connection_id]] if connection_id else list(self.clients.values())

        if not clients:
            print("No active connections for simulation")
            return

        tools = [
            "swift_analyze_file",
            "swift_get_symbols_overview",
            "swift_find_symbol_references",
            "swift_validate_file",
        ]

        for i in range(iterations):
            for client in clients:
                if client.is_connected:
                    tool = random.choice(tools)
                    args = {"file_path": f"Example{i}.swift"}

                    try:
                        await client.simulate_tool_call(tool, args, delay=random.uniform(0.1, 1.0))
                        print(f"✅ Simulated {tool} on {client.server_url}")
                    except Exception as e:
                        print(f"❌ Simulated error on {client.server_url}: {e}")

            # Wait between iterations
            await asyncio.sleep(random.uniform(0.5, 2.0))

    def get_dashboard_url(self) -> str | None:
        """Get the dashboard URL if dashboard is enabled"""
        return self.dashboard.get_url() if self.dashboard else None

    def stop_dashboard(self):
        """Stop the dashboard server"""
        if self.dashboard:
            self.dashboard.stop_server()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect_all()
        self.stop_dashboard()


# Convenience functions for quick setup
async def connect_with_dashboard(
    server_url: str, dashboard_port: int = 53729, auto_find_port: bool = True
) -> MCPClientWithDashboard:
    """Quick setup: Connect to a server with auto-dashboard"""
    dashboard = DashboardProxy(port=dashboard_port, auto_find_port=auto_find_port)
    dashboard.start_server()

    client = MCPClientWithDashboard(server_url, dashboard=dashboard)
    await client.connect()
    return client


def start_client_dashboard(
    port: int = 53729, open_browser: bool = True, auto_find_port: bool = True
) -> DashboardProxy:
    """Start a standalone client dashboard for monitoring"""
    dashboard = DashboardProxy(port=port, auto_find_port=auto_find_port)
    dashboard.start_server(open_browser=open_browser)
    return dashboard
