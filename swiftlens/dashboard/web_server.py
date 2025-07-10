"""
FastAPI web server for Swift Context MCP Server Dashboard
Provides REST API and WebSocket endpoints for real-time monitoring
"""

import asyncio
import logging
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_dashboard_config
from .logger import get_dashboard_logger
from .resource_manager import register_dashboard_server


class DashboardServer:
    """Web server for the Swift Context MCP Dashboard"""

    def __init__(self, host: str = None, port: int = None):
        config = get_dashboard_config()
        self.host = host or config.host
        self.port = port or config.port
        self.config = config
        self.app = FastAPI(
            title="Swift Context MCP Dashboard",
            description="Real-time monitoring dashboard for Swift Context MCP Server",
            version="1.0.0",
        )
        self.logger = get_dashboard_logger()
        self.server_thread: threading.Thread | None = None
        self.server_process = None
        self._setup_routes()
        self._setup_middleware()
        self._setup_static_files()

    def _setup_middleware(self):
        """Setup CORS and other middleware"""
        # SECURITY: Restrict CORS to localhost only to prevent CSRF attacks
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                f"http://localhost:{self.port}",
                f"http://127.0.0.1:{self.port}",
                "http://localhost:53729",  # Default port
                "http://127.0.0.1:53729",  # Default port
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    def _setup_static_files(self):
        """Setup static file serving for dashboard UI"""
        # Create static directory if it doesn't exist
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)

        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _setup_routes(self):
        """Setup all API routes"""

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_root():
            """Serve the main dashboard page"""
            static_dir = Path(__file__).parent / "static"
            index_file = static_dir / "index.html"

            if index_file.exists():
                return HTMLResponse(content=index_file.read_text(), status_code=200)
            else:
                return HTMLResponse(content=self._get_default_dashboard_html(), status_code=200)

        @self.app.get("/dashboard", response_class=HTMLResponse)
        async def dashboard_page():
            """Serve the dashboard page (alternative route)"""
            return await dashboard_root()

        @self.app.get("/api/logs")
        async def get_logs(
            limit: int = Query(100, ge=1, le=1000),
            offset: int = Query(0, ge=0),
            tool_name: str | None = Query(None),
            session_id: str | None = Query(None),
        ):
            """Get logs with optional filtering"""
            try:
                logs = self.logger.get_logs(
                    limit=limit,
                    offset=offset,
                    tool_name=tool_name,
                    session_id=session_id,
                )
                return JSONResponse(content={"logs": logs, "count": len(logs)})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/api/sessions")
        async def get_sessions():
            """Get all sessions"""
            try:
                sessions = self.logger.get_sessions()
                return JSONResponse(content={"sessions": sessions})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/api/statistics")
        async def get_statistics():
            """Get dashboard statistics"""
            try:
                stats = self.logger.get_statistics()
                return JSONResponse(content=stats)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            return JSONResponse(
                content={
                    "status": "healthy",
                    "server": "Swift Context MCP Dashboard",
                    "version": "1.0.0",
                }
            )

        @self.app.post("/api/shutdown")
        async def shutdown_server():
            """Shutdown the MCP server gracefully"""
            try:
                # Schedule shutdown in background
                asyncio.create_task(self._delayed_shutdown())
                return JSONResponse(content={"message": "Server shutdown initiated"})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time log updates"""
            await websocket.accept()
            self.logger.register_websocket(websocket)

            try:
                # Send initial data
                await websocket.send_json(
                    {
                        "type": "connected",
                        "message": "Connected to Swift Context MCP Dashboard",
                    }
                )

                # Keep connection alive and handle messages
                while True:
                    try:
                        data = await websocket.receive_json()
                        # Handle client messages if needed
                        if data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": str(e)})

            except WebSocketDisconnect:
                pass
            finally:
                self.logger.unregister_websocket(websocket)

    async def _delayed_shutdown(self):
        """Delayed shutdown to allow response to be sent"""
        await asyncio.sleep(1)
        if self.server_process:
            self.server_process.should_exit = True

    def _get_default_dashboard_html(self) -> str:
        """Get default dashboard HTML when static files are not available"""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Swift Context MCP Dashboard</title>
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
                h1 {
                    color: #333;
                    margin-bottom: 20px;
                }
                .status {
                    padding: 10px 20px;
                    background-color: #e7f3ff;
                    border: 1px solid #b3d9ff;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }
                .info {
                    color: #666;
                    line-height: 1.6;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Swift Context MCP Dashboard</h1>
                <div class="status">
                    <strong>Dashboard is running!</strong> Static files are being served.
                </div>
                <div class="info">
                    <p>The Swift Context MCP Server dashboard is now running on port 53729.</p>
                    <p>This is a placeholder page. The full dashboard interface will be available once the static files are properly configured.</p>
                    <p><strong>Available API endpoints:</strong></p>
                    <ul>
                        <li><a href="/api/health">/api/health</a> - Health check</li>
                        <li><a href="/api/statistics">/api/statistics</a> - Server statistics</li>
                        <li><a href="/api/logs">/api/logs</a> - Recent logs</li>
                        <li><a href="/api/sessions">/api/sessions</a> - Active sessions</li>
                        <li><code>/ws</code> - WebSocket for real-time updates</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

    def start_server(self):
        """Start the dashboard server in a background thread"""
        if self.server_thread and self.server_thread.is_alive():
            return

        def run_server():
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False,
            )
            self.server_process = uvicorn.Server(config)
            asyncio.run(self.server_process.serve())

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        logging.info(f"Swift Context MCP Dashboard started on http://{self.host}:{self.port}")

    def stop_server(self):
        """Stop the dashboard server"""
        if self.server_process:
            self.server_process.should_exit = True

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

        try:
            logging.info("Swift Context MCP Dashboard stopped")
        except (ValueError, OSError):
            # Handle cases where stdout/stderr are closed during shutdown
            pass

    def is_running(self) -> bool:
        """Check if the server is running"""
        return (
            self.server_thread is not None
            and self.server_thread.is_alive()
            and self.server_process is not None
            and not self.server_process.should_exit
        )


# Global server instance
_server_instance = None


def get_dashboard_server() -> DashboardServer:
    """Get the global dashboard server instance"""
    global _server_instance
    if _server_instance is None:
        _server_instance = DashboardServer()
        register_dashboard_server(_server_instance)
    return _server_instance


def start_dashboard_server():
    """Start the global dashboard server"""
    server = get_dashboard_server()
    server.start_server()


def stop_dashboard_server():
    """Stop the global dashboard server"""
    server = get_dashboard_server()
    server.stop_server()


def is_dashboard_running() -> bool:
    """Check if the dashboard server is running"""
    global _server_instance
    if _server_instance is None:
        return False
    return _server_instance.is_running()
