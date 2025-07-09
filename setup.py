#!/usr/bin/env python3
"""
Setup script for SwiftLens MCP Server
Simple Python package that uses pre-compiled swiftlens-core for LSP functionality
"""

import os
import sys

from setuptools import find_packages, setup


def main():
    """Main setup function"""
    # Platform validation - require macOS
    if sys.platform != "darwin":
        print("ERROR: SwiftLens MCP Server requires macOS.")
        print(f"Current platform: {sys.platform}")
        print(
            "This tool depends on Xcode development tools (xcrun, sourcekit-lsp) that are only available on macOS."
        )
        sys.exit(1)

    # Read requirements
    requirements = []
    if os.path.exists("requirements.txt"):
        with open("requirements.txt") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # Read long description
    long_description = ""
    if os.path.exists("README.md"):
        with open("README.md", encoding="utf-8") as f:
            long_description = f.read()

    # Read version from _version.py
    version = {}
    with open("src/_version.py") as f:
        exec(f.read(), version)

    setup(
        name="swiftlens",
        version=version["__version__"],
        description="Professional Swift code semantic analysis MCP server with enhanced AI capabilities",
        long_description=long_description,
        long_description_content_type="text/markdown",
        author="SwiftLens Devs",
        author_email="devs@swiftlens.tools",
        url="https://github.com/swiftlens/swiftlens",
        # Package configuration
        packages=find_packages(include=["src*"]),
        # Include static files for dashboard
        package_data={
            "src.dashboard": ["static/*"],
        },
        # Dependencies
        install_requires=requirements,
        extras_require={
            "dev": [
                "pytest>=7.0.0",
                "pytest-asyncio>=0.21.0",
                "black",
                "isort",
                "mypy",
                "ruff",
            ],
        },
        # Entry points
        entry_points={
            "console_scripts": [
                "swiftlens=src.server:main",
            ],
        },
        # Metadata
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "License :: Other/Proprietary License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Programming Language :: Python :: 3.13",
            "Topic :: Software Development :: Quality Assurance",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Text Processing :: Linguistic",
            "Topic :: Utilities",
        ],
        python_requires=">=3.10",
        # Platform requirement
        platforms=["macosx"],
        # Build settings
        zip_safe=True,  # No compiled extensions now
        include_package_data=True,
    )


if __name__ == "__main__":
    main()
