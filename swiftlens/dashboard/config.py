"""
Configuration management for Swift Context MCP Dashboard
Supports environment variables, config files, and defaults
"""

import json
import os
from pathlib import Path


class DashboardConfig:
    """Configuration management for the dashboard"""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        """Load configuration from multiple sources in priority order"""
        # Default values
        self.host = "localhost"
        self.port = 53729
        self.db_path = self._get_default_db_path()
        self.connection_pool_size = 10
        self.websocket_timeout = 1.0
        self.log_retention_days = 30

        # Load from config file if it exists
        self._load_from_file()

        # Override with environment variables
        self._load_from_env()

    def _get_default_db_path(self) -> str:
        """Get default database path in a suitable location"""
        # Use user's home directory or temp directory for database
        if os.name == "nt":  # Windows
            base_dir = Path.home() / "AppData" / "Local" / "SwiftContextMCP"
        else:  # Unix-like (macOS, Linux)
            base_dir = Path.home() / ".swift-context-mcp"

        base_dir.mkdir(parents=True, exist_ok=True)
        return str(base_dir / "dashboard_logs.db")

    def _load_from_file(self):
        """Load configuration from config.json if it exists"""
        config_paths = [
            Path("config.json"),
            Path.home() / ".swift-context-mcp" / "config.json",
            Path("/etc/swift-context-mcp/config.json"),
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config_data = json.load(f)
                        dashboard_config = config_data.get("dashboard", {})

                        self.host = dashboard_config.get("host", self.host)
                        self.port = dashboard_config.get("port", self.port)
                        self.db_path = dashboard_config.get("db_path", self.db_path)
                        self.connection_pool_size = dashboard_config.get(
                            "connection_pool_size", self.connection_pool_size
                        )
                        self.websocket_timeout = dashboard_config.get(
                            "websocket_timeout", self.websocket_timeout
                        )
                        self.log_retention_days = dashboard_config.get(
                            "log_retention_days", self.log_retention_days
                        )
                        break
                except (OSError, json.JSONDecodeError):
                    continue

    def _load_from_env(self):
        """Load configuration from environment variables"""
        self.host = os.getenv("DASHBOARD_HOST", self.host)
        self.port = int(os.getenv("DASHBOARD_PORT", str(self.port)))
        self.db_path = os.getenv("DASHBOARD_DB_PATH", self.db_path)
        self.connection_pool_size = int(
            os.getenv("DASHBOARD_POOL_SIZE", str(self.connection_pool_size))
        )
        self.websocket_timeout = float(
            os.getenv("DASHBOARD_WS_TIMEOUT", str(self.websocket_timeout))
        )
        self.log_retention_days = int(
            os.getenv("DASHBOARD_LOG_RETENTION", str(self.log_retention_days))
        )

    def to_dict(self) -> dict:
        """Export configuration as dictionary"""
        return {
            "host": self.host,
            "port": self.port,
            "db_path": self.db_path,
            "connection_pool_size": self.connection_pool_size,
            "websocket_timeout": self.websocket_timeout,
            "log_retention_days": self.log_retention_days,
        }

    def save_to_file(self, config_path: str | None = None):
        """Save current configuration to file"""
        if config_path is None:
            config_dir = Path.home() / ".swift-context-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"

        config_data = {"dashboard": self.to_dict()}

        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)


# Global configuration instance
_config_instance = None


def get_dashboard_config() -> DashboardConfig:
    """Get the global dashboard configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = DashboardConfig()
    return _config_instance


def reload_config():
    """Reload configuration from sources"""
    global _config_instance
    _config_instance = DashboardConfig()
    return _config_instance
