"""Environment variable utilities."""

import os


def get_max_workers(default: int = 4) -> int:
    """Get the maximum number of worker threads from environment variable.

    Args:
        default: Default value if environment variable is not set or invalid

    Returns:
        Maximum number of worker threads (limited to safe bounds based on system)
    """
    try:
        max_workers = int(os.environ.get("SWIFT_LSP_MAX_WORKERS", str(default)))
        # Limit to reasonable bounds based on system
        # On macOS, spawning >32 SourceKit-LSP instances often crashes
        safe_limit = min(32, os.cpu_count() * 2) if os.cpu_count() else 32
        return max(1, min(max_workers, safe_limit))
    except ValueError:
        return default


def get_max_files(default: int = 500) -> int:
    """Get the maximum number of files to process from environment variable.

    Args:
        default: Default value if environment variable is not set or invalid

    Returns:
        Maximum number of files to process (1-10000)
    """
    try:
        max_files = int(os.environ.get("SWIFT_LSP_MAX_FILES", str(default)))
        if max_files <= 0 or max_files > 10000:
            return default
        return max_files
    except ValueError:
        return default
