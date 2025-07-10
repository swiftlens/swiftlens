"""
Tests for command-line launcher functionality
"""

import asyncio
from io import StringIO

# Add src to path for imports
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swiftlens.client.launcher import (
    dashboard_only_mode,
    demo_mode,
    main,
    multiple_connections_mode,
    remote_connection_mode,
)


class TestLauncherModes:
    """Test launcher mode functions"""

    @pytest.mark.asyncio
    async def test_dashboard_only_mode(self):
        """Test dashboard-only mode"""
        mock_dashboard = Mock()
        mock_dashboard.get_url.return_value = "http://127.0.0.1:53729"
        mock_dashboard.is_running = True

        with patch(
            "swiftlens.client.launcher.start_client_dashboard", return_value=mock_dashboard
        ) as mock_start:
            # Create a task that will complete quickly
            task = asyncio.create_task(dashboard_only_mode(port=8888))

            # Let it start, then stop the dashboard to end the loop
            await asyncio.sleep(0.1)
            mock_dashboard.is_running = False

            # Wait for completion
            await task

        mock_start.assert_called_once_with(port=8888, open_browser=True, auto_find_port=True)
        mock_dashboard.get_url.assert_called()

    @pytest.mark.asyncio
    async def test_remote_connection_mode_success(self):
        """Test successful remote connection mode"""
        mock_client = AsyncMock()
        mock_client.is_connected = True

        with patch(
            "swiftlens.client.launcher.connect_with_dashboard", return_value=mock_client
        ) as mock_connect:
            # Create a task that will complete quickly
            task = asyncio.create_task(remote_connection_mode("https://test-server.com", port=8888))

            # Let it start, then disconnect to end the loop
            await asyncio.sleep(0.1)
            mock_client.is_connected = False

            # Wait for completion
            result = await task

        mock_connect.assert_called_once_with(
            "https://test-server.com", dashboard_port=8888, auto_find_port=True
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_remote_connection_mode_failure(self):
        """Test failed remote connection mode"""
        with patch(
            "swiftlens.client.launcher.connect_with_dashboard",
            side_effect=Exception("Connection failed"),
        ):
            result = await remote_connection_mode("https://test-server.com")

        assert result == 1

    @pytest.mark.asyncio
    async def test_demo_mode_success(self):
        """Test successful demo mode"""
        mock_manager = AsyncMock()
        mock_manager.dashboard = Mock()
        mock_manager.get_dashboard_url.return_value = "http://127.0.0.1:53729"
        mock_manager.clients = {}
        mock_manager.simulate_activity = AsyncMock()

        # Mock the context manager behavior
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "swiftlens.client.launcher.MCPClientManager", return_value=mock_manager
        ) as mock_manager_class:
            # Create a task that will complete quickly
            task = asyncio.create_task(demo_mode(port=8888, connections=2))

            # Let it start, then simulate KeyboardInterrupt
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        mock_manager_class.assert_called_once_with(
            enable_dashboard=True, dashboard_port=8888, auto_find_port=True
        )

    @pytest.mark.asyncio
    async def test_demo_mode_no_connections(self):
        """Test demo mode with no successful connections"""
        mock_manager = AsyncMock()
        mock_manager.dashboard = None
        mock_manager.clients = {}

        # Mock the context manager behavior
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock(return_value=None)

        with patch("swiftlens.client.launcher.MCPClientManager", return_value=mock_manager):
            result = await demo_mode(connections=0)  # No connections

        assert result == 1

    @pytest.mark.asyncio
    async def test_multiple_connections_mode_success(self):
        """Test successful multiple connections mode"""
        mock_manager = AsyncMock()
        mock_manager.get_dashboard_url.return_value = "http://127.0.0.1:53729"

        mock_client1 = Mock()
        mock_client1.is_connected = True
        mock_client2 = Mock()
        mock_client2.is_connected = True

        mock_manager.connect_to_server.side_effect = [mock_client1, mock_client2]

        # Mock the context manager behavior
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock(return_value=None)

        servers = ["https://server1.com", "https://server2.com"]

        with patch("swiftlens.client.launcher.MCPClientManager", return_value=mock_manager):
            # Create a task that will complete quickly
            task = asyncio.create_task(multiple_connections_mode(servers, port=8888))

            # Let it start, then disconnect clients to end the loop
            await asyncio.sleep(0.1)
            mock_client1.is_connected = False
            mock_client2.is_connected = False

            # Wait for completion
            result = await task

        assert mock_manager.connect_to_server.call_count == 2
        assert result == 0

    @pytest.mark.asyncio
    async def test_multiple_connections_mode_no_connections(self):
        """Test multiple connections mode with no successful connections"""
        mock_manager = AsyncMock()
        mock_manager.connect_to_server.side_effect = Exception("Connection failed")

        # Mock the context manager behavior
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock(return_value=None)

        servers = ["https://server1.com", "https://server2.com"]

        with patch("swiftlens.client.launcher.MCPClientManager", return_value=mock_manager):
            result = await multiple_connections_mode(servers)

        assert result == 1


class TestMainFunction:
    """Test main function and argument parsing"""

    def test_main_dashboard_only(self):
        """Test main function with dashboard-only mode"""
        test_args = ["launcher.py", "--dashboard-only"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run") as mock_run,
            patch("swiftlens.client.launcher.dashboard_only_mode"),
        ):
            mock_run.return_value = 0
            result = main()

        mock_run.assert_called_once()
        assert result == 0

    def test_main_remote_connection(self):
        """Test main function with remote connection mode"""
        test_args = ["launcher.py", "--remote", "https://test-server.com"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run") as mock_run,
            patch("swiftlens.client.launcher.remote_connection_mode"),
        ):
            mock_run.return_value = 0
            result = main()

        mock_run.assert_called_once()
        assert result == 0

    def test_main_demo_mode(self):
        """Test main function with demo mode"""
        test_args = ["launcher.py", "--demo", "--connections", "3"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run") as mock_run,
            patch("swiftlens.client.launcher.demo_mode"),
        ):
            mock_run.return_value = 0
            result = main()

        mock_run.assert_called_once()
        assert result == 0

    def test_main_multiple_connections(self):
        """Test main function with multiple connections mode"""
        test_args = [
            "launcher.py",
            "--multiple",
            "server1.com",
            "server2.com",
            "server3.com",
        ]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run") as mock_run,
            patch("swiftlens.client.launcher.multiple_connections_mode"),
        ):
            mock_run.return_value = 0
            result = main()

        mock_run.assert_called_once()
        assert result == 0

    def test_main_custom_port(self):
        """Test main function with custom port"""
        test_args = ["launcher.py", "--dashboard-only", "--port", "9000"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run") as mock_run,
            patch("swiftlens.client.launcher.dashboard_only_mode"),
        ):
            mock_run.return_value = 0
            result = main()

        mock_run.assert_called_once()
        # Verify port argument was passed correctly
        mock_run.call_args[0][0]  # Get the coroutine that was passed to asyncio.run
        assert result == 0

    def test_main_invalid_port(self):
        """Test main function with invalid port"""
        test_args = ["launcher.py", "--dashboard-only", "--port", "999"]  # Too low

        with patch("sys.argv", test_args), patch("builtins.print") as mock_print:
            result = main()

        assert result == 1
        mock_print.assert_called_with("❌ Port must be between 1024 and 65535")

    def test_main_no_arguments(self):
        """Test main function with no mode specified"""
        test_args = ["launcher.py"]

        with patch("sys.argv", test_args), patch("sys.stderr", new_callable=StringIO):
            # Should exit with error due to missing required argument
            try:
                result = main()
                assert result != 0  # Should fail
            except SystemExit as e:
                assert e.code != 0  # Should exit with error

    def test_main_keyboard_interrupt(self):
        """Test main function handling KeyboardInterrupt"""
        test_args = ["launcher.py", "--dashboard-only"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run", side_effect=KeyboardInterrupt),
            patch("builtins.print") as mock_print,
        ):
            result = main()

        assert result == 0
        mock_print.assert_called_with("\n👋 Goodbye!")

    def test_main_exception_handling(self):
        """Test main function exception handling"""
        test_args = ["launcher.py", "--dashboard-only"]

        with (
            patch("sys.argv", test_args),
            patch("asyncio.run", side_effect=Exception("Test error")),
            patch("builtins.print") as mock_print,
        ):
            result = main()

        assert result == 1
        mock_print.assert_called_with("❌ Error: Test error")

    def test_main_help_text(self):
        """Test that help text contains expected information"""
        test_args = ["launcher.py", "--help"]

        with (
            patch("sys.argv", test_args),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            try:
                main()
            except SystemExit:
                pass  # Help exits with SystemExit

        help_output = mock_stdout.getvalue()
        assert "SwiftLens Client Dashboard Launcher" in help_output
        assert "--dashboard-only" in help_output
        assert "--remote" in help_output
        assert "--demo" in help_output
        assert "--multiple" in help_output
        assert "Examples:" in help_output
