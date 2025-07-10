"""
Centralized logging system for Swift Context MCP Server Dashboard
Provides SQLite-based logging with real-time dashboard updates
"""

import asyncio
import json
import queue
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any


@dataclass
class LogEntry:
    """Represents a single log entry in the dashboard"""

    id: str
    timestamp: str
    tool_name: str
    parameters: dict[str, Any]
    result: dict[str, Any] | None
    execution_time_ms: float
    client_id: str
    session_id: str
    status: str  # 'success', 'error', 'in_progress'
    error_message: str | None = None


@dataclass
class SessionInfo:
    """Represents a client session"""

    session_id: str
    client_info: dict[str, Any]
    start_time: str
    end_time: str | None = None
    tool_count: int = 0


class DashboardLogger:
    """Centralized logger for the Swift Context MCP Server dashboard"""

    def __init__(self, db_path: str = None):
        config = get_dashboard_config()
        self.db_path = db_path or config.db_path
        self.config = config
        self.active_sessions: dict[str, SessionInfo] = {}
        self.log_queue = queue.Queue()
        self.websocket_clients = set()
        self._event_loop = None
        self._loop_thread = None
        self._connection_pool = queue.Queue(maxsize=config.connection_pool_size)
        self._pool_lock = threading.Lock()
        self._init_database()
        self._init_connection_pool()
        self._start_event_loop()
        self._start_log_processor()

    def _init_database(self):
        """Initialize SQLite database with required tables"""
        # Ensure database directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    parameters TEXT,
                    result TEXT,
                    execution_time_ms REAL,
                    client_id TEXT,
                    session_id TEXT,
                    status TEXT,
                    error_message TEXT
                )
            """)

            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    client_info TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    tool_count INTEGER DEFAULT 0
                )
            """)

            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_tool_name ON logs(tool_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_session_id ON logs(session_id)")

            conn.commit()

    def _init_connection_pool(self):
        """Initialize the SQLite connection pool"""
        pool_size = min(self.config.connection_pool_size, 5)  # Start with up to 5 connections
        for _ in range(pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety and performance
            self._connection_pool.put(conn)

    @contextmanager
    def _get_db_connection(self):
        """Context manager to get a database connection from the pool"""
        conn = None
        try:
            # Try to get a connection from the pool
            try:
                conn = self._connection_pool.get(timeout=1)
            except queue.Empty:
                # Pool is empty, create a new connection
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")

            yield conn
        finally:
            if conn:
                try:
                    # Return connection to pool if there's space
                    self._connection_pool.put_nowait(conn)
                except queue.Full:
                    # Pool is full, close the connection
                    conn.close()

    def _start_event_loop(self):
        """Start a dedicated event loop in a background thread for async operations"""

        def run_event_loop():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.run_forever()

        self._loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        self._loop_thread.start()

        # Wait for the event loop to be ready
        while self._event_loop is None:
            time.sleep(0.01)

    def _start_log_processor(self):
        """Start background thread to process log entries"""

        def process_logs():
            while True:
                try:
                    log_entry = self.log_queue.get(timeout=1)
                    if log_entry is None:  # Shutdown signal
                        break
                    self._store_log_entry(log_entry)
                    # Schedule the async broadcast in the dedicated event loop
                    if self._event_loop and not self._event_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            self._broadcast_to_websockets(log_entry), self._event_loop
                        )
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Error processing log entry: {e}")

        self.log_thread = threading.Thread(target=process_logs, daemon=True)
        self.log_thread.start()

    def _store_log_entry(self, log_entry: LogEntry):
        """Store log entry in SQLite database"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO logs
                (id, timestamp, tool_name, parameters, result, execution_time_ms,
                 client_id, session_id, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log_entry.id,
                    log_entry.timestamp,
                    log_entry.tool_name,
                    json.dumps(log_entry.parameters),
                    json.dumps(log_entry.result) if log_entry.result else None,
                    log_entry.execution_time_ms,
                    log_entry.client_id,
                    log_entry.session_id,
                    log_entry.status,
                    log_entry.error_message,
                ),
            )
            conn.commit()

    async def _broadcast_to_websockets(self, log_entry: LogEntry):
        """Broadcast log entry to all connected WebSocket clients (non-blocking)"""
        if not self.websocket_clients:
            return

        message = json.dumps({"type": "log_entry", "data": asdict(log_entry)})

        # Create tasks for all clients to send concurrently
        async def send_to_client(websocket):
            try:
                # Add timeout to prevent slow clients from blocking
                await asyncio.wait_for(
                    websocket.send_text(message), timeout=self.config.websocket_timeout
                )
                return websocket, True
            except (asyncio.TimeoutError, Exception):
                return websocket, False

        # Send to all clients concurrently
        if self.websocket_clients:
            tasks = [send_to_client(ws) for ws in self.websocket_clients.copy()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Remove disconnected or slow clients
            disconnected = set()
            for result in results:
                if isinstance(result, tuple):
                    websocket, success = result
                    if not success:
                        disconnected.add(websocket)
                elif isinstance(result, Exception):
                    # Handle any exceptions that occurred
                    pass

            self.websocket_clients -= disconnected

    def register_websocket(self, websocket):
        """Register a WebSocket client for real-time updates"""
        self.websocket_clients.add(websocket)

    def unregister_websocket(self, websocket):
        """Unregister a WebSocket client"""
        self.websocket_clients.discard(websocket)

    def start_session(self, session_id: str, client_info: dict[str, Any]) -> SessionInfo:
        """Start a new client session"""
        session = SessionInfo(
            session_id=session_id,
            client_info=client_info,
            start_time=datetime.now().isoformat(),
        )
        self.active_sessions[session_id] = session

        # Store in database
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, client_info, start_time, tool_count)
                VALUES (?, ?, ?, ?)
            """,
                (
                    session.session_id,
                    json.dumps(session.client_info),
                    session.start_time,
                    0,
                ),
            )
            conn.commit()

        return session

    def end_session(self, session_id: str):
        """End a client session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.end_time = datetime.now().isoformat()

            # Update database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE sessions
                    SET end_time = ?, tool_count = ?
                    WHERE session_id = ?
                """,
                    (session.end_time, session.tool_count, session_id),
                )
                conn.commit()

            del self.active_sessions[session_id]

    def log_tool_call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        client_id: str = "unknown",
        session_id: str = "default",
    ) -> str:
        """Log the start of a tool call and return log entry ID"""
        log_id = str(uuid.uuid4())
        log_entry = LogEntry(
            id=log_id,
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            parameters=parameters,
            result=None,
            execution_time_ms=0,
            client_id=client_id,
            session_id=session_id,
            status="in_progress",
        )

        # Update session tool count
        if session_id in self.active_sessions:
            self.active_sessions[session_id].tool_count += 1

        self.log_queue.put(log_entry)
        return log_id

    def log_tool_result(
        self,
        log_id: str,
        result: dict[str, Any],
        execution_time_ms: float,
        status: str = "success",
        error_message: str | None = None,
    ):
        """Log the completion of a tool call"""
        # Update the existing log entry in database
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE logs
                SET result = ?, execution_time_ms = ?, status = ?, error_message = ?
                WHERE id = ?
            """,
                (json.dumps(result), execution_time_ms, status, error_message, log_id),
            )
            conn.commit()

        # Broadcast update to WebSocket clients
        updated_entry = LogEntry(
            id=log_id,
            timestamp=datetime.now().isoformat(),
            tool_name="",  # Will be filled from database if needed
            parameters={},
            result=result,
            execution_time_ms=execution_time_ms,
            client_id="",
            session_id="",
            status=status,
            error_message=error_message,
        )
        # Schedule the async broadcast in the dedicated event loop
        if self._event_loop and not self._event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._broadcast_to_websockets(updated_entry), self._event_loop
            )

    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        tool_name: str | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Retrieve logs from database with optional filtering"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM logs"
            params = []
            conditions = []

            if tool_name:
                conditions.append("tool_name = ?")
                params.append(tool_name)

            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to dictionaries
            columns = [desc[0] for desc in cursor.description]
            logs = []
            for row in rows:
                log_dict = dict(zip(columns, row, strict=False))
                # Parse JSON fields
                if log_dict["parameters"]:
                    log_dict["parameters"] = json.loads(log_dict["parameters"])
                if log_dict["result"]:
                    log_dict["result"] = json.loads(log_dict["result"])
                logs.append(log_dict)

            return logs

    def get_sessions(self) -> list[dict]:
        """Get all sessions from database"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            rows = cursor.fetchall()

            columns = [desc[0] for desc in cursor.description]
            sessions = []
            for row in rows:
                session_dict = dict(zip(columns, row, strict=False))
                if session_dict["client_info"]:
                    session_dict["client_info"] = json.loads(session_dict["client_info"])
                sessions.append(session_dict)

            return sessions

    def get_statistics(self) -> dict[str, Any]:
        """Get dashboard statistics"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()

            # Total tool calls
            cursor.execute("SELECT COUNT(*) FROM logs")
            total_calls = cursor.fetchone()[0]

            # Tool usage counts
            cursor.execute("""
                SELECT tool_name, COUNT(*) as count
                FROM logs
                GROUP BY tool_name
                ORDER BY count DESC
            """)
            tool_usage = dict(cursor.fetchall())

            # Success/error rates
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM logs
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())

            # Active sessions
            active_session_count = len(self.active_sessions)

            return {
                "total_tool_calls": total_calls,
                "tool_usage": tool_usage,
                "status_counts": status_counts,
                "active_sessions": active_session_count,
                "connected_websockets": len(self.websocket_clients),
            }

    def shutdown(self):
        """Shutdown the logger and cleanup resources"""
        # Stop log processing thread
        self.log_queue.put(None)
        if hasattr(self, "log_thread"):
            self.log_thread.join(timeout=5)

        # End all active sessions
        for session_id in list(self.active_sessions.keys()):
            self.end_session(session_id)

        # Close all connections in the pool
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get_nowait()
                conn.close()
            except queue.Empty:
                break

        # Cleanup event loop
        if self._event_loop and not self._event_loop.is_closed():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2)


# Import configuration and resource manager after class definition to avoid circular imports
try:
    from .config import get_dashboard_config
    from .resource_manager import register_dashboard_logger
except ImportError:
    # Fallback if config is not available
    def get_dashboard_config():
        class FallbackConfig:
            def __init__(self):
                self.db_path = "dashboard_logs.db"
                self.connection_pool_size = 10
                self.websocket_timeout = 1.0
                self.log_retention_days = 30

        return FallbackConfig()

    def register_dashboard_logger(logger):
        pass  # No-op fallback


# Global logger instance
_logger_instance = None


def get_dashboard_logger() -> DashboardLogger:
    """Get the global dashboard logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = DashboardLogger()
        register_dashboard_logger(_logger_instance)
    return _logger_instance


def log_tool_execution(tool_name: str):
    """Decorator to log tool execution for dashboard monitoring"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_dashboard_logger()

            # Extract parameters (remove sensitive data if needed)
            parameters = {**kwargs}
            if args:
                parameters["_args"] = str(args)

            # Start logging
            start_time = time.time()
            log_id = logger.log_tool_call(tool_name, parameters)

            try:
                # Execute the function
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                # Log success
                logger.log_tool_result(
                    log_id,
                    {
                        "success": True,
                        "data": str(result)[:1000],
                    },  # Truncate large results
                    execution_time,
                    "success",
                )

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000

                # Log error
                logger.log_tool_result(
                    log_id,
                    {"success": False, "error": str(e)},
                    execution_time,
                    "error",
                    str(e),
                )

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_dashboard_logger()

            # Extract parameters
            parameters = {**kwargs}
            if args:
                parameters["_args"] = str(args)

            # Start logging
            start_time = time.time()
            log_id = logger.log_tool_call(tool_name, parameters)

            try:
                # Execute the function
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                # Log success
                logger.log_tool_result(
                    log_id,
                    {"success": True, "data": str(result)[:1000]},
                    execution_time,
                    "success",
                )

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000

                # Log error
                logger.log_tool_result(
                    log_id,
                    {"success": False, "error": str(e)},
                    execution_time,
                    "error",
                    str(e),
                )

                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
