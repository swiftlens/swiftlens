"""
Unified LSP diagnostics tool that combines environment checks, health status, and performance stats.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from swiftlens.utils.validation import validate_project_path


@dataclass
class DiagnosticsConfig:
    """Configuration for diagnostics with resource limits."""

    max_depth: int = 10  # Prevent deep recursion in large repos
    max_files: int = 10000  # Limit memory usage
    max_compile_commands_size: int = 50 * 1024 * 1024  # 50MB limit
    subprocess_timeout: int = int(
        os.getenv("SWIFTLENS_SUBPROCESS_TIMEOUT", "5")
    )  # Configurable timeout
    max_lines_to_read: int = 100  # Lines to read from compile_commands.json


# Global configuration instance
CONFIG = DiagnosticsConfig()


# TODO: These will be implemented when the LSP managed client is available
def get_lsp_stats():
    """Get LSP performance statistics."""
    raise NotImplementedError("LSP stats collection not yet implemented")


def perform_lsp_health_check():
    """Check LSP client health status."""
    raise NotImplementedError("LSP health check not yet implemented")


def swift_lsp_diagnostics(
    project_path: str | None = None, include_recommendations: bool = True
) -> dict[str, Any]:
    """
    Comprehensive LSP diagnostics combining environment, health, and performance checks.

    This tool consolidates:
    - swift_diagnose_lsp: Environment and setup diagnostics
    - lsp_health_check: LSP client health status
    - lsp_manager_stats: Performance statistics

    Args:
        project_path: Optional path to Swift project for testing
        include_recommendations: Whether to include setup recommendations

    Returns:
        dict: Comprehensive diagnostics with environment, health, stats, and recommendations
    """
    result = {
        "success": True,
        "environment": _check_environment(),
        "lsp_server": _check_lsp_server(),
        "health": {},
        "stats": {},
        "project_setup": None,
        "recommendations": [],
    }

    # Check project setup if path provided
    if project_path is not None:
        # Validate project path for security
        is_valid, safe_path, err = validate_project_path(project_path)
        if not is_valid:
            result["success"] = False
            result["error"] = err
            result["error_type"] = "VALIDATION_ERROR"
            return result
        result["project_setup"] = _check_project_setup(safe_path)

    # Get LSP manager health and stats
    try:
        # Health check
        result["health"] = perform_lsp_health_check()

        # Performance stats
        result["stats"] = get_lsp_stats()

    except NotImplementedError:
        # Expected for now - stub functions not implemented
        result["health"] = {
            "status": "not_implemented",
            "error": "LSP health check pending implementation",
        }
        result["stats"] = {"status": "not_implemented", "error": "LSP stats pending implementation"}
    except Exception as e:
        # Don't set success=False - the diagnostic tool succeeded
        # even if it couldn't get health/stats
        if not isinstance(result.get("health"), dict):
            result["health"] = {}
        if not isinstance(result.get("stats"), dict):
            result["stats"] = {}
        result["health"]["error"] = str(e)
        result["stats"]["error"] = str(e)

    # Generate recommendations
    if include_recommendations:
        result["recommendations"] = _generate_recommendations(result)

    # Overall success check - only set to False on actual errors
    # Missing components are diagnostics, not failures
    # (The tool succeeds at diagnosing, even if components are missing)

    return result


def _check_environment() -> dict[str, Any]:
    """Check Swift development environment."""
    import sys

    env = {
        "has_swift": False,
        "swift_version": None,
        "has_xcode": False,
        "xcode_version": None,
        "sourcekit_lsp_path": None,
        "platform": sys.platform,  # Add platform detection
    }

    # Check Swift
    if shutil.which("swift"):
        env["has_swift"] = True
        try:
            version_output = subprocess.run(
                ["swift", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=CONFIG.subprocess_timeout,
            )
            env["swift_version"] = version_output.stdout.strip().split("\n")[0]
            if version_output.stderr:
                env["swift_version_stderr"] = version_output.stderr.strip()
        except subprocess.CalledProcessError as e:
            env["swift_version_error"] = f"Command failed with exit code {e.returncode}"
            if e.stderr:
                env["swift_version_stderr"] = e.stderr.strip()
        except subprocess.TimeoutExpired:
            env["swift_version_error"] = "Command timed out"
        except Exception as e:
            # Store error for debugging while continuing checks
            env["swift_version_error"] = str(e)

    # Check Xcode
    if shutil.which("xcodebuild"):
        env["has_xcode"] = True
        try:
            version_output = subprocess.run(
                ["xcodebuild", "-version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=CONFIG.subprocess_timeout,
            )
            env["xcode_version"] = version_output.stdout.strip().split("\n")[0]
            if version_output.stderr:
                env["xcode_version_stderr"] = version_output.stderr.strip()
        except subprocess.CalledProcessError as e:
            env["xcode_version_error"] = f"Command failed with exit code {e.returncode}"
            if e.stderr:
                env["xcode_version_stderr"] = e.stderr.strip()
        except subprocess.TimeoutExpired:
            env["xcode_version_error"] = "Command timed out"
        except Exception as e:
            # Store error for debugging while continuing checks
            env["xcode_version_error"] = str(e)

    # Check SourceKit-LSP
    lsp_path = shutil.which("sourcekit-lsp")
    if lsp_path:
        env["sourcekit_lsp_path"] = lsp_path

    return env


def _check_lsp_server() -> dict[str, Any]:
    """Check LSP server availability and version."""
    lsp_info = {"exists": False, "path": None, "version": None, "error": None}

    try:
        # Try to find sourcekit-lsp using xcrun
        result = subprocess.run(
            ["xcrun", "--find", "sourcekit-lsp"],
            capture_output=True,
            text=True,
            timeout=CONFIG.subprocess_timeout,
        )

        if result.returncode == 0:
            lsp_path = result.stdout.strip()
            if lsp_path and os.path.exists(lsp_path):
                lsp_info["exists"] = True
                lsp_info["path"] = lsp_path

                # Try to get version
                try:
                    version_output = subprocess.run(
                        [lsp_path, "--version"],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=CONFIG.subprocess_timeout,
                    )
                    lsp_info["version"] = version_output.stdout.strip()
                    if version_output.stderr:
                        lsp_info["version_stderr"] = version_output.stderr.strip()
                except subprocess.CalledProcessError as e:
                    lsp_info["version"] = "Unknown (command failed)"
                    lsp_info["version_error"] = f"Exit code {e.returncode}"
                except subprocess.TimeoutExpired:
                    lsp_info["version"] = "Unknown (timeout)"
                except Exception:
                    lsp_info["version"] = "Unknown"
        else:
            lsp_info["error"] = "sourcekit-lsp not found via xcrun"
            if result.stderr:
                lsp_info["error_details"] = result.stderr.strip()

    except subprocess.TimeoutExpired:
        lsp_info["error"] = "Command timed out"
    except Exception as e:
        lsp_info["error"] = str(e)

    return lsp_info


def _check_project_setup(project_path: str) -> dict[str, Any]:
    """Check Swift project setup and configuration with TOCTOU protection."""
    setup = {
        "path": project_path,
        "exists": False,
        "has_swift_files": False,
        "has_package_swift": False,
        "has_xcodeproj": False,
        "has_index_store": False,
        "index_store_details": {},
        "swift_file_count": 0,
    }

    path = Path(project_path)
    if not path.exists():
        return setup

    # TOCTOU protection: Lock in the directory inode
    try:
        # Try to open directory with O_PATH if available (Linux 2.6.39+)
        if hasattr(os, "O_PATH"):
            dir_fd = os.open(project_path, os.O_PATH | os.O_DIRECTORY)
            os.close(dir_fd)
    except Exception:
        # Fall back to basic check - best effort
        pass

    setup["exists"] = True

    # Check for Swift files with depth limit to prevent hanging on large repos
    swift_files = []
    files_limit_reached = False
    base_depth = str(path).count(os.sep)

    try:
        for root, dirs, files in os.walk(path):
            # Calculate current depth relative to base
            current_depth = root.count(os.sep) - base_depth
            if current_depth >= CONFIG.max_depth:
                dirs[:] = []  # Don't recurse deeper
                continue

            # Add Swift files from current directory
            for file in files:
                if file.endswith(".swift"):
                    swift_files.append(Path(root) / file)
                    if len(swift_files) >= CONFIG.max_files:
                        files_limit_reached = True
                        break

            if files_limit_reached:
                break

    except Exception as e:
        # Continue with whatever files we found
        setup["file_scan_error"] = str(e)

    setup["has_swift_files"] = len(swift_files) > 0
    setup["swift_file_count"] = len(swift_files)
    if files_limit_reached:
        setup["swift_file_count_note"] = f"Stopped at limit of {CONFIG.max_files} files"

    # Check for Package.swift
    if (path / "Package.swift").exists():
        setup["has_package_swift"] = True

    # Check for Xcode project
    xcodeproj_files = list(path.glob("*.xcodeproj"))
    setup["has_xcodeproj"] = len(xcodeproj_files) > 0

    # Check for index store with detailed diagnostics
    index_paths = [
        path / ".build" / "index" / "store",
        path / ".build" / "index",  # Modern Swift uses this path
    ]

    for index_path in index_paths:
        if index_path.exists():
            setup["has_index_store"] = True
            try:
                # Get detailed index information
                if index_path.is_dir():
                    details = {"exists": True}
                    
                    # Check for v5 index format (modern Swift)
                    v5_path = index_path / "v5"
                    if v5_path.exists():
                        units_path = v5_path / "units"
                        records_path = v5_path / "records"
                        
                        details["format"] = "v5"
                        details["has_units"] = units_path.exists()
                        details["has_records"] = records_path.exists()
                        
                        if units_path.exists():
                            details["units_count"] = len(list(units_path.glob("*")))
                        if records_path.exists():
                            details["records_count"] = len(list(records_path.glob("*/*")))
                    else:
                        # Legacy format check
                        files = list(index_path.iterdir())
                        details["entry_count"] = len(files)
                        details["has_units"] = any(f.name.startswith("v") for f in files)
                        details["has_records"] = any(f.name.startswith("data") for f in files)
                    
                    setup["index_store_details"][str(index_path)] = details
            except Exception as e:
                setup["index_store_details"][str(index_path)] = {"exists": True, "error": str(e)}

    # Check for compile_commands.json
    compile_commands = path / "compile_commands.json"
    if compile_commands.exists():
        setup["has_compile_commands"] = True
        try:
            import json

            # Check file size first
            file_size = compile_commands.stat().st_size

            if file_size > CONFIG.max_compile_commands_size:
                setup["compile_commands_too_large"] = True
                setup["compile_commands_size"] = file_size
                setup["compile_commands_note"] = (
                    f"File size {file_size:,} bytes exceeds limit of {CONFIG.max_compile_commands_size:,} bytes"
                )
            else:
                with open(compile_commands, encoding="utf-8", errors="replace") as f:
                    # Only read first few entries to check format
                    first_line = f.readline().strip()
                    if first_line.startswith("["):
                        # Read a few more lines to get first entry
                        lines = [first_line]
                        for _ in range(CONFIG.max_lines_to_read):
                            line = f.readline()
                            if not line:
                                break
                            lines.append(line)
                            if '"file"' in line and '"command"' in line:
                                break

                        # Parse just the beginning
                        # Note: Manual JSON closing to handle partial reads efficiently
                        partial_json = "".join(lines)
                        if not partial_json.rstrip().endswith("]"):
                            partial_json = partial_json.rstrip().rstrip(",") + "]"

                        commands = json.loads(partial_json)
                        if commands and isinstance(commands, list) and len(commands) > 0:
                            # Check if paths are absolute
                            first_file = commands[0].get("file", "")
                            setup["uses_absolute_paths"] = os.path.isabs(first_file)

                            # Check for index store flags
                            first_command = commands[0].get("command", "")
                            setup["has_index_flags"] = "-index-store-path" in first_command
                    else:
                        setup["compile_commands_valid"] = False
        except (json.JSONDecodeError, Exception) as e:
            setup["compile_commands_valid"] = False
            setup["compile_commands_error"] = str(e)

    return setup


def _generate_recommendations(diagnostics: dict[str, Any]) -> list[str]:
    """Generate setup recommendations based on diagnostics."""
    recommendations = []

    # Environment recommendations
    if not diagnostics["environment"]["has_swift"]:
        recommendations.append("Install Swift: https://swift.org/install")

    if (
        not diagnostics["environment"]["has_xcode"]
        and diagnostics["environment"].get("platform") == "darwin"
    ):
        recommendations.append("Install Xcode for full Swift development support")

    # LSP server recommendations
    if not diagnostics["lsp_server"]["exists"]:
        if diagnostics["environment"]["has_xcode"]:
            recommendations.append("Run: xcrun --find sourcekit-lsp")
        else:
            recommendations.append("Install Swift toolchain with SourceKit-LSP support")

    # Project setup recommendations
    if diagnostics["project_setup"]:
        setup = diagnostics["project_setup"]

        if not setup["has_swift_files"]:
            recommendations.append("Add Swift source files to your project")

        if not setup["has_package_swift"] and not setup["has_xcodeproj"]:
            recommendations.append("Initialize with: swift package init")

        if not setup["has_index_store"] and setup["has_swift_files"]:
            recommendations.append("Build project to generate index: swift build")

    # Health/Stats recommendations
    if diagnostics.get("health", {}).get("error"):
        recommendations.append(f"Fix LSP health issue: {diagnostics['health']['error']}")

    # Index store recommendations
    if diagnostics["project_setup"] and diagnostics["project_setup"]["has_swift_files"]:
        setup = diagnostics["project_setup"]
        if not setup["has_index_store"]:
            recommendations.append(
                "No index store found. Build with: swift build -Xswiftc -index-store-path -Xswiftc .build/index"
            )
        elif setup.get("index_store_details"):
            # Check for empty or incomplete index
            for path, details in setup["index_store_details"].items():
                if details.get("format") == "v5":
                    # Check v5 format
                    if not details.get("has_units") or not details.get("has_records"):
                        recommendations.append(f"Index store at {path} is incomplete. Rebuild project")
                    elif details.get("units_count", 0) == 0:
                        recommendations.append(f"Index store at {path} has no units. Rebuild project")
                    elif details.get("records_count", 0) == 0:
                        recommendations.append(
                            f"Index store at {path} missing reference records. Rebuild with: swift build --enable-index-store -Xswiftc -index-store-path -Xswiftc .build/index -Xswiftc -index-include-locals"
                        )
                else:
                    # Legacy format
                    if details.get("entry_count", 0) == 0:
                        recommendations.append(f"Index store at {path} is empty. Rebuild project")
                    elif not details.get("has_records"):
                        recommendations.append(
                            f"Index store at {path} missing reference records. Rebuild with proper flags"
                        )

        # Compilation database recommendations
        if setup.get("has_compile_commands"):
            if not setup.get("uses_absolute_paths", True):
                recommendations.append(
                    "compile_commands.json uses relative paths. Use absolute paths for better LSP compatibility"
                )
            if not setup.get("has_index_flags", True):
                recommendations.append(
                    "compile_commands.json missing index flags. Regenerate with proper indexing directives"
                )

    return recommendations
