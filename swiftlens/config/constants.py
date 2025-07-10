"""Configuration constants for Swift Context MCP tools."""

# File analysis limits
MAX_SWIFT_FILES_FOR_ANALYSIS = 5000
MAX_FILE_SIZE_MB = 10
MAX_KEY_FILES_IN_CONTEXT = 10

# Project analysis thresholds
LARGE_PROJECT_THRESHOLD = 100
MAX_MAIN_CANDIDATES = 3
MAX_SOURCE_FILES_IN_CONTEXT = 5

# Performance optimization settings
FILE_TRAVERSAL_BATCH_SIZE = 1000
PROGRESS_REPORT_INTERVAL = 500

# Validation limits
MAX_PATH_LENGTH = 4096
MAX_CONFIG_FILE_SIZE = 100000

# Common directory patterns to exclude during file discovery
EXCLUDE_DIRECTORIES = {
    ".git",
    ".build",
    "build",
    "Build",
    "DerivedData",
    "node_modules",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
    ".idea",
}

# Swift-specific directory patterns
SWIFT_SOURCE_DIRECTORIES = ["Sources", "src", "Source"]
SWIFT_TEST_DIRECTORIES = ["Tests", "Test"]
SWIFT_EXAMPLE_DIRECTORIES = ["Example", "Examples"]

# Git ignore patterns for SwiftLens
SWIFTLENS_GITIGNORE_PATTERNS = [
    ".swiftlens.json",
    ".build/",
    "build/",
    "DerivedData/",
    "*.swiftpm",
    ".DS_Store",
]
