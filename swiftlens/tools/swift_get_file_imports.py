"""Tool for extracting import statements from a Swift file."""

import os
import re
from typing import Any

from swiftlens.model.models import ErrorType, FileImportsResponse


def swift_get_file_imports(file_path: str) -> dict[str, Any]:
    """Extract all import statements from a Swift file.

    Handles most common Swift import patterns including:
    - Basic imports: import Foundation
    - Submodule imports: import UIKit.UIView
    - Testable imports: @testable import MyApp
    - Multiple attributes: @_exported @testable import SomeFramework
    - Scoped imports: import struct Foundation.Date
    - Implementation-only: @_implementationOnly import SomeModule
    - Trailing comments: import Foundation // comment

    Known limitations:
    - Does not evaluate conditional compilation (#if blocks)
    - May not handle all future Swift import syntax variations
    - Unicode module names support is limited to basic cases

    Args:
        file_path: Path to the Swift file to analyze

    Returns:
        FileImportsResponse as dict with success status, imports, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return FileImportsResponse(
            success=False,
            file_path=file_path,
            imports=[],
            import_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return FileImportsResponse(
            success=False,
            file_path=file_path,
            imports=[],
            import_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    try:
        # Read file content directly - no LSP needed for import extraction
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

            # Extract import statements using improved regex
            # This pattern handles:
            # - Multiple leading attributes (e.g., @_exported @testable)
            # - Scoped imports (e.g., import struct Foundation.Date)
            # - Captures only the import statement itself, ignoring trailing comments
            import_pattern = re.compile(
                r"^\s*"  # Leading whitespace
                r"((?:@\w+\s+)*"  # 0 or more attributes (e.g., @testable)
                r"import(?:\s+(?:struct|class|func|enum|protocol|var|let))?"  # import keyword and optional kind
                r"\s+[A-Za-z_][A-Za-z0-9_.]*)"  # Module name
            )

            imports = []
            raw_imports = []

            for line in content.splitlines():
                match = import_pattern.match(line)
                if match:
                    full_import_statement = match.group(1).strip()
                    raw_imports.append(full_import_statement)

            # Clean up attributes from the captured statements for the final output
            for statement in raw_imports:
                # Remove all leading attributes, not just one
                cleaned_statement = re.sub(r"^(?:@\w+\s+)+", "", statement)
                imports.append(cleaned_statement)

            return FileImportsResponse(
                success=True,
                file_path=file_path,
                imports=imports,
                import_count=len(imports),
            ).model_dump()

    except Exception as e:
        return FileImportsResponse(
            success=False,
            file_path=file_path,
            imports=[],
            import_count=0,
            error=f"Failed to extract imports: {str(e)}",
            error_type=ErrorType.TOOL_INTERNAL_ERROR,
        ).model_dump()
