"""Environment variable utilities."""

import os


def get_max_workers(default: int = 4) -> int:
    """Get the maximum number of worker threads from environment variable.

    Args:
        default: Default value if environment variable is not set or invalid

    Returns:
        Maximum number of worker threads (1-100)
    """
    try:
        max_workers = int(os.environ.get("SWIFT_LSP_MAX_WORKERS", str(default)))
        if max_workers <= 0 or max_workers > 100:
            return default
        return max_workers
    except ValueError:
        return default
