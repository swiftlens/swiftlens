"""Tool for building/rebuilding Swift project index for LSP functionality."""

import fcntl
import json
import os
import re
import subprocess
import time
from typing import Any

from swiftlens.compiler.error_parser import SwiftErrorParser
from swiftlens.model.models import BuildIndexResponse, ErrorType
from swiftlens.utils.validation import validate_project_path

# Constants
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
ENVIRONMENT_CHECK_TIMEOUT = 5
SCHEME_DETECTION_TIMEOUT = 10

# Pre-compiled regex patterns for build output sanitization (performance optimization)
_SANITIZATION_PATTERNS = [
    # Remove absolute paths (keep relative paths for context)
    (re.compile(r"/[\w\-\._/]+?(?=\s|$|:)"), "<path>"),
    # Remove environment variables
    (re.compile(r"\b[A-Z_]+=[\w\-\._/]+"), "<env_var>"),
    # Remove tokens/keys (sequences of alphanumeric chars > 20 chars)
    (re.compile(r"\b[a-zA-Z0-9]{20,}\b"), "<token>"),
    # Remove API keys and secrets (sk-, pk-, etc. followed by alphanumeric)
    (re.compile(r"\b(?:sk|pk|api_key|token|secret)[-_]?[a-zA-Z0-9]{10,}\b"), "<token>"),
    # Remove IP addresses
    (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"), "<ip>"),
    # Remove UUIDs
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "<uuid>",
    ),
]

# Valid scheme name pattern (alphanumeric, hyphens, underscores, literal spaces only - no newlines/tabs)
_SCHEME_NAME_PATTERN = re.compile(r"^[\w\-]+(?: [\w\-]+)*$")

# Constants for error summarization and token optimization
COMPRESSION_THRESHOLDS = {
    "NONE": 1000,  # Below this, no compression
    "MODERATE": 5000,  # Below this, moderate compression
    "AGGRESSIVE": None,  # Above previous, maximum compression
}

# Error pattern groups for categorizing and compressing errors
ERROR_PATTERNS = {
    "ambiguous": re.compile(r"ambiguous use of '([^']+)'|'([^']+)' is ambiguous"),
    "concurrency": re.compile(r"var '([^']+)' is not concurrency-safe"),
    "conformance": re.compile(r"type '([^']+)' does not conform to protocol '([^']+)'"),
    "scope": re.compile(r"cannot find '([^']+)' in scope"),
    "redeclaration": re.compile(r"invalid redeclaration of '([^']+)'"),
    "no_member": re.compile(r"value of type '([^']+)' has no member '([^']+)'"),
}


def _sanitize_build_output(output: str) -> str:
    """Sanitize build output to prevent sensitive information leakage.

    Removes potentially sensitive paths, environment variables, and build configuration.
    Uses pre-compiled regex patterns for improved performance.
    """
    if not output:
        return output

    sanitized = output
    for pattern, replacement in _SANITIZATION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def _summarize_build_errors(output: str, project_path: str) -> str:
    """Summarize build errors for token-optimized output.

    Compresses verbose build output into actionable summaries optimized for minimal
    token usage by AI agents while preserving all critical debugging information.

    Args:
        output: Raw build output containing errors
        project_path: Project path for relative file paths

    Returns:
        Compressed error summary string
    """
    if not output:
        return output

    output_len = len(output)

    # Determine compression level based on output size
    if output_len < COMPRESSION_THRESHOLDS["NONE"]:
        return _sanitize_build_output(output)

    # Parse errors using SwiftErrorParser
    parser = SwiftErrorParser()
    diagnostics = parser.parse_diagnostics(output)

    if not diagnostics:
        # Fallback for unparseable output
        lines = output.strip().split("\n")
        error_lines = [line for line in lines if "error:" in line.lower()]
        warning_lines = [line for line in lines if "warning:" in line.lower()]

        summary_parts = []
        if error_lines:
            summary_parts.append(f"E:{len(error_lines)}")
        if warning_lines:
            summary_parts.append(f"W:{len(warning_lines)}")

        if summary_parts:
            result = f"Build failed: {' '.join(summary_parts)}\n"
            # Add first few error examples
            for i, line in enumerate(error_lines[:3]):
                # Extract just the error message part
                if "error:" in line:
                    msg = line.split("error:", 1)[1].strip()
                    result += f"E{i + 1}:{msg[:80]}\n"
            if len(error_lines) > 3:
                result += f"+{len(error_lines) - 3} more errors"
            return result
        else:
            return "Build failed (no errors parsed)"

    # Group errors by pattern
    error_groups = {}
    uncategorized = []

    for diag in diagnostics:
        if diag.type != "error":
            continue

        categorized = False
        for category, pattern in ERROR_PATTERNS.items():
            match = pattern.search(diag.message)
            if match:
                if category not in error_groups:
                    error_groups[category] = {}

                # Extract key information based on category
                if category == "ambiguous":
                    # Pattern has two groups, use whichever matched
                    symbol = match.group(1) or match.group(2)
                    if symbol not in error_groups[category]:
                        error_groups[category][symbol] = []
                    error_groups[category][symbol].append(
                        f"{os.path.basename(diag.file_path or 'unknown')}:{diag.line}"
                    )

                elif category == "concurrency":
                    var_name = match.group(1)
                    if "vars" not in error_groups[category]:
                        error_groups[category]["vars"] = []
                    error_groups[category]["vars"].append(var_name)

                elif category == "conformance":
                    type_name = match.group(1)
                    protocol_name = match.group(2)
                    key = f"{type_name}->{protocol_name}"
                    if key not in error_groups[category]:
                        error_groups[category][key] = []
                    error_groups[category][key].append(
                        f"{os.path.basename(diag.file_path or 'unknown')}:{diag.line}"
                    )

                else:
                    # Generic grouping by first match group
                    key = match.group(1)
                    if key not in error_groups[category]:
                        error_groups[category][key] = []
                    error_groups[category][key].append(
                        f"{os.path.basename(diag.file_path or 'unknown')}:{diag.line}"
                    )

                categorized = True
                break

        if not categorized:
            uncategorized.append(diag)

    # Build ultra-compressed summary
    summary = parser.get_diagnostic_summary(diagnostics)
    total_errors = summary.get("error", 0)
    total_warnings = summary.get("warning", 0)

    # Count unique files
    unique_files = set()
    for diag in diagnostics:
        if diag.file_path:
            unique_files.add(os.path.basename(diag.file_path))

    if output_len > COMPRESSION_THRESHOLDS["MODERATE"]:
        # Ultra-compressed format for very large outputs
        result = f"{total_errors}E/{len(unique_files)}F:"

        # Add compressed error summaries
        if "ambiguous" in error_groups:
            symbols = list(error_groups["ambiguous"].keys())[:3]
            locations = [f"{sym}@{error_groups['ambiguous'][sym][0]}" for sym in symbols]
            remaining = len(error_groups["ambiguous"]) - len(symbols)
            result += f"ambiguous({len(error_groups['ambiguous'])}):{','.join(locations)}"
            if remaining > 0:
                result += f"+{remaining}"
            result += ";"

        if "concurrency" in error_groups and "vars" in error_groups["concurrency"]:
            vars_list = error_groups["concurrency"]["vars"]
            unique_vars = list(set(vars_list))[:5]
            result += f"concurrency({len(set(vars_list))}):{','.join(unique_vars)}"
            if len(set(vars_list)) > 5:
                result += f"+{len(set(vars_list)) - 5}"
            result += ";"

        if "conformance" in error_groups:
            items = list(error_groups["conformance"].items())[:2]
            result += f"conformance({len(error_groups['conformance'])}):"
            result += ",".join([f"{k}@{v[0]}" for k, v in items])
            if len(error_groups["conformance"]) > 2:
                result += f"+{len(error_groups['conformance']) - 2}"
            result += ";"

        # Add other categories briefly
        for category in ["scope", "redeclaration", "no_member"]:
            if category in error_groups:
                count = len(error_groups[category])
                first_key = list(error_groups[category].keys())[0]
                first_loc = error_groups[category][first_key][0]
                result += f"{category}({count}):{first_key}@{first_loc};"

        if uncategorized:
            result += f"other({len(uncategorized)})"

    else:
        # Moderate compression for medium-sized outputs
        result = f"Build failed: {total_errors} errors in {len(unique_files)} files\n\n"

        # Add grouped errors with more detail
        if "ambiguous" in error_groups:
            result += f"Type ambiguity ({len(error_groups['ambiguous'])} symbols):\n"
            for _, (symbol, locations) in enumerate(list(error_groups["ambiguous"].items())[:3]):
                result += f"  '{symbol}' @ {', '.join(locations[:2])}\n"
            if len(error_groups["ambiguous"]) > 3:
                result += f"  +{len(error_groups['ambiguous']) - 3} more\n"
            result += "\n"

        if "concurrency" in error_groups and "vars" in error_groups["concurrency"]:
            unique_vars = list(set(error_groups["concurrency"]["vars"]))
            result += f"Concurrency ({len(unique_vars)} vars):\n"
            result += f"  Not concurrency-safe: {', '.join(unique_vars[:5])}\n"
            if len(unique_vars) > 5:
                result += f"  +{len(unique_vars) - 5} more\n"
            result += "  Fix: Add @MainActor or convert to 'let'\n\n"

        if "conformance" in error_groups:
            result += f"Protocol conformance ({len(error_groups['conformance'])} issues):\n"
            for _, (key, locations) in enumerate(list(error_groups["conformance"].items())[:2]):
                result += f"  {key} @ {locations[0]}\n"
            if len(error_groups["conformance"]) > 2:
                result += f"  +{len(error_groups['conformance']) - 2} more\n"
            result += "\n"

        # Add brief summary of other errors
        other_count = 0
        for category in ["scope", "redeclaration", "no_member"]:
            if category in error_groups:
                other_count += len(error_groups[category])

        if uncategorized:
            other_count += len(uncategorized)

        if other_count > 0:
            result += f"Other errors: {other_count}\n"

        if total_warnings > 0:
            result += f"\nAlso: {total_warnings} warnings"

    return result.strip()


def _check_development_environment(
    tool_name: str, find_command: str, error_message: str, project_path: str
) -> BuildIndexResponse | None:
    """Common environment check logic for both SPM and Xcode builds.

    Returns BuildIndexResponse with error if environment check fails, None if successful.
    """
    try:
        result = subprocess.run(
            ["xcrun", "--find", find_command],
            capture_output=True,
            text=True,
            timeout=ENVIRONMENT_CHECK_TIMEOUT,
        )

        if result.returncode != 0:
            return BuildIndexResponse(
                success=False,
                project_path=project_path,
                error=error_message,
                error_type=ErrorType.ENVIRONMENT_ERROR,
            )

    except subprocess.TimeoutExpired:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"{tool_name} environment check timed out",
            error_type=ErrorType.ENVIRONMENT_ERROR,
        )
    except Exception as e:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"Error checking {tool_name} environment: {str(e)}",
            error_type=ErrorType.ENVIRONMENT_ERROR,
        )

    return None


def _validate_scheme_name(scheme: str) -> bool:
    """Validate Xcode scheme name for security.

    Args:
        scheme: Scheme name to validate

    Returns:
        True if scheme name is safe, False otherwise
    """
    if not scheme or not isinstance(scheme, str):
        return False

    # Check for null bytes
    if "\0" in scheme:
        return False

    # Validate against safe pattern (alphanumeric, hyphens, underscores, spaces)
    if not _SCHEME_NAME_PATTERN.match(scheme):
        return False

    # Additional length check
    if len(scheme) > 100:  # Reasonable scheme name length limit
        return False

    return True


def _validate_index_path_security(index_path: str, project_path: str) -> bool:
    """Validate that index path stays within project bounds.

    Args:
        index_path: Constructed index path to validate
        project_path: Project root path that should contain index

    Returns:
        True if index path is safe, False otherwise
    """
    try:
        # Resolve both paths to absolute, canonical forms (resolving symlinks)
        abs_index_path = os.path.realpath(index_path)
        abs_project_path = os.path.realpath(project_path)

        # Check that index path is within project directory
        common_path = os.path.commonpath([abs_index_path, abs_project_path])

        # Index path should be within project path
        return common_path == abs_project_path

    except (ValueError, OSError):
        # If we can't resolve paths safely, reject
        return False


def swift_build_index(
    project_path: str = None, timeout: int = 60, scheme: str = None
) -> dict[str, Any]:
    """Build or rebuild the Swift project index for better LSP functionality.

    Supports both Swift Package Manager (SPM) and Xcode projects, ensuring the
    index is stored in a consistent location (.build/index/store) for both.

    Args:
        project_path: Path to Swift project directory. If None, uses current directory.
        timeout: Maximum time in seconds for build operation (default 60, max 300)
        scheme: For Xcode projects, specific scheme to build. Auto-detected if not provided.

    Returns:
        BuildIndexResponse as dict with build status and index location
    """
    # Determine project path
    if project_path is None:
        project_path = os.getcwd()

    # Validate and sanitize the project path using common validation
    is_valid, real_project_path, error_msg = validate_project_path(project_path)
    if not is_valid:
        # Clean up error message prefix for consistency
        if error_msg.startswith("Error: "):
            error_msg = error_msg[7:]  # Remove "Error: " prefix
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=error_msg,
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Validate timeout
    if timeout > MAX_TIMEOUT:
        timeout = MAX_TIMEOUT
    elif timeout < 1:
        timeout = DEFAULT_TIMEOUT

    # Detect project type and build
    package_swift_path = os.path.join(real_project_path, "Package.swift")
    if os.path.exists(package_swift_path):
        return _build_with_spm(real_project_path, timeout)
    else:
        # Look for Xcode project
        xcode_project = _find_xcode_project(real_project_path)
        if xcode_project:
            return _build_with_xcode(real_project_path, xcode_project, scheme, timeout)
        else:
            return BuildIndexResponse(
                success=False,
                project_path=real_project_path,
                error="No Swift project found (Package.swift or .xcodeproj/.xcworkspace)",
                error_type=ErrorType.VALIDATION_ERROR,
            ).model_dump()


def _build_with_spm(project_path: str, timeout: int) -> dict[str, Any]:
    """Build index for Swift Package Manager project."""
    # Check environment using common function
    env_error = _check_development_environment(
        "Swift",
        "swift",
        "Swift command not found. Please install Xcode or Swift toolchain.",
        project_path,
    )
    if env_error:
        return env_error.model_dump()

    # Build the index with file locking
    lock_file = os.path.join(project_path, ".build", ".index-build.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    try:
        # Acquire file lock to prevent concurrent builds
        with open(lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            start_time = time.time()

            # Construct the build command
            cmd = [
                "xcrun",
                "swift",
                "build",
                "-Xswiftc",
                "-index-store-path",
                "-Xswiftc",
                ".build/index/store",
            ]

            # Execute the build command
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=project_path
            )

            build_time = time.time() - start_time

            # Determine the index path
            index_path = os.path.join(project_path, ".build", "index", "store")

            if result.returncode == 0:
                # Build succeeded
                return BuildIndexResponse(
                    success=True,
                    project_path=project_path,
                    index_path=index_path if os.path.exists(index_path) else None,
                    build_output=_sanitize_build_output(result.stdout + result.stderr),
                    build_time=build_time,
                    project_type="spm",
                ).model_dump()
            else:
                # Build failed - summarize errors if output is large
                full_output = result.stdout + result.stderr
                if len(full_output) > COMPRESSION_THRESHOLDS["NONE"]:
                    build_output = _summarize_build_errors(full_output, project_path)
                else:
                    build_output = _sanitize_build_output(full_output)

                return BuildIndexResponse(
                    success=False,
                    project_path=project_path,
                    build_output=build_output,
                    build_time=build_time,
                    error=f"Build failed with exit code {result.returncode}",
                    error_type=ErrorType.BUILD_ERROR,
                ).model_dump()

    except BlockingIOError:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error="Another build is already in progress for this project",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()
    except subprocess.TimeoutExpired:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"Build timed out after {timeout} seconds",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()
    except Exception as e:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"Build error: {str(e)}",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()


def _build_with_xcode(
    project_path: str, xcode_project: str, scheme: str, timeout: int
) -> dict[str, Any]:
    """Build index for Xcode project."""
    # Check environment using common function
    env_error = _check_development_environment(
        "Xcode", "xcodebuild", "xcodebuild not found. Please install Xcode.", project_path
    )
    if env_error:
        return env_error.model_dump()

    # Auto-detect scheme if not provided
    if not scheme:
        scheme = _detect_xcode_scheme(xcode_project)
        if not scheme:
            return BuildIndexResponse(
                success=False,
                project_path=project_path,
                error="No scheme found in Xcode project. Please specify a scheme.",
                error_type=ErrorType.VALIDATION_ERROR,
            ).model_dump()

    # Validate scheme name for security (prevent command injection)
    if not _validate_scheme_name(scheme):
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error="Invalid scheme name. Scheme names can only contain alphanumeric characters, hyphens, underscores, and spaces.",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    # Prepare index path
    index_path = os.path.join(project_path, ".build", "index", "store")

    # Validate index path for security (prevent path injection)
    if not _validate_index_path_security(index_path, project_path):
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error="Invalid index path. Index must be within project directory.",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    os.makedirs(index_path, exist_ok=True)

    # Build with file locking
    lock_file = os.path.join(project_path, ".build", ".index-build.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    try:
        # Acquire file lock
        with open(lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            start_time = time.time()

            # Determine project type flag
            is_workspace = xcode_project.endswith(".xcworkspace")
            project_flag = "-workspace" if is_workspace else "-project"

            # Construct the build command using O3's recommended approach
            cmd = [
                "xcrun",
                "xcodebuild",
                project_flag,
                xcode_project,
                "-scheme",
                scheme,
                "build",
                f"INDEX_STORE_PATH={index_path}",
                f"CLANG_INDEX_STORE_PATH={index_path}",  # For Obj-C/C++
                "INDEX_ENABLE_BUILD_ARENA=YES",
            ]

            # Execute the build command
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=project_path
            )

            build_time = time.time() - start_time

            if result.returncode == 0:
                # Build succeeded
                return BuildIndexResponse(
                    success=True,
                    project_path=project_path,
                    index_path=index_path if os.path.exists(index_path) else None,
                    build_output=_sanitize_build_output(result.stdout + result.stderr),
                    build_time=build_time,
                    project_type="xcode",
                ).model_dump()
            else:
                # Build failed - summarize errors if output is large
                full_output = result.stdout + result.stderr
                if len(full_output) > COMPRESSION_THRESHOLDS["NONE"]:
                    build_output = _summarize_build_errors(full_output, project_path)
                else:
                    build_output = _sanitize_build_output(full_output)

                return BuildIndexResponse(
                    success=False,
                    project_path=project_path,
                    build_output=build_output,
                    build_time=build_time,
                    error=f"Xcode build failed with exit code {result.returncode}",
                    error_type=ErrorType.BUILD_ERROR,
                ).model_dump()

    except BlockingIOError:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error="Another build is already in progress for this project",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()
    except subprocess.TimeoutExpired:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"Xcode build timed out after {timeout} seconds",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()
    except Exception as e:
        return BuildIndexResponse(
            success=False,
            project_path=project_path,
            error=f"Xcode build error: {str(e)}",
            error_type=ErrorType.BUILD_ERROR,
        ).model_dump()


def _find_xcode_project(start_dir: str) -> str | None:
    """Find .xcworkspace or .xcodeproj in directory.

    Prioritizes .xcworkspace over .xcodeproj for CocoaPods/mixed projects.
    Handles symlinks and permission checks.
    """
    try:
        # Check directory permissions
        if not os.access(start_dir, os.R_OK):
            return None

        # First look for .xcworkspace
        for item in os.listdir(start_dir):
            if item.endswith(".xcworkspace") and not item.startswith("."):
                full_path = os.path.join(start_dir, item)
                # Handle symlinks - resolve to actual path and check accessibility
                if os.path.islink(full_path):
                    try:
                        real_path = os.path.realpath(full_path)
                        if os.path.exists(real_path) and os.access(real_path, os.R_OK):
                            return full_path  # Return symlink path, not resolved path
                    except (OSError, PermissionError):
                        continue
                elif os.path.isdir(full_path) and os.access(full_path, os.R_OK):
                    return full_path

        # Then look for .xcodeproj
        for item in os.listdir(start_dir):
            if item.endswith(".xcodeproj") and not item.startswith("."):
                full_path = os.path.join(start_dir, item)
                # Handle symlinks - resolve to actual path and check accessibility
                if os.path.islink(full_path):
                    try:
                        real_path = os.path.realpath(full_path)
                        if os.path.exists(real_path) and os.access(real_path, os.R_OK):
                            return full_path  # Return symlink path, not resolved path
                    except (OSError, PermissionError):
                        continue
                elif os.path.isdir(full_path) and os.access(full_path, os.R_OK):
                    return full_path

    except (OSError, PermissionError):
        # Directory listing failed due to permissions
        pass

    return None


def _detect_xcode_scheme(xcode_project: str) -> str | None:
    """Auto-detect first available scheme in Xcode project."""
    try:
        # Determine project type flag
        is_workspace = xcode_project.endswith(".xcworkspace")
        project_flag = "-workspace" if is_workspace else "-project"

        # Get list of schemes
        cmd = ["xcrun", "xcodebuild", project_flag, xcode_project, "-list", "-json"]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=SCHEME_DETECTION_TIMEOUT
        )

        if result.returncode == 0:
            try:
                schemes_info = json.loads(result.stdout)
                # Handle both project and workspace formats
                if is_workspace and "workspace" in schemes_info:
                    schemes = schemes_info["workspace"].get("schemes", [])
                elif "project" in schemes_info:
                    schemes = schemes_info["project"].get("schemes", [])
                else:
                    schemes = []

                # Return first non-empty scheme
                for scheme in schemes:
                    if scheme and not scheme.startswith("."):
                        return scheme
            except (json.JSONDecodeError, KeyError):
                pass

    except Exception:
        pass

    return None
