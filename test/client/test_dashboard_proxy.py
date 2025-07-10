"""
Tests for DashboardProxy class
"""

from unittest.mock import Mock, patch

import pytest

from swiftlens.client.connection_state import MCPConnectionState
from swiftlens.client.dashboard_proxy import DashboardProxy


class TestDashboardProxy:
    """Test DashboardProxy class"""

    def test_dashboard_proxy_initialization(self):
        """Test dashboard proxy initialization"""
        dashboard = DashboardProxy(port=8888, auto_find_port=False)

        # Security: should always bind to localhost
        assert dashboard.host == "127.0.0.1"
        assert dashboard.port == 8888
        assert dashboard.connections == {}
        assert dashboard.websockets == []
        assert not dashboard.is_running

    def test_security_localhost_only(self):
        """Test that dashboard always binds to localhost for security"""
        # Try to set different host - should be overridden for security
        dashboard = DashboardProxy(host="0.0.0.0", port=8889, auto_find_port=False)

        # Security: should always be localhost
        assert dashboard.host == "127.0.0.1"

    def test_add_connection(self):
        """Test adding MCP connections"""
        dashboard = DashboardProxy(port=8890)
        connection = MCPConnectionState("https://test-server.com", "test-conn-1")

        with patch.object(dashboard, "_broadcast_update") as mock_broadcast:
            dashboard.add_connection(connection)

        assert "test-conn-1" in dashboard.connections
        assert dashboard.connections["test-conn-1"] == connection

        # Verify broadcast was called
        mock_broadcast.assert_called_once_with(
            "connection_added",
            {
                "connection_id": "test-conn-1",
                "server_url": "https://test-server.com",
                "status": "connecting",
            },
        )

    def test_remove_connection(self):
        """Test removing MCP connections"""
        dashboard = DashboardProxy(port=8891)
        connection = MCPConnectionState("https://test-server.com", "test-conn-2")
        dashboard.connections["test-conn-2"] = connection

        with patch.object(dashboard, "_broadcast_update") as mock_broadcast:
            dashboard.remove_connection("test-conn-2")

        assert "test-conn-2" not in dashboard.connections

        # Verify broadcast was called
        mock_broadcast.assert_called_once_with(
            "connection_removed",
            {
                "connection_id": "test-conn-2",
                "server_url": "https://test-server.com",
            },
        )

    def test_get_url(self):
        """Test getting dashboard URL"""
        dashboard = DashboardProxy(port=8892, auto_find_port=False)
        url = dashboard.get_url()

        assert url == "http://127.0.0.1:8892"

    @pytest.mark.asyncio
    async def test_api_endpoints_basic(self):
        """Test basic API endpoints without starting server"""
        dashboard = DashboardProxy(port=8893)

        # Add test connections
        conn1 = MCPConnectionState("https://server1.com", "conn1")
        conn1.update_status("connected")
        conn2 = MCPConnectionState("https://server2.com", "conn2")
        conn2.update_status("connecting")

        dashboard.connections["conn1"] = conn1
        dashboard.connections["conn2"] = conn2

        # Test connections endpoint logic
        connections_data = {}
        for conn_id, connection in dashboard.connections.items():
            connections_data[conn_id] = connection.get_statistics()

        assert len(connections_data) == 2
        assert "conn1" in connections_data
        assert "conn2" in connections_data
        assert connections_data["conn1"]["status"] == "connected"
        assert connections_data["conn2"]["status"] == "connecting"

    def test_cors_security_setup(self):
        """Test CORS security configuration"""
        dashboard = DashboardProxy(port=8894)

        # Check that CORS middleware is configured
        cors_middleware = None
        for middleware in dashboard.app.user_middleware:
            if hasattr(middleware, "cls") and "CORS" in str(middleware.cls):
                cors_middleware = middleware
                break

        # Should have CORS middleware configured
        assert cors_middleware is not None

    def test_static_files_setup(self):
        """Test static files configuration"""
        dashboard = DashboardProxy(port=8895)

        # Check that static files are mounted
        routes = dashboard.app.routes
        static_routes = [
            route for route in routes if hasattr(route, "path") and route.path == "/static"
        ]

        # Should have static file mounting
        assert len(static_routes) > 0

    def test_fallback_html_generation(self):
        """Test fallback HTML generation"""
        dashboard = DashboardProxy(port=8896)

        # Mock the static files to not exist to force fallback
        with patch("pathlib.Path.exists", return_value=False):
            html = dashboard._get_client_dashboard_html()

        assert "SwiftLens Client Dashboard" in html
        assert "<!DOCTYPE html>" in html
        assert "/api/health" in html
        assert "/api/connections" in html
        assert "connection-count" in html

    @patch("webbrowser.open")
    @patch("threading.Timer")
    def test_start_server_browser_opening(self, mock_timer, mock_browser, real_dashboard):
        """Test server start with browser opening"""
        # real_dashboard fixture activates real dashboard functionality
        dashboard = DashboardProxy(port=8897)

        # Override test environment detection to allow dashboard to start
        dashboard._detect_test_environment = Mock(return_value=False)
        dashboard._is_test_environment = False

        with patch.object(dashboard, "server_thread") as mock_thread:
            mock_thread.start = Mock()
            dashboard.server_thread = Mock()
            dashboard.server_thread.start = Mock()

            dashboard.start_server(open_browser=True)

            # Should schedule browser opening
            mock_timer.assert_called_once()
            timer_call = mock_timer.call_args
            assert (
                timer_call[0][0] == 1.0
            )  # 1 second delay  # 1 second delay  # 1 second delay  # 1 second delay  # 1 second delay

    def test_stop_server(self):
        """Test server shutdown"""
        dashboard = DashboardProxy(port=8898)

        # Mock server components
        dashboard.is_running = True
        dashboard.server_process = Mock()
        dashboard.server_thread = Mock()
        dashboard.server_thread.is_alive.return_value = True

        dashboard.stop_server()

        assert not dashboard.is_running
        assert dashboard.server_process.should_exit is True
        dashboard.server_thread.join.assert_called_once_with(timeout=5)

    def test_broadcast_update_empty_websockets(self):
        """Test broadcast with no websockets connected"""
        dashboard = DashboardProxy(port=8899)

        # Should not raise error with empty websockets list
        dashboard._broadcast_update("test_event", {"data": "test"})

        # Should complete without issues
        assert len(dashboard.websockets) == 0

    def test_broadcast_update_with_websockets(self):
        """Test broadcast with mock websockets"""
        dashboard = DashboardProxy(port=8900)

        # Add mock websockets
        mock_ws1 = Mock()
        mock_ws2 = Mock()
        mock_ws2.send_json.side_effect = Exception("Disconnected")  # Simulate disconnection

        dashboard.websockets = [mock_ws1, mock_ws2]

        dashboard._broadcast_update("test_event", {"data": "test"})

        # Should remove the disconnected websocket
        assert mock_ws2 not in dashboard.websockets

    def test_multiple_dashboard_instances(self):
        """Test that multiple dashboard instances can be created with different ports"""
        dashboard1 = DashboardProxy(port=8901)
        dashboard2 = DashboardProxy(port=8902)

        assert dashboard1.port == 8901
        assert dashboard2.port == 8902
        assert dashboard1.get_url() != dashboard2.get_url()

    def test_connection_statistics_aggregation(self):
        """Test aggregation of connection statistics"""
        dashboard = DashboardProxy(port=8903)

        # Add connections with various states
        conn1 = MCPConnectionState("https://server1.com", "conn1")
        conn1.update_status("connected")
        conn1.total_tool_calls = 10
        conn1.successful_calls = 8
        conn1.failed_calls = 2

        conn2 = MCPConnectionState("https://server2.com", "conn2")
        conn2.update_status("connected")
        conn2.total_tool_calls = 5
        conn2.successful_calls = 5
        conn2.failed_calls = 0

        conn3 = MCPConnectionState("https://server3.com", "conn3")
        conn3.update_status("disconnected")

        dashboard.connections = {"conn1": conn1, "conn2": conn2, "conn3": conn3}

        # Calculate expected statistics
        total_connections = 3
        active_connections = 2  # conn1 and conn2 are connected
        total_tool_calls = 15
        total_successful = 13
        total_failed = 2
        expected_success_rate = round(13 / 15 * 100, 2)

        # Verify the logic that would be used in the API endpoint
        actual_total_connections = len(dashboard.connections)
        actual_active_connections = len(
            [c for c in dashboard.connections.values() if c.status == "connected"]
        )
        actual_total_tool_calls = sum(c.total_tool_calls for c in dashboard.connections.values())
        actual_total_successful = sum(c.successful_calls for c in dashboard.connections.values())
        actual_total_failed = sum(c.failed_calls for c in dashboard.connections.values())
        actual_success_rate = (
            round(actual_total_successful / actual_total_tool_calls * 100, 2)
            if actual_total_tool_calls > 0
            else 0
        )

        assert actual_total_connections == total_connections
        assert actual_active_connections == active_connections
        assert actual_total_tool_calls == total_tool_calls
        assert actual_total_successful == total_successful
        assert actual_total_failed == total_failed
        assert actual_success_rate == expected_success_rate

    def test_port_discovery_functionality(self):
        """Test automatic port discovery when requested port is in use"""
        from unittest.mock import patch

        # Mock socket.bind to simulate port 8900 being in use, but 8901 available
        def mock_bind_side_effect(address):
            host, port = address
            if port == 8900:
                # Simulate "Address already in use" for port 8900
                raise OSError(48, "Address already in use")
            else:
                # Allow binding on any other port
                return None

        with patch("socket.socket.bind") as mock_bind:
            mock_bind.side_effect = mock_bind_side_effect

            # Now try to create dashboard with port 8900 - should auto-discover next port
            dashboard = DashboardProxy(port=8900, auto_find_port=True)

            # Should have found port 8901 instead
            assert dashboard.requested_port == 8900
            assert dashboard.port == 8901
            assert dashboard.port_was_changed is True

    def test_port_discovery_disabled(self):
        """Test that port discovery can be disabled"""
        dashboard = DashboardProxy(port=8902, auto_find_port=False)

        # Should use exact port requested
        assert dashboard.requested_port == 8902
        assert dashboard.port == 8902
        assert dashboard.port_was_changed is False

    def test_find_available_port_function(self):
        """Test the find_available_port utility function"""
        from unittest.mock import patch

        from swiftlens.client.dashboard_proxy import find_available_port

        # Test finding first available port (no conflicts)
        with patch("socket.socket.bind") as mock_bind:
            mock_bind.return_value = None  # Success on first try
            port = find_available_port(8903)
            assert port == 8903
            mock_bind.assert_called_once()

        # Test with port in use - should skip 8904 and find 8905
        def mock_bind_side_effect(address):
            host, port = address
            if port == 8904:
                # Simulate "Address already in use" for port 8904
                raise OSError(48, "Address already in use")
            else:
                # Allow binding on any other port
                return None

        with patch("socket.socket.bind") as mock_bind:
            mock_bind.side_effect = mock_bind_side_effect
            port = find_available_port(8904)
            assert port == 8905  # Should skip 8904 and find 8905

            # Should have tried port 8904 first, then 8905
            assert mock_bind.call_count == 2  # Should skip 8904 and find 8905

    def test_find_available_port_error_handling(self):
        """Test error handling when no ports are available"""
        import pytest

        from swiftlens.client.dashboard_proxy import find_available_port

        # Test by starting with a port that will quickly go out of range
        # The function skips ports above 65535, so with max_attempts=1 starting from 65536 should fail
        with pytest.raises(OSError, match="No available port found"):
            find_available_port(
                65536, max_attempts=1
            )  # 65536 is above valid range  # Only check 65534, 65535 might not be in range  # Only 65535 left, but we need valid ports

    def test_dashboard_start_with_port_change_message(self, capsys, real_dashboard):
        """Test that port change message is displayed when port is changed"""
        from unittest.mock import patch

        # Mock socket.bind to simulate port 8906 being in use, but 8907 available
        def mock_bind_side_effect(address):
            host, port = address
            if port == 8906:
                # Simulate "Address already in use" for port 8906
                raise OSError(48, "Address already in use")
            else:
                # Allow binding on any other port
                return None

        with patch("socket.socket.bind") as mock_bind:
            mock_bind.side_effect = mock_bind_side_effect

            # Create dashboard that will need to change ports
            dashboard = DashboardProxy(port=8906, auto_find_port=True)

            # Verify port was changed during initialization
            assert dashboard.port == 8907
            assert dashboard.port_was_changed is True

            # real_dashboard fixture activates real dashboard functionality
            # Override test environment detection to allow dashboard to start
            dashboard._detect_test_environment = Mock(return_value=False)
            dashboard._is_test_environment = False

            # Mock the server start to avoid actually starting it
            with (
                patch.object(dashboard, "server_thread"),
                patch.object(dashboard, "server_process"),
                patch("threading.Timer"),
            ):
                dashboard.start_server(open_browser=False)

                # Check that port change message was printed
                captured = capsys.readouterr()
                assert "🔄 Port 8906 in use, using port 8907 instead" in captured.out
                assert (
                    "🌐 SwiftLens Client Dashboard started on http://127.0.0.1:8907" in captured.out
                )
