"""
Tests for MCP client functionality
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from swiftlens.client.mcp_client import (
    MCPClientManager,
    MCPClientWithDashboard,
    connect_with_dashboard,
    start_client_dashboard,
)


class TestMCPClientWithDashboard:
    """Test MCPClientWithDashboard class"""

    def test_client_initialization(self):
        """Test client initialization"""
        client = MCPClientWithDashboard("https://test-server.com")

        assert client.server_url == "https://test-server.com"
        assert client.dashboard is None
        assert not client.is_connected
        assert client.connection_state.server_url == "https://test-server.com"

    def test_client_initialization_with_dashboard(self):
        """Test client initialization with dashboard"""
        mock_dashboard = Mock()
        mock_dashboard.add_connection = Mock()

        client = MCPClientWithDashboard("https://test-server.com", dashboard=mock_dashboard)

        assert client.dashboard == mock_dashboard
        mock_dashboard.add_connection.assert_called_once_with(client.connection_state)

    @pytest.mark.asyncio
    async def test_connect_missing_httpx(self):
        """Test connection failure when httpx is not available"""
        client = MCPClientWithDashboard("https://test-server.com")

        with patch("swiftlens.client.mcp_client.httpx", None):
            with pytest.raises(ImportError, match="httpx is required"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection"""
        client = MCPClientWithDashboard("https://test-server.com")

        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_http_client.get.return_value = mock_response

        with patch("swiftlens.client.mcp_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http_client

            result = await client.connect()

        assert result is True
        assert client.is_connected is True
        assert client.connection_state.status == "connected"
        assert client.http_client == mock_http_client

    @pytest.mark.asyncio
    async def test_connect_health_check_failure_but_fallback_success(self):
        """Test connection with health check failure but fallback success"""
        client = MCPClientWithDashboard("https://test-server.com")

        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = Exception("Health check failed")

        with patch("swiftlens.client.mcp_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http_client

            result = await client.connect()

        # Should fallback to basic connection test and succeed
        assert result is True
        assert client.is_connected is True
        assert client.connection_state.status == "connected"

    @pytest.mark.asyncio
    async def test_connect_complete_failure(self):
        """Test complete connection failure"""
        client = MCPClientWithDashboard("https://test-server.com")

        with patch("swiftlens.client.mcp_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.side_effect = Exception("Connection failed")

            result = await client.connect()

        assert result is False
        assert client.is_connected is False
        assert client.connection_state.status == "error"
        assert "Connection failed" in client.connection_state.error_message

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection"""
        client = MCPClientWithDashboard("https://test-server.com")
        mock_dashboard = Mock()
        mock_dashboard.remove_connection = Mock()
        client.dashboard = mock_dashboard

        # Mock connected state
        client.is_connected = True
        client.http_client = AsyncMock()
        client.connection_state.update_status("connected")

        await client.disconnect()

        assert not client.is_connected
        assert client.http_client is None
        assert client.connection_state.status == "disconnected"
        mock_dashboard.remove_connection.assert_called_once_with(
            client.connection_state.connection_id
        )

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Test tool call when not connected"""
        client = MCPClientWithDashboard("https://test-server.com")

        with pytest.raises(Exception, match="Not connected to MCP server"):
            await client.call_tool("swift_analyze_file", {"file_path": "test.swift"})

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool call"""
        client = MCPClientWithDashboard("https://test-server.com")
        client.is_connected = True

        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "result": "test result"}
        mock_http_client.post.return_value = mock_response
        client.http_client = mock_http_client

        result = await client.call_tool("swift_analyze_file", {"file_path": "test.swift"})

        assert result == {"success": True, "result": "test result"}
        assert client.connection_state.total_tool_calls == 1
        assert client.connection_state.successful_calls == 1
        assert client.connection_state.failed_calls == 0

    @pytest.mark.asyncio
    async def test_call_tool_http_error(self):
        """Test tool call with HTTP error"""
        client = MCPClientWithDashboard("https://test-server.com")
        client.is_connected = True

        mock_http_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_http_client.post.return_value = mock_response
        client.http_client = mock_http_client

        with pytest.raises(Exception, match="HTTP 500"):
            await client.call_tool("swift_analyze_file", {"file_path": "test.swift"})

        assert client.connection_state.total_tool_calls == 1
        assert client.connection_state.successful_calls == 0
        assert client.connection_state.failed_calls == 1

    @pytest.mark.asyncio
    async def test_simulate_tool_call_success(self):
        """Test simulated tool call success"""
        client = MCPClientWithDashboard("https://test-server.com")

        with patch("random.random", return_value=0.5):  # Ensures success (< 0.9)
            result = await client.simulate_tool_call(
                "swift_analyze_file", {"file_path": "test.swift"}, delay=0.01
            )

        assert result["success"] is True
        assert result["tool"] == "swift_analyze_file"
        assert "result" in result
        assert client.connection_state.total_tool_calls == 1
        assert client.connection_state.successful_calls == 1

    @pytest.mark.asyncio
    async def test_simulate_tool_call_failure(self):
        """Test simulated tool call failure"""
        client = MCPClientWithDashboard("https://test-server.com")

        with patch("random.random", return_value=0.95):  # Ensures failure (>= 0.9)
            with pytest.raises(Exception, match="Simulated error"):
                await client.simulate_tool_call(
                    "swift_analyze_file", {"file_path": "test.swift"}, delay=0.01
                )

        assert client.connection_state.total_tool_calls == 1
        assert client.connection_state.failed_calls == 1

    def test_get_connection_info(self):
        """Test getting connection information"""
        client = MCPClientWithDashboard("https://test-server.com")

        info = client.get_connection_info()

        assert isinstance(info, dict)
        assert info["server_url"] == "https://test-server.com"
        assert "connection_id" in info
        assert "status" in info


class TestMCPClientManager:
    """Test MCPClientManager class"""

    @pytest.mark.skip(reason="Requires real dashboard setup")
    def test_manager_initialization_with_dashboard(self, real_dashboard):
        """Test manager initialization with dashboard enabled"""
        with patch("swiftlens.client.mcp_client.DashboardProxy") as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.start_server = Mock()
            mock_dashboard_class.return_value = mock_dashboard

            # Use real dashboard fixture to bypass test environment protection
            with real_dashboard():
                manager = MCPClientManager(
                    enable_dashboard=True, dashboard_port=8999, auto_find_port=False
                )

        assert manager.enable_dashboard is True
        assert manager.dashboard == mock_dashboard
        mock_dashboard.start_server.assert_called_once()
        assert manager.clients == {}

    def test_manager_initialization_without_dashboard(self):
        """Test manager initialization with dashboard disabled"""
        manager = MCPClientManager(enable_dashboard=False)

        assert manager.enable_dashboard is False
        assert manager.dashboard is None
        assert manager.clients == {}

    @pytest.mark.asyncio
    async def test_connect_to_server_success(self):
        """Test successful server connection"""
        manager = MCPClientManager(enable_dashboard=False)

        with patch("swiftlens.client.mcp_client.MCPClientWithDashboard") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = True
            mock_client_class.return_value = mock_client

            client = await manager.connect_to_server("https://test-server.com")

        assert client == mock_client
        assert "https://test-server.com" in manager.clients
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_to_server_failure(self):
        """Test failed server connection"""
        manager = MCPClientManager(enable_dashboard=False)

        with patch("swiftlens.client.mcp_client.MCPClientWithDashboard") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect.return_value = False
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="Failed to connect"):
                await manager.connect_to_server("https://test-server.com")

        assert "https://test-server.com" not in manager.clients

    @pytest.mark.asyncio
    async def test_disconnect_from_server(self):
        """Test disconnecting from specific server"""
        manager = MCPClientManager(enable_dashboard=False)

        mock_client = AsyncMock()
        manager.clients["test-server"] = mock_client

        await manager.disconnect_from_server("test-server")

        mock_client.disconnect.assert_called_once()
        assert "test-server" not in manager.clients

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Test disconnecting from all servers"""
        manager = MCPClientManager(enable_dashboard=False)

        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        manager.clients = {"server1": mock_client1, "server2": mock_client2}

        await manager.disconnect_all()

        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()
        assert manager.clients == {}

    def test_get_client(self):
        """Test getting specific client"""
        manager = MCPClientManager(enable_dashboard=False)

        mock_client = Mock()
        manager.clients["test-server"] = mock_client

        result = manager.get_client("test-server")
        assert result == mock_client

        result = manager.get_client("nonexistent")
        assert result is None

    def test_list_connections(self):
        """Test listing all connections"""
        manager = MCPClientManager(enable_dashboard=False)

        mock_client1 = Mock()
        mock_client1.server_url = "https://server1.com"
        mock_client1.is_connected = True
        mock_client1.get_connection_info.return_value = {"status": "connected"}

        mock_client2 = Mock()
        mock_client2.server_url = "https://server2.com"
        mock_client2.is_connected = False
        mock_client2.get_connection_info.return_value = {"status": "disconnected"}

        manager.clients = {"server1": mock_client1, "server2": mock_client2}

        connections = manager.list_connections()

        assert len(connections) == 2
        assert connections[0]["connection_id"] == "server1"
        assert connections[0]["server_url"] == "https://server1.com"
        assert connections[0]["is_connected"] is True
        assert connections[1]["connection_id"] == "server2"
        assert connections[1]["is_connected"] is False

    @pytest.mark.asyncio
    async def test_simulate_activity_no_clients(self):
        """Test activity simulation with no clients"""
        manager = MCPClientManager(enable_dashboard=False)

        # Should not raise an error
        await manager.simulate_activity(iterations=1)

    @pytest.mark.asyncio
    async def test_simulate_activity_with_clients(self):
        """Test activity simulation with connected clients"""
        manager = MCPClientManager(enable_dashboard=False)

        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.server_url = "https://test-server.com"
        mock_client.simulate_tool_call = AsyncMock()

        manager.clients = {"test-server": mock_client}

        with (
            patch("random.choice") as mock_choice,
            patch("random.uniform", return_value=0.1),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_choice.return_value = "swift_analyze_file"

            await manager.simulate_activity(iterations=2)

        # Should have called simulate_tool_call for each iteration
        assert mock_client.simulate_tool_call.call_count == 2

    def test_get_dashboard_url_with_dashboard(self):
        """Test getting dashboard URL when dashboard is enabled"""
        with patch("swiftlens.client.mcp_client.DashboardProxy") as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.start_server = Mock()
            mock_dashboard.get_url.return_value = "http://127.0.0.1:53729"
            mock_dashboard_class.return_value = mock_dashboard

            manager = MCPClientManager(enable_dashboard=True, auto_find_port=False)
            url = manager.get_dashboard_url()

        assert url == "http://127.0.0.1:53729"

    def test_get_dashboard_url_without_dashboard(self):
        """Test getting dashboard URL when dashboard is disabled"""
        manager = MCPClientManager(enable_dashboard=False)
        url = manager.get_dashboard_url()

        assert url is None

    def test_stop_dashboard(self):
        """Test stopping dashboard"""
        with patch("swiftlens.client.mcp_client.DashboardProxy") as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.start_server = Mock()
            mock_dashboard.stop_server = Mock()
            mock_dashboard_class.return_value = mock_dashboard

            manager = MCPClientManager(enable_dashboard=True, auto_find_port=False)
            manager.stop_dashboard()

        mock_dashboard.stop_server.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions"""

    @pytest.mark.asyncio
    async def test_connect_with_dashboard(self):
        """Test connect_with_dashboard convenience function"""
        with (
            patch("swiftlens.client.mcp_client.DashboardProxy") as mock_dashboard_class,
            patch("swiftlens.client.mcp_client.MCPClientWithDashboard") as mock_client_class,
        ):
            mock_dashboard = Mock()
            mock_dashboard.start_server = Mock()
            mock_dashboard_class.return_value = mock_dashboard

            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await connect_with_dashboard("https://test-server.com", dashboard_port=8888)

        mock_dashboard_class.assert_called_once_with(port=8888, auto_find_port=True)
        mock_dashboard.start_server.assert_called_once()
        mock_client_class.assert_called_once_with(
            "https://test-server.com", dashboard=mock_dashboard
        )
        mock_client.connect.assert_called_once()
        assert result == mock_client

    def test_start_client_dashboard(self):
        """Test start_client_dashboard convenience function"""
        with patch("swiftlens.client.mcp_client.DashboardProxy") as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.start_server = Mock()
            mock_dashboard_class.return_value = mock_dashboard

            result = start_client_dashboard(port=8888, open_browser=False, auto_find_port=False)

        mock_dashboard_class.assert_called_once_with(port=8888, auto_find_port=False)
        mock_dashboard.start_server.assert_called_once_with(open_browser=False)
        assert result == mock_dashboard
