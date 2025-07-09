"""
Connection state management for client-side dashboard

This module provides classes to track and manage MCP connection states
for the client-side dashboard monitoring interface.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Represents a single tool call made through the MCP connection"""

    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


@dataclass
class LogEntry:
    """Represents a log entry for dashboard display"""

    level: str  # info, warning, error, debug
    message: str
    timestamp: float = field(default_factory=time.time)
    tool_name: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "level": self.level,
            "message": self.message,
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "session_id": self.session_id,
        }


class MCPConnectionState:
    """Tracks the state of a single MCP server connection"""

    def __init__(self, server_url: str, connection_id: str = None):
        self.server_url = server_url
        self.connection_id = connection_id or str(uuid.uuid4())
        self.connected_at = time.time()
        self.last_activity = time.time()
        self.status = "connecting"  # connecting, connected, disconnected, error
        self.error_message: str | None = None

        # Track tool calls and logs
        self.tool_calls: list[ToolCall] = []
        self.logs: list[LogEntry] = []

        # Connection statistics
        self.total_tool_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.average_response_time = 0.0

        # Add initial connection log
        self.add_log("info", f"Initializing connection to {server_url}")

    def update_status(self, status: str, error_message: str = None):
        """Update connection status"""
        old_status = self.status
        self.status = status
        self.error_message = error_message
        self.last_activity = time.time()

        # Log status changes
        if status != old_status:
            if status == "connected":
                self.add_log("info", "Successfully connected to MCP server")
            elif status == "disconnected":
                self.add_log("warning", "Disconnected from MCP server")
            elif status == "error":
                self.add_log("error", f"Connection error: {error_message}")

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> ToolCall:
        """Add a new tool call and return the ToolCall object for updating"""
        tool_call = ToolCall(tool_name=tool_name, arguments=arguments)
        self.tool_calls.append(tool_call)
        self.total_tool_calls += 1
        self.last_activity = time.time()

        # Log the tool call
        self.add_log("info", f"Calling tool: {tool_name}", tool_name=tool_name)

        return tool_call

    def complete_tool_call(
        self, tool_call: ToolCall, result: dict[str, Any] = None, error: str = None
    ):
        """Complete a tool call with result or error"""
        start_time = tool_call.timestamp
        tool_call.duration_ms = (time.time() - start_time) * 1000

        if error:
            tool_call.error = error
            self.failed_calls += 1
            self.add_log(
                "error",
                f"Tool call failed: {tool_call.tool_name} - {error}",
                tool_name=tool_call.tool_name,
            )
        else:
            tool_call.result = result
            self.successful_calls += 1
            self.add_log(
                "info",
                f"Tool call completed: {tool_call.tool_name}",
                tool_name=tool_call.tool_name,
            )

        # Update average response time
        total_time = sum(tc.duration_ms for tc in self.tool_calls if tc.duration_ms)
        completed_calls = len([tc for tc in self.tool_calls if tc.duration_ms])
        if completed_calls > 0:
            self.average_response_time = total_time / completed_calls

    def add_log(self, level: str, message: str, tool_name: str = None):
        """Add a log entry"""
        log_entry = LogEntry(
            level=level,
            message=message,
            tool_name=tool_name,
            session_id=self.connection_id,
        )
        self.logs.append(log_entry)

        # Keep only last 1000 log entries to prevent memory issues
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]

    def get_recent_tool_calls(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent tool calls as dictionaries"""
        recent_calls = self.tool_calls[-limit:] if limit else self.tool_calls
        return [tc.to_dict() for tc in recent_calls]

    def get_recent_logs(self, limit: int = 100, level_filter: str = None) -> list[dict[str, Any]]:
        """Get recent logs as dictionaries, optionally filtered by level"""
        logs = self.logs

        if level_filter:
            logs = [log for log in logs if log.level == level_filter]

        recent_logs = logs[-limit:] if limit else logs
        return [log.to_dict() for log in recent_logs]

    def get_statistics(self) -> dict[str, Any]:
        """Get connection statistics"""
        uptime = time.time() - self.connected_at
        success_rate = (
            (self.successful_calls / self.total_tool_calls * 100)
            if self.total_tool_calls > 0
            else 0
        )

        return {
            "connection_id": self.connection_id,
            "server_url": self.server_url,
            "status": self.status,
            "uptime_seconds": uptime,
            "total_tool_calls": self.total_tool_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(success_rate, 2),
            "average_response_time_ms": round(self.average_response_time, 2),
            "last_activity": self.last_activity,
            "error_message": self.error_message,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert entire connection state to dictionary"""
        return {
            "connection_info": self.get_statistics(),
            "recent_tool_calls": self.get_recent_tool_calls(20),
            "recent_logs": self.get_recent_logs(50),
        }
