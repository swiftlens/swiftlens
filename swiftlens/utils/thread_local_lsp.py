"""Thread-local LSP client management utilities.

This module provides thread-safe LSP client caching to optimize performance
in parallel processing scenarios. Each thread gets its own LSP client instance,
avoiding the ~2 second initialization overhead per file while maintaining
thread safety.

The implementation uses Python's threading.local() to store FileAnalyzer
instances per thread and per project root, ensuring proper isolation and
allowing threads to process files from different projects correctly.
"""

import atexit
import hashlib
import logging
import os
import threading
import weakref
from collections import OrderedDict
from typing import Final

try:
    from lsp.client_manager import get_manager
    from lsp.timeouts import LSPTimeouts
except ImportError as e:
    raise ImportError(
        "swiftlens-core package is required but not installed. "
        "Please install it with: pip install swiftlens-core"
    ) from e

from swiftlens.analysis.file_analyzer import FileAnalyzer

# Configure logging
logger = logging.getLogger(__name__)

# Thread-local storage for FileAnalyzer instances
_thread_local = threading.local()

# Constants
MAX_CACHE_SIZE: Final[int] = 50  # Maximum analyzers per thread

# Validate cache size configuration
if MAX_CACHE_SIZE <= 0:
    raise ValueError(f"MAX_CACHE_SIZE must be positive, got {MAX_CACHE_SIZE}")

_cache_registry_lock = threading.Lock()  # Protects cache registry
# Track thread cache keys - uses weak references to allow garbage collection
_thread_caches: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


# Sentinel class that supports weak references
class _ThreadCacheSentinel:
    """Lightweight sentinel object that supports weak references."""

    pass


def _get_thread_cache() -> OrderedDict:
    """Get or create the thread-local LRU cache."""
    if not hasattr(_thread_local, "_lru_cache"):
        cache = OrderedDict()
        _thread_local._lru_cache = cache
        # FIX 3: Initialize analyzer counter
        _thread_local._analyzer_count = 0
        # Register this thread's cache with weak reference
        thread_id = threading.get_ident()
        with _cache_registry_lock:
            _thread_caches[thread_id] = _ThreadCacheSentinel()  # Lightweight sentinel
    cache = _thread_local._lru_cache

    # Ensure counter exists even if cache was created by older version
    if not hasattr(_thread_local, "_analyzer_count"):
        count = len([k for k in cache if not k.endswith("_root")])
        logger.warning(
            "Missing _analyzer_count in thread-local cache. "
            "Re-initializing count to %d. This may happen after an upgrade.",
            count,
        )
        _thread_local._analyzer_count = count

    return cache


def _evict_oldest_analyzer():
    """Evict the oldest analyzer from the thread-local cache."""
    cache = _get_thread_cache()
    if not cache:
        return

    # FIX 2: Remove any orphaned root entries first
    for key in list(cache.keys()):
        if key.endswith("_root") and key[:-5] not in cache:
            cache.pop(key)
            logger.debug(f"Removed orphaned root entry: {key}")

    # Find the oldest analyzer key (skip root entries)
    oldest_analyzer_key = None
    for key in cache:
        if not key.endswith("_root"):
            oldest_analyzer_key = key
            break

    if not oldest_analyzer_key:
        return

    # Remove the analyzer and its root entry
    oldest_analyzer = cache.pop(oldest_analyzer_key, None)
    cache.pop(f"{oldest_analyzer_key}_root", None)

    # FIX 3: Decrement analyzer count safely
    if oldest_analyzer is not None and getattr(_thread_local, "_analyzer_count", 0) > 0:
        _thread_local._analyzer_count -= 1
        # Debug assertion to catch desync issues
        expected_count = len([k for k in cache if not k.endswith("_root")])
        assert _thread_local._analyzer_count == expected_count, (
            f"Analyzer count mismatch! Is: {_thread_local._analyzer_count}, Should be: {expected_count}"
        )

    logger.info(f"Evicting oldest analyzer from cache: {oldest_analyzer_key}")

    # Clean up the analyzer
    if oldest_analyzer and hasattr(oldest_analyzer, "client"):
        try:
            if hasattr(oldest_analyzer.client, "stop"):
                oldest_analyzer.client.stop()
        except Exception as e:
            logger.warning(f"Error stopping evicted analyzer: {e}")


def get_thread_local_analyzer(project_root: str | None = None) -> FileAnalyzer:
    """Get or create a thread-local FileAnalyzer instance.

    This ensures each thread in the pool has its own LSP client,
    avoiding thread safety issues while reusing clients across multiple files.
    The analyzer is cached per (thread, project_root) combination to support
    processing files from different projects in the same thread pool.

    Args:
        project_root: Project root for LSP initialization. If None, uses current working directory.

    Returns:
        FileAnalyzer instance specific to the current thread and project root.

    Raises:
        RuntimeError: If LSP client creation fails.
    """
    if project_root is None:
        project_root = os.getcwd()
    else:
        project_root = os.path.abspath(project_root)

    # Create a secure cache key using SHA256 hash
    # This prevents path injection and ensures valid Python identifiers
    path_hash = hashlib.sha256(project_root.encode()).hexdigest()[:32]
    cache_key = f"analyzer_{path_hash}"

    # Get the LRU cache for this thread
    cache = _get_thread_cache()

    # Check if we have a cached analyzer
    if cache_key in cache:
        analyzer = cache[cache_key]

        # Try to use the cached analyzer with race condition protection
        try:
            # Verify the client is still alive
            if hasattr(analyzer, "client") and hasattr(analyzer.client, "is_alive"):
                if analyzer.client.is_alive():
                    # Verify it's for the correct project (FIX 4: validate before LRU update)
                    # Check if we stored the project root with this cache key
                    root_key = f"{cache_key}_root"
                    if root_key in cache and cache[root_key] == project_root:
                        # Move to end of LRU cache ONLY after validation
                        cache.move_to_end(cache_key)
                        cache.move_to_end(root_key)  # Keep root in sync
                        return analyzer
                    else:
                        logger.warning(f"Cache key collision detected for {cache_key}")
                else:
                    logger.info(f"Replacing dead LSP client for project: {project_root}")
            else:
                logger.warning(f"Invalid analyzer in cache for {cache_key}")
        except (RuntimeError, AttributeError, OSError) as e:
            # Client is dead or invalid - will recreate below
            logger.warning(f"Error accessing cached analyzer: {e}")

        # Remove the dead/invalid analyzer (FIX 3: only use cache, no attributes)
        # FIX 1: Stop the client before removal to prevent resource leak
        if analyzer and hasattr(analyzer, "client") and hasattr(analyzer.client, "stop"):
            try:
                analyzer.client.stop()
                logger.debug(f"Stopped dead client for {cache_key}")
            except Exception as e:
                logger.warning(f"Error stopping dead client: {e}")
        removed_analyzer = cache.pop(cache_key, None)
        cache.pop(f"{cache_key}_root", None)
        # FIX 3: Decrement analyzer count safely
        if removed_analyzer is not None and getattr(_thread_local, "_analyzer_count", 0) > 0:
            _thread_local._analyzer_count -= 1
            # Debug assertion to catch desync issues
            cache = _get_thread_cache()
            expected_count = len([k for k in cache if not k.endswith("_root")])
            assert _thread_local._analyzer_count == expected_count, (
                f"Analyzer count mismatch! Is: {_thread_local._analyzer_count}, Should be: {expected_count}"
            )

    # Create a new analyzer
    logger.debug(f"Creating new LSP analyzer for project: {project_root}")
    try:
        manager = get_manager()
        client = manager.get_client(project_root=project_root, timeout=LSPTimeouts.HEAVY_OPERATION)
        analyzer = FileAnalyzer(client)

        # Check cache size and evict if necessary
        # FIX 3: Use counter instead of O(n) counting
        # Safe access with default
        count = getattr(_thread_local, "_analyzer_count", 0)
        if count >= MAX_CACHE_SIZE:
            _evict_oldest_analyzer()

        # Add to cache only (FIX 3: no redundant storage)
        cache[cache_key] = analyzer
        cache[f"{cache_key}_root"] = project_root
        # FIX 3: Increment analyzer count
        # Safe increment with default
        _thread_local._analyzer_count = getattr(_thread_local, "_analyzer_count", 0) + 1

        return analyzer
    except Exception as e:
        logger.error(f"Failed to create LSP analyzer for {project_root}: {e}")
        raise RuntimeError(f"LSP client creation failed: {e}") from e


def cleanup_thread_local_analyzers():
    """Clean up all thread-local analyzers.

    This function can be called to explicitly clean up LSP clients,
    though Python's garbage collector will handle cleanup when threads terminate.
    """
    logger.debug("Starting cleanup of thread-local analyzers")

    # Get the current thread's cache if it exists
    if hasattr(_thread_local, "_lru_cache"):
        cache = _thread_local._lru_cache

        # Clean up all analyzers in the cache (skip root entries)
        for cache_key in list(cache.keys()):
            if not cache_key.endswith("_root"):
                analyzer = cache.get(cache_key)
                if analyzer and hasattr(analyzer, "client"):
                    try:
                        # Attempt to stop the client gracefully
                        if hasattr(analyzer.client, "stop"):
                            analyzer.client.stop()
                            logger.debug(f"Stopped analyzer for {cache_key}")
                    except (RuntimeError, OSError, ConnectionError) as e:
                        # Handle known LSP-related errors during cleanup
                        logger.warning(f"Expected error during cleanup of {cache_key}: {e}")
                    except Exception as e:
                        # Log unexpected errors
                        logger.error(f"Unexpected error during cleanup of {cache_key}: {e}")

        # Clear the cache
        cache.clear()
        delattr(_thread_local, "_lru_cache")
        # FIX 3: Reset analyzer count
        if hasattr(_thread_local, "_analyzer_count"):
            delattr(_thread_local, "_analyzer_count")

    # Update registry - remove this thread
    thread_id = threading.get_ident()
    with _cache_registry_lock:
        _thread_caches.pop(thread_id, None)

    logger.debug("Completed cleanup of thread-local analyzers")


def cleanup_all_thread_analyzers():
    """Clean up analyzers from all threads.

    This function is designed to be called at exit to ensure all LSP processes
    are properly terminated across all threads. It cannot access other threads'
    local storage directly, but it can ensure the registry is cleared.
    """
    logger.debug("Starting cleanup of all thread analyzers")

    # First, clean up current thread's analyzers
    cleanup_thread_local_analyzers()

    # Clear the entire thread cache registry
    # Note: We cannot directly access other threads' local storage,
    # but clearing the registry ensures proper cleanup tracking
    with _cache_registry_lock:
        thread_count = len(_thread_caches)
        if thread_count > 0:
            logger.info(f"Clearing registry of {thread_count} thread caches")
            _thread_caches.clear()

    logger.debug("Completed cleanup of all thread analyzers")


# Register cleanup handler to ensure LSP processes are terminated on exit
atexit.register(cleanup_all_thread_analyzers)
