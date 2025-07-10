"""
Client-side dashboard proxy for SwiftLens MCP Server

This module provides a local web server that serves the dashboard interface
for monitoring MCP client connections. It reuses existing dashboard static files
while running locally on the client machine for security.
"""

import asyncio
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .connection_state import MCPConnectionState


def find_available_port(preferred_port: int, max_attempts: int = 100) -> int:
    """Find an available port starting from the preferred port.

    Args:
        preferred_port: The preferred port to start checking from
        max_attempts: Maximum number of ports to try before giving up

    Returns:
        An available port number

    Raises:
        OSError: If no available port is found within max_attempts
    """
    import socket

    for attempt in range(max_attempts):
        port_to_try = preferred_port + attempt

        # Skip reserved ports (below 1024) and high ports (above 65535)
        if port_to_try < 1024 or port_to_try > 65535:
            continue

        try:
            # Try to bind to the port to check if it's available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port_to_try))
                return port_to_try
        except OSError:
            # Port is in use, try the next one
            continue

    raise OSError(
        f"No available port found after trying {max_attempts} ports starting from {preferred_port}"
    )


class DashboardProxy:
    """Local web server providing dashboard interface for MCP client connections"""

    def __init__(self, host: str = "127.0.0.1", port: int = 53729, auto_find_port: bool = True):
        # SECURITY: Always bind to localhost only
        self.host = "127.0.0.1"  # Never allow 0.0.0.0
        self.requested_port = port

        # Find available port if auto_find_port is enabled
        if auto_find_port:
            try:
                self.port = find_available_port(port)
                self.port_was_changed = self.port != port
            except OSError:
                # Fall back to requested port and let server startup handle the error
                self.port = port
                self.port_was_changed = False
        else:
            self.port = port
            self.port_was_changed = False

        self.app = FastAPI(
            title="SwiftLens Client Dashboard",
            description="Client-side monitoring dashboard for SwiftLens MCP connections",
            version="1.0.0",
        )

        # Connection state tracking
        self.connections: dict[str, MCPConnectionState] = {}
        self.websockets: list[WebSocket] = []

        # Test environment detection to disable threading during testing
        self._is_test_environment = self._detect_test_environment()

        # Server management
        self.server_thread: threading.Thread | None = None
        self.server_process = None
        self.is_running = False

        self._setup_routes()
        self._setup_middleware()
        self._setup_static_files()

    def _detect_test_environment(self) -> bool:
        """Detect if we're running in a test environment to disable threading."""
        import os
        import sys

        # Environment variable override - can force disable dashboard
        if os.environ.get("SWIFTLENS_DISABLE_DASHBOARD", "").lower() in ("1", "true", "yes"):
            return True

        # Check for pytest execution
        if "pytest" in sys.modules:
            return True

        # Check for test-related environment variables
        if any(var in os.environ for var in ["PYTEST_CURRENT_TEST", "TESTING", "TEST_MODE"]):
            return True

        # Check for test-related command line arguments
        if any("test" in arg.lower() for arg in sys.argv):
            return True

        # Check for common test framework indicators
        test_indicators = ["pytest", "unittest", "test_", "_test", "conftest"]
        if any(indicator in " ".join(sys.argv).lower() for indicator in test_indicators):
            return True

        # Check if current working directory contains test-related patterns
        cwd = os.getcwd()
        if any(pattern in cwd.lower() for pattern in ["test", "tests"]):
            return True

        return False

    def _setup_middleware(self):
        """Setup CORS and other middleware"""
        # SECURITY: Restrict CORS to localhost only
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                f"http://localhost:{self.port}",
                f"http://127.0.0.1:{self.port}",
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    def _setup_static_files(self):
        """Setup static file serving using existing dashboard files"""
        # Use existing dashboard static files
        dashboard_static = Path(__file__).parent.parent / "dashboard" / "static"

        if dashboard_static.exists():
            self.app.mount("/static", StaticFiles(directory=str(dashboard_static)), name="static")

    def _setup_routes(self):
        """Setup all API routes"""

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_root():
            """Serve the main dashboard page"""
            return HTMLResponse(content=self._get_client_dashboard_html(), status_code=200)

        @self.app.get("/dashboard", response_class=HTMLResponse)
        async def dashboard_page():
            """Alternative dashboard route"""
            return await dashboard_root()

        @self.app.get("/api/connections")
        async def get_connections():
            """Get all MCP connections"""
            connections_data = {}
            for conn_id, connection in self.connections.items():
                connections_data[conn_id] = connection.get_statistics()
            return JSONResponse(content={"connections": connections_data})

        @self.app.get("/api/logs")
        async def get_logs(
            limit: int = Query(100, ge=1, le=1000),
            connection_id: str = Query(None),
            level: str = Query(None),
        ):
            """Get logs from all or specific connections"""
            all_logs = []

            for conn_id, connection in self.connections.items():
                if connection_id and conn_id != connection_id:
                    continue

                conn_logs = connection.get_recent_logs(limit=limit, level_filter=level)
                # Add connection info to each log
                for log in conn_logs:
                    log["connection_id"] = conn_id
                    log["server_url"] = connection.server_url
                all_logs.extend(conn_logs)

            # Sort by timestamp (most recent first)
            all_logs.sort(key=lambda x: x["timestamp"], reverse=True)

            # Apply limit to combined results
            if limit:
                all_logs = all_logs[:limit]

            return JSONResponse(content={"logs": all_logs, "count": len(all_logs)})

        @self.app.get("/api/tool-calls")
        async def get_tool_calls(
            limit: int = Query(50, ge=1, le=500),
            connection_id: str = Query(None),
        ):
            """Get tool calls from all or specific connections"""
            all_calls = []

            for conn_id, connection in self.connections.items():
                if connection_id and conn_id != connection_id:
                    continue

                conn_calls = connection.get_recent_tool_calls(limit=limit)
                # Add connection info to each call
                for call in conn_calls:
                    call["connection_id"] = conn_id
                    call["server_url"] = connection.server_url
                all_calls.extend(conn_calls)

            # Sort by timestamp (most recent first)
            all_calls.sort(key=lambda x: x["timestamp"], reverse=True)

            # Apply limit to combined results
            if limit:
                all_calls = all_calls[:limit]

            return JSONResponse(content={"tool_calls": all_calls, "count": len(all_calls)})

        @self.app.get("/api/statistics")
        async def get_statistics():
            """Get dashboard statistics"""
            total_connections = len(self.connections)
            active_connections = len(
                [c for c in self.connections.values() if c.status == "connected"]
            )
            total_tool_calls = sum(c.total_tool_calls for c in self.connections.values())
            total_successful = sum(c.successful_calls for c in self.connections.values())
            total_failed = sum(c.failed_calls for c in self.connections.values())

            success_rate = (
                (total_successful / total_tool_calls * 100) if total_tool_calls > 0 else 0
            )

            return JSONResponse(
                content={
                    "total_connections": total_connections,
                    "active_connections": active_connections,
                    "total_tool_calls": total_tool_calls,
                    "successful_calls": total_successful,
                    "failed_calls": total_failed,
                    "success_rate": round(success_rate, 2),
                    "uptime": time.time() - getattr(self, "start_time", time.time()),
                }
            )

        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            return JSONResponse(
                content={
                    "status": "healthy",
                    "service": "SwiftLens Client Dashboard",
                    "version": "1.0.0",
                    "connections": len(self.connections),
                }
            )

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.websockets.append(websocket)

            try:
                # Send initial data
                await websocket.send_json(
                    {
                        "type": "connected",
                        "message": "Connected to SwiftLens Client Dashboard",
                        "connections": len(self.connections),
                    }
                )

                # Keep connection alive
                while True:
                    try:
                        data = await websocket.receive_json()
                        if data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": str(e)})

            except WebSocketDisconnect:
                pass
            finally:
                if websocket in self.websockets:
                    self.websockets.remove(websocket)

    def _get_client_dashboard_html(self) -> str:
        """Get client dashboard HTML"""
        # Try to use existing dashboard HTML
        dashboard_static = Path(__file__).parent.parent / "dashboard" / "static"
        index_file = dashboard_static / "index.html"

        if index_file.exists():
            # Read existing HTML and modify title for client version
            html_content = index_file.read_text()
            # Update title to indicate this is client-side
            html_content = html_content.replace(
                "Swift Context MCP Dashboard", "SwiftLens Client Dashboard"
            )
            return html_content

        # Fallback HTML if static files not available
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SwiftLens Client Dashboard</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 8px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #e0e0e0;
                }
                h1 {
                    color: #333;
                    margin: 0;
                }
                .status {
                    padding: 10px 20px;
                    background-color: #e7f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }
                .connections {
                    display: grid;
                    gap: 20px;
                    margin-top: 20px;
                }
                .connection-card {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 20px;
                    background: #fafafa;
                }
                .connection-status {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .status-connected { background: #d4edda; color: #155724; }
                .status-connecting { background: #fff3cd; color: #856404; }
                .status-disconnected { background: #f8d7da; color: #721c24; }
                .info { color: #666; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SwiftLens Client Dashboard</h1>
                    <div id="connection-count">0 connections</div>
                </div>

                <div class="status">
                    <strong>Client Dashboard Active!</strong> Monitoring MCP connections locally.
                </div>

                <div class="info">
                    <p>This is the client-side dashboard for SwiftLens MCP connections.</p>
                    <p><strong>Available API endpoints:</strong></p>
                    <ul>
                        <li><a href="/api/health">/api/health</a> - Health check</li>
                        <li><a href="/api/connections">/api/connections</a> - Connection status</li>
                        <li><a href="/api/statistics">/api/statistics</a> - Dashboard statistics</li>
                        <li><a href="/api/logs">/api/logs</a> - Recent logs</li>
                        <li><a href="/api/tool-calls">/api/tool-calls</a> - Tool call history</li>
                        <li><code>/ws</code> - WebSocket for real-time updates</li>
                    </ul>
                </div>

                <div id="connections" class="connections">
                    <p>No active connections. Start an MCP client to see connections here.</p>
                </div>
            </div>

            <script>
                // Simple client-side updates
                async function updateDashboard() {
                    try {
                        const response = await fetch('/api/connections');
                        const data = await response.json();
                        const connections = data.connections;

                        document.getElementById('connection-count').textContent =
                            Object.keys(connections).length + ' connections';

                        const connectionsDiv = document.getElementById('connections');
                        if (Object.keys(connections).length === 0) {
                            connectionsDiv.innerHTML = '<p>No active connections. Start an MCP client to see connections here.</p>';
                        } else {
                            connectionsDiv.innerHTML = Object.entries(connections).map(([id, conn]) => `
                                <div class="connection-card">
                                    <h3>${conn.server_url}</h3>
                                    <div class="connection-status status-${conn.status}">${conn.status}</div>
                                    <p>Tool calls: ${conn.total_tool_calls} (${conn.successful_calls} successful)</p>
                                    <p>Uptime: ${Math.round(conn.uptime_seconds)}s</p>
                                </div>
                            `).join('');
                        }
                    } catch (e) {
                        console.error('Failed to update dashboard:', e);
                    }
                }

                // Update every 2 seconds
                setInterval(updateDashboard, 2000);
                updateDashboard();
            </script>
        </body>
        </html>
        """

    def add_connection(self, connection: MCPConnectionState):
        """Add a new MCP connection to monitor"""
        self.connections[connection.connection_id] = connection
        self._broadcast_update(
            "connection_added",
            {
                "connection_id": connection.connection_id,
                "server_url": connection.server_url,
                "status": connection.status,
            },
        )

    def remove_connection(self, connection_id: str):
        """Remove an MCP connection from monitoring"""
        if connection_id in self.connections:
            connection = self.connections.pop(connection_id)
            self._broadcast_update(
                "connection_removed",
                {
                    "connection_id": connection_id,
                    "server_url": connection.server_url,
                },
            )

    def _broadcast_update(self, update_type: str, data: dict):
        """Broadcast update to all connected WebSocket clients"""
        if not self.websockets:
            return

        message = {
            "type": update_type,
            "data": data,
            "timestamp": time.time(),
        }

        # Remove disconnected websockets
        disconnected = []
        for ws in self.websockets:
            try:
                asyncio.create_task(ws.send_json(message))
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            if ws in self.websockets:
                self.websockets.remove(ws)

    def start_server(self, open_browser: bool = True):
        """Start the dashboard server in a separate thread.

        This method sets up the server but delegates the actual serving to
        the serve() coroutine to avoid asyncio.run() conflicts with test frameworks.
        """
        if self.is_running:
            return

        # Skip dashboard in test environments to prevent threading issues
        if self._is_test_environment:
            print("📊 Dashboard disabled during testing to prevent threading conflicts")
            self.is_running = False  # Keep as False to indicate it's not really running
            return

        # Additional failsafe - check test environment again at startup time
        if self._detect_test_environment():
            print("📊 Dashboard startup blocked - test environment detected at runtime")
            self.is_running = False
            return

        self.start_time = time.time()

        # Show port change message if port was changed during discovery
        if self.port_was_changed:
            print(f"🔄 Port {self.requested_port} in use, using port {self.port} instead")

        def run_server():
            # Final failsafe - prevent asyncio.run during tests
            import os

            if os.environ.get("SWIFTLENS_DISABLE_DASHBOARD", "").lower() in ("1", "true", "yes"):
                print("📊 Dashboard server thread blocked by environment variable")
                return

            # Additional test environment check in thread context
            if "pytest" in __import__("sys").modules:
                print("📊 Dashboard server thread blocked - pytest detected")
                return

            # Use asyncio.new_event_loop() instead of asyncio.run() to avoid conflicts
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.serve())
            finally:
                loop.close()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True

        dashboard_url = f"http://{self.host}:{self.port}"
        print(f"🌐 SwiftLens Client Dashboard started on {dashboard_url}")

        if open_browser:
            # Wait a moment for server to start, then open browser
            threading.Timer(1.0, lambda: webbrowser.open(dashboard_url)).start()

    async def serve(self):
        """Coroutine that runs the uvicorn server.

        This method contains the actual server logic, separated from start_server()
        to avoid asyncio.run() conflicts with test frameworks like pytest.
        """
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",  # Reduce noise
            access_log=False,
        )
        self.server_process = uvicorn.Server(config)
        await self.server_process.serve()

    def stop_server(self):
        """Stop the dashboard server"""
        if not self.is_running:
            return

        self.is_running = False

        if self.server_process:
            self.server_process.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

        print("🛑 SwiftLens Client Dashboard stopped")

    def get_url(self) -> str:
        """Get the dashboard URL"""
        return f"http://{self.host}:{self.port}"
