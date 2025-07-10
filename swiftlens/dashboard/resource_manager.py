"""
Centralized resource management for Swift Context MCP Dashboard
Coordinates cleanup between logger and web server
"""

import atexit
import signal
import sys
import threading
import time


class DashboardResourceManager:
    """Centralized resource manager for dashboard components"""

    def __init__(self):
        self._logger = None
        self._server = None
        self._shutdown_in_progress = False
        self._shutdown_lock = threading.Lock()
        self._register_cleanup_handlers()

    def _register_cleanup_handlers(self):
        """Register cleanup handlers for various shutdown scenarios"""
        # Register atexit handler
        atexit.register(self.cleanup_all)

        # Register signal handlers for graceful shutdown
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._signal_handler)
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.cleanup_all()
        sys.exit(0)

    def register_logger(self, logger):
        """Register the dashboard logger for cleanup coordination"""
        self._logger = logger

    def register_server(self, server):
        """Register the dashboard server for cleanup coordination"""
        self._server = server

    def cleanup_all(self):
        """Cleanup all registered resources in proper order"""
        with self._shutdown_lock:
            if self._shutdown_in_progress:
                return

            self._shutdown_in_progress = True

            try:
                try:
                    print("🛑 Shutting down Swift Context MCP Dashboard...")
                except (ValueError, OSError):
                    pass

                # 1. Stop accepting new connections first
                if self._server:
                    try:
                        print("   Stopping web server...")
                    except (ValueError, OSError):
                        pass
                    self._server.stop_server()

                # 2. Give a moment for ongoing requests to complete
                time.sleep(0.5)

                # 3. Shutdown logger and database connections
                if self._logger:
                    try:
                        print("   Closing database connections...")
                    except (ValueError, OSError):
                        pass
                    self._logger.shutdown()

                try:
                    print("✅ Dashboard shutdown complete")
                except (ValueError, OSError):
                    pass

            except Exception as e:
                try:
                    print(f"⚠️  Error during shutdown: {e}")
                except (ValueError, OSError):
                    # Handle cases where stdout/stderr are closed during shutdown
                    pass
            finally:
                self._shutdown_in_progress = False

    def is_shutdown_in_progress(self) -> bool:
        """Check if shutdown is currently in progress"""
        return self._shutdown_in_progress

    def get_status(self) -> dict:
        """Get status of managed resources"""
        return {
            "logger_registered": self._logger is not None,
            "server_registered": self._server is not None,
            "server_running": self._server.is_running() if self._server else False,
            "shutdown_in_progress": self._shutdown_in_progress,
        }


# Global resource manager instance
_resource_manager = None


def get_resource_manager() -> DashboardResourceManager:
    """Get the global resource manager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = DashboardResourceManager()
    return _resource_manager


def register_dashboard_logger(logger):
    """Register logger with resource manager"""
    manager = get_resource_manager()
    manager.register_logger(logger)


def register_dashboard_server(server):
    """Register server with resource manager"""
    manager = get_resource_manager()
    manager.register_server(server)


def shutdown_dashboard():
    """Initiate graceful shutdown of all dashboard components"""
    manager = get_resource_manager()
    manager.cleanup_all()
