"""
Tests for MCPConnectionState class
"""

from unittest.mock import patch

from swiftlens.client.connection_state import LogEntry, MCPConnectionState, ToolCall


class TestToolCall:
    """Test ToolCall dataclass"""

    def test_tool_call_creation(self):
        """Test tool call creation with required fields"""
        tool_call = ToolCall(tool_name="swift_analyze_file", arguments={"file_path": "test.swift"})

        assert tool_call.tool_name == "swift_analyze_file"
        assert tool_call.arguments == {"file_path": "test.swift"}
        assert tool_call.result is None
        assert tool_call.error is None
        assert tool_call.duration_ms is None
        assert isinstance(tool_call.timestamp, float)

    def test_tool_call_to_dict(self):
        """Test tool call dictionary conversion"""
        tool_call = ToolCall(
            tool_name="swift_validate_file",
            arguments={"file_path": "example.swift"},
            result={"success": True},
            duration_ms=150.5,
        )

        result = tool_call.to_dict()

        assert result["tool_name"] == "swift_validate_file"
        assert result["arguments"] == {"file_path": "example.swift"}
        assert result["result"] == {"success": True}
        assert result["duration_ms"] == 150.5
        assert "timestamp" in result


class TestLogEntry:
    """Test LogEntry dataclass"""

    def test_log_entry_creation(self):
        """Test log entry creation"""
        log_entry = LogEntry(level="info", message="Test message", tool_name="swift_analyze_file")

        assert log_entry.level == "info"
        assert log_entry.message == "Test message"
        assert log_entry.tool_name == "swift_analyze_file"
        assert isinstance(log_entry.timestamp, float)

    def test_log_entry_to_dict(self):
        """Test log entry dictionary conversion"""
        log_entry = LogEntry(level="error", message="Test error message", session_id="test-session")

        result = log_entry.to_dict()

        assert result["level"] == "error"
        assert result["message"] == "Test error message"
        assert result["session_id"] == "test-session"
        assert "timestamp" in result


class TestMCPConnectionState:
    """Test MCPConnectionState class"""

    def test_connection_state_initialization(self):
        """Test connection state initialization"""
        state = MCPConnectionState("https://test-server.com")

        assert state.server_url == "https://test-server.com"
        assert state.status == "connecting"
        assert state.total_tool_calls == 0
        assert state.successful_calls == 0
        assert state.failed_calls == 0
        assert len(state.logs) == 1  # Initial connection log
        assert isinstance(state.connection_id, str)

    def test_connection_state_with_custom_id(self):
        """Test connection state with custom connection ID"""
        state = MCPConnectionState("https://test-server.com", "custom-id")

        assert state.connection_id == "custom-id"

    def test_update_status(self):
        """Test status updates"""
        state = MCPConnectionState("https://test-server.com")

        state.update_status("connected")
        assert state.status == "connected"
        assert state.error_message is None

        state.update_status("error", "Connection failed")
        assert state.status == "error"
        assert state.error_message == "Connection failed"

    def test_add_tool_call(self):
        """Test adding tool calls"""
        state = MCPConnectionState("https://test-server.com")

        tool_call = state.add_tool_call("swift_analyze_file", {"file_path": "test.swift"})

        assert state.total_tool_calls == 1
        assert len(state.tool_calls) == 1
        assert tool_call.tool_name == "swift_analyze_file"
        assert tool_call.arguments == {"file_path": "test.swift"}

    def test_complete_tool_call_success(self):
        """Test completing tool call with success"""
        state = MCPConnectionState("https://test-server.com")

        # Create tool call with manual timestamp to avoid time.time issues
        tool_call = ToolCall(
            tool_name="swift_analyze_file",
            arguments={"file_path": "test.swift"},
            timestamp=1000.0,
        )

        # Add to state manually
        state.tool_calls.append(tool_call)
        state.total_tool_calls += 1
        state.last_activity = 1000.0

        # Mock time.time for the completion
        with patch("time.time", return_value=1000.5):
            state.complete_tool_call(tool_call, result={"success": True})

        assert state.successful_calls == 1
        assert state.failed_calls == 0
        assert tool_call.result == {"success": True}
        assert tool_call.error is None
        assert tool_call.duration_ms == 500.0

    def test_complete_tool_call_error(self):
        """Test completing tool call with error"""
        state = MCPConnectionState("https://test-server.com")

        # Create tool call with manual timestamp to avoid time.time issues
        tool_call = ToolCall(
            tool_name="swift_analyze_file",
            arguments={"file_path": "test.swift"},
            timestamp=2000.0,
        )

        # Add to state manually
        state.tool_calls.append(tool_call)
        state.total_tool_calls += 1
        state.last_activity = 2000.0

        # Mock time.time for the completion
        with patch("time.time", return_value=2000.3):
            state.complete_tool_call(tool_call, error="File not found")

        assert state.successful_calls == 0
        assert state.failed_calls == 1
        assert tool_call.result is None
        assert tool_call.error == "File not found"
        assert abs(tool_call.duration_ms - 300.0) < 0.001

    def test_add_log(self):
        """Test adding log entries"""
        state = MCPConnectionState("https://test-server.com")
        initial_log_count = len(state.logs)

        state.add_log("info", "Test log message", "swift_analyze_file")

        assert len(state.logs) == initial_log_count + 1
        latest_log = state.logs[-1]
        assert latest_log.level == "info"
        assert latest_log.message == "Test log message"
        assert latest_log.tool_name == "swift_analyze_file"

    def test_log_rotation(self):
        """Test log rotation to prevent memory issues"""
        state = MCPConnectionState("https://test-server.com")

        # Add many logs to trigger rotation
        for i in range(1100):
            state.add_log("info", f"Log message {i}")

        # Should keep only last 1000 logs
        assert len(state.logs) == 1000
        # Check that newer logs are kept
        assert "Log message 1099" in state.logs[-1].message

    def test_get_recent_tool_calls(self):
        """Test getting recent tool calls"""
        state = MCPConnectionState("https://test-server.com")

        # Add several tool calls
        for i in range(5):
            tool_call = state.add_tool_call(f"tool_{i}", {"arg": i})
            state.complete_tool_call(tool_call, result={"value": i})

        recent_calls = state.get_recent_tool_calls(limit=3)

        assert len(recent_calls) == 3
        assert all(isinstance(call, dict) for call in recent_calls)
        assert recent_calls[-1]["arguments"]["arg"] == 4  # Most recent

    def test_get_recent_logs(self):
        """Test getting recent logs with filtering"""
        state = MCPConnectionState("https://test-server.com")

        # Add logs of different levels
        state.add_log("info", "Info message 1")
        state.add_log("error", "Error message 1")
        state.add_log("info", "Info message 2")
        state.add_log("warning", "Warning message 1")

        # Test getting all logs
        all_logs = state.get_recent_logs(limit=10)
        assert len(all_logs) >= 4  # At least our 4 logs plus initial connection log

        # Test filtering by level
        error_logs = state.get_recent_logs(limit=10, level_filter="error")
        assert len(error_logs) == 1
        assert error_logs[0]["level"] == "error"
        assert error_logs[0]["message"] == "Error message 1"

    def test_get_statistics(self):
        """Test getting connection statistics"""
        state = MCPConnectionState("https://test-server.com")

        # Add some activity
        tool_call1 = state.add_tool_call("tool1", {"arg": 1})
        state.complete_tool_call(tool_call1, result={"success": True})

        tool_call2 = state.add_tool_call("tool2", {"arg": 2})
        state.complete_tool_call(tool_call2, error="Failed")

        stats = state.get_statistics()

        assert stats["connection_id"] == state.connection_id
        assert stats["server_url"] == "https://test-server.com"
        assert stats["total_tool_calls"] == 2
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 1
        assert stats["success_rate"] == 50.0
        assert "uptime_seconds" in stats
        assert "average_response_time_ms" in stats

    def test_to_dict(self):
        """Test converting entire state to dictionary"""
        state = MCPConnectionState("https://test-server.com")

        # Add some activity
        tool_call = state.add_tool_call("swift_analyze_file", {"file_path": "test.swift"})
        state.complete_tool_call(tool_call, result={"success": True})

        result = state.to_dict()

        assert "connection_info" in result
        assert "recent_tool_calls" in result
        assert "recent_logs" in result

        # Verify structure
        assert isinstance(result["connection_info"], dict)
        assert isinstance(result["recent_tool_calls"], list)
        assert isinstance(result["recent_logs"], list)

        # Verify content
        assert result["connection_info"]["server_url"] == "https://test-server.com"
        assert len(result["recent_tool_calls"]) == 1
        assert result["recent_tool_calls"][0]["tool_name"] == "swift_analyze_file"
