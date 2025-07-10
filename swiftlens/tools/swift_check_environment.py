"""Tool for checking Swift development environment."""

import os
import subprocess
import sys
from typing import Any

from swiftlens.model.models import EnvironmentCheckResponse, ErrorType


def swift_check_environment() -> dict[str, Any]:
    """Check if Swift development environment is properly configured on macOS.

    This tool requires macOS as it depends on Xcode development tools.

    Returns:
        EnvironmentCheckResponse as dict with success status, environment details, and recommendations
    """
    # Platform validation - require macOS
    if sys.platform != "darwin":
        return EnvironmentCheckResponse(
            success=False,
            environment={},
            ready=False,
            recommendations=[],
            error=f"Swift Context MCP Server requires macOS. Current platform: {sys.platform}",
            error_type=ErrorType.ENVIRONMENT_ERROR,
        ).model_dump()

    try:
        environment = {
            "xcrun_available": False,
            "sourcekit_lsp_available": False,
            "xcode_select_path": None,
            "python_version": None,
            "working_directory": os.getcwd(),
            "project_type": None,
            "index_store_available": False,
            "build_required": False,
        }
        recommendations = []

        # Check xcrun (required on macOS)
        try:
            result = subprocess.run(
                ["xcrun", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                environment["xcrun_available"] = True
            else:
                recommendations.append("Install Xcode or Xcode Command Line Tools")
        except Exception:
            recommendations.append("Install Xcode or Xcode Command Line Tools")

        # Check sourcekit-lsp using xcrun
        try:
            result = subprocess.run(
                ["xcrun", "sourcekit-lsp", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                environment["sourcekit_lsp_available"] = True
            else:
                recommendations.append("Install full Xcode (not just Command Line Tools)")
        except Exception:
            recommendations.append("Install full Xcode and configure xcode-select")

        # Check xcode-select path
        try:
            result = subprocess.run(
                ["xcode-select", "-p"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                environment["xcode_select_path"] = result.stdout.strip()
                if "CommandLineTools" in environment["xcode_select_path"]:
                    recommendations.append(
                        "Switch to full Xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
                    )
        except Exception:
            recommendations.append("Configure xcode-select properly")

        # Python version
        environment["python_version"] = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

        # Check project type and index store
        _check_project_setup(environment, recommendations)

        # Overall status
        ready = (
            environment["xcrun_available"]
            and environment["sourcekit_lsp_available"]
            and len(recommendations) == 0
        )

        return EnvironmentCheckResponse(
            success=True,
            environment=environment,
            ready=ready,
            recommendations=recommendations,
        ).model_dump()

    except Exception as e:
        return EnvironmentCheckResponse(
            success=False,
            environment=environment,  # Return populated environment even on error
            ready=False,
            recommendations=recommendations,
            error=str(e),
            error_type=ErrorType.ENVIRONMENT_ERROR,
        ).model_dump()


def _check_project_setup(environment: dict[str, Any], recommendations: list[str]) -> None:
    """Check project type and index store availability."""
    cwd = environment["working_directory"]

    # Check for Swift Package Manager project
    if os.path.exists(os.path.join(cwd, "Package.swift")):
        environment["project_type"] = "Swift Package Manager"

        # Check for .build directory (indicates project has been built)
        build_dir = os.path.join(cwd, ".build")
        if os.path.exists(build_dir):
            # Look for index store in build directory
            index_stores = []
            for root, _dirs, _files in os.walk(build_dir):
                if "IndexStoreDB" in root or "index" in root.lower():
                    index_stores.append(root)

            if index_stores:
                environment["index_store_available"] = True
            else:
                environment["build_required"] = True
                recommendations.append(
                    "Run 'swift build' to generate index store for LSP functionality"
                )
        else:
            environment["build_required"] = True
            recommendations.append("Run 'swift build' to create .build directory and index store")

    # Check for Xcode project
    elif any(item.endswith((".xcodeproj", ".xcworkspace")) for item in os.listdir(cwd)):
        environment["project_type"] = "Xcode Project"

        # Look for common Xcode build output locations
        xcode_build_locations = [
            os.path.join(cwd, "DerivedData"),
            os.path.expanduser("~/Library/Developer/Xcode/DerivedData"),
        ]

        # Check for project-specific derived data
        project_files = [f for f in os.listdir(cwd) if f.endswith((".xcodeproj", ".xcworkspace"))]
        if project_files:
            project_name = project_files[0].split(".")[0]

            # Check for index store in common locations
            index_found = False
            for location in xcode_build_locations:
                if os.path.exists(location):
                    for item in os.listdir(location):
                        if project_name.lower() in item.lower():
                            # Check both possible IndexStoreDB locations
                            possible_paths = [
                                os.path.join(location, item, "Index", "DataStore"),
                                os.path.join(location, item, "Index.noindex", "DataStore"),
                            ]
                            for index_path in possible_paths:
                                if os.path.exists(index_path):
                                    environment["index_store_available"] = True
                                    index_found = True
                                    break
                            if index_found:
                                break
                    if index_found:
                        break

            if not index_found:
                environment["build_required"] = True
                recommendations.extend(
                    [
                        f"Build your Xcode project ({project_files[0]}) at least once to generate index store",
                        "Ensure COMPILER_INDEX_STORE_ENABLE=YES (default) in build settings",
                        "Consider installing xcode-build-server for better LSP integration: brew install xcode-build-server",
                    ]
                )

    else:
        environment["project_type"] = "Unknown"
        recommendations.append(
            "No Swift project detected. Create Package.swift or open .xcodeproj/.xcworkspace"
        )
