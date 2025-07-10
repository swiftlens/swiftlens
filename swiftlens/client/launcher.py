#!/usr/bin/env python3
"""
Command-line launcher for SwiftLens client-side dashboard

This module provides a command-line interface for testing and demonstrating
the client-side dashboard functionality with various modes.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.mcp_client import (
    MCPClientManager,
    connect_with_dashboard,
    start_client_dashboard,
)


async def dashboard_only_mode(port: int = 53729, auto_find_port: bool = True):
    """Start dashboard only for monitoring external connections"""
    print("🌐 Starting SwiftLens Client Dashboard in monitoring mode...")

    dashboard = start_client_dashboard(port=port, open_browser=True, auto_find_port=auto_find_port)

    print(f"Dashboard available at: {dashboard.get_url()}")
    print("Dashboard is ready to monitor MCP client connections.")
    print("Press Ctrl+C to stop...")

    try:
        # Keep the dashboard running
        while dashboard.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping dashboard...")
        dashboard.stop_server()


async def remote_connection_mode(server_url: str, port: int = 53729, auto_find_port: bool = True):
    """Connect to a remote MCP server with dashboard"""
    print(f"🔗 Connecting to remote MCP server: {server_url}")

    try:
        client = await connect_with_dashboard(
            server_url, dashboard_port=port, auto_find_port=auto_find_port
        )

        print(f"✅ Connected to {server_url}")
        print(f"Dashboard available at: {client.dashboard.get_url()}")
        print("Press Ctrl+C to disconnect...")

        # Keep connection alive and show some activity
        try:
            while client.is_connected:
                await asyncio.sleep(5)
                # You could add periodic heartbeat or status checks here

        except KeyboardInterrupt:
            print("\n🛑 Disconnecting...")
            await client.disconnect()

    except Exception as e:
        print(f"❌ Failed to connect to {server_url}: {e}")
        return 1

    return 0


async def demo_mode(port: int = 53729, connections: int = 2, auto_find_port: bool = True):
    """Demonstration mode with simulated MCP servers"""
    print(f"🎭 Starting demo mode with {connections} simulated connections...")

    async with MCPClientManager(
        enable_dashboard=True, dashboard_port=port, auto_find_port=auto_find_port
    ) as manager:
        # Explicitly start the dashboard
        manager.start_dashboard()
        # Create simulated connections
        demo_servers = [f"https://demo-server-{i + 1}.example.com" for i in range(connections)]

        clients = []
        for server_url in demo_servers:
            try:
                # For demo, we'll create clients that simulate being connected
                from client.mcp_client import MCPClientWithDashboard

                client = MCPClientWithDashboard(server_url, dashboard=manager.dashboard)
                # Simulate successful connection
                client.is_connected = True
                client.connection_state.update_status("connected")

                clients.append(client)
                manager.clients[server_url] = client

                print(f"✅ Demo connection established: {server_url}")

            except Exception as e:
                print(f"❌ Failed to create demo connection to {server_url}: {e}")

        if not clients:
            print("❌ No demo connections could be established")
            return 1

        dashboard_url = manager.get_dashboard_url()
        print(f"\n🌐 Dashboard available at: {dashboard_url}")
        print("🎯 Simulating MCP tool activity...")
        print("Press Ctrl+C to stop demo...")

        try:
            # Run continuous simulation
            iteration = 0
            while True:
                iteration += 1
                print(f"\n🔄 Demo iteration {iteration}")

                # Simulate activity on all connections
                await manager.simulate_activity(iterations=3)

                # Wait before next round
                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Stopping demo...")

    return 0


async def multiple_connections_mode(servers: list, port: int = 53729, auto_find_port: bool = True):
    """Test multiple concurrent connections"""
    print(f"🔗 Testing multiple connections to {len(servers)} servers...")

    async with MCPClientManager(
        enable_dashboard=True, dashboard_port=port, auto_find_port=auto_find_port
    ) as manager:
        # Explicitly start the dashboard
        manager.start_dashboard()
        connected_clients = []

        # Connect to all servers
        for server_url in servers:
            try:
                client = await manager.connect_to_server(server_url)
                connected_clients.append(client)
                print(f"✅ Connected to {server_url}")
            except Exception as e:
                print(f"❌ Failed to connect to {server_url}: {e}")

        if not connected_clients:
            print("❌ No successful connections")
            return 1

        dashboard_url = manager.get_dashboard_url()
        print(f"\n🌐 Dashboard available at: {dashboard_url}")
        print(f"📊 Monitoring {len(connected_clients)} connections")
        print("Press Ctrl+C to disconnect all...")

        try:
            # Keep connections alive
            while connected_clients:
                await asyncio.sleep(1)
                # Remove disconnected clients
                connected_clients = [c for c in connected_clients if c.is_connected]

        except KeyboardInterrupt:
            print("\n🛑 Disconnecting all connections...")

    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="SwiftLens Client Dashboard Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start dashboard only for monitoring
  python launcher.py --dashboard-only

  # Connect to a deployed SwiftLens server
  python launcher.py --remote https://swiftlens-server.render.com

  # Run demonstration with simulated connections
  python launcher.py --demo --connections 3

  # Test multiple server connections
  python launcher.py --multiple server1.com server2.com server3.com
        """,
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Start dashboard only for monitoring external connections",
    )
    mode_group.add_argument("--remote", metavar="URL", help="Connect to specific remote MCP server")
    mode_group.add_argument(
        "--demo",
        action="store_true",
        help="Run demonstration with simulated connections",
    )
    mode_group.add_argument(
        "--multiple",
        nargs="+",
        metavar="URL",
        help="Test multiple concurrent connections",
    )

    # Common options
    parser.add_argument("--port", type=int, default=53729, help="Dashboard port (default: 53729)")
    parser.add_argument(
        "--connections",
        type=int,
        default=2,
        help="Number of demo connections (default: 2)",
    )

    args = parser.parse_args()

    # Validate port
    if not (1024 <= args.port <= 65535):
        print("❌ Port must be between 1024 and 65535")
        return 1

    # Run the appropriate mode
    try:
        if args.dashboard_only:
            return asyncio.run(dashboard_only_mode(port=args.port))

        elif args.remote:
            return asyncio.run(remote_connection_mode(args.remote, port=args.port))

        elif args.demo:
            return asyncio.run(demo_mode(port=args.port, connections=args.connections))

        elif args.multiple:
            return asyncio.run(multiple_connections_mode(args.multiple, port=args.port))

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
