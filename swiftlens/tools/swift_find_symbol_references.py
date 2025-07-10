"""Tool for finding references to a specific symbol in a Swift file."""

import os
from typing import Any

from analysis.file_analyzer import FileAnalyzer
from lsp.managed_client import find_swift_project_root, managed_lsp_client
from model.models import ErrorType, SymbolReference, SymbolReferenceResponse
from pydantic import ValidationError


def swift_find_symbol_references(file_path: str, symbol_name: str, client=None) -> dict[str, Any]:
    """Find all references to a symbol in the given Swift file.

    Args:
        file_path: Path to the Swift file to analyze
        symbol_name: Name of the symbol to find references for
        client: Optional pre-initialized SwiftLSPClient for performance optimization

    Returns:
        SymbolReferenceResponse as dict with success status, references, and metadata
    """

    # Convert to absolute path if relative
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    # Early validation
    if not file_path.endswith(".swift"):
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error="File must be a Swift file (.swift extension)",
            error_type=ErrorType.VALIDATION_ERROR,
        ).model_dump()

    if not os.path.exists(file_path):
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=f"File not found: {file_path}",
            error_type=ErrorType.FILE_NOT_FOUND,
        ).model_dump()

    try:
        if client:
            # Use provided client (performance optimization for tests)
            analyzer = FileAnalyzer(client)
            result_dict = analyzer.find_symbol_references(file_path, symbol_name)
        else:
            # Fall back to creating new client (backward compatibility)
            project_root = find_swift_project_root(file_path)

            with managed_lsp_client(project_root=project_root, timeout=10.0) as new_client:
                analyzer = FileAnalyzer(new_client)
                result_dict = analyzer.find_symbol_references(file_path, symbol_name)

        if result_dict["success"]:
            # Convert references to Pydantic models
            references = []
            for ref in result_dict["references"]:
                try:
                    symbol_ref = SymbolReference(
                        file_path=ref.get("file_path", file_path),
                        line=ref["line"],
                        character=ref["character"],
                        context=ref["context_line"].strip() if ref["context_line"] else "",
                    )
                    references.append(symbol_ref)
                except ValidationError:
                    # Skip invalid references but continue processing
                    continue

            response = SymbolReferenceResponse(
                success=True,
                file_path=file_path,
                symbol_name=symbol_name,
                references=references,
                reference_count=len(references),
            )

            # Add diagnostic information if no references found
            if len(references) == 0:
                response_dict = response.model_dump()

                # Check for index store existence
                index_diagnostics = []
                if project_root:
                    index_paths = [
                        os.path.join(project_root, ".build", "debug", "index", "store"),
                        os.path.join(project_root, ".build", "release", "index", "store"),
                        os.path.join(project_root, "DerivedData"),
                    ]

                    index_found = False
                    for index_path in index_paths:
                        if os.path.exists(index_path):
                            index_found = True
                            try:
                                # Check if index has content
                                files = os.listdir(index_path)
                                if len(files) > 0:
                                    index_diagnostics.append(
                                        f"Index found at {index_path} with {len(files)} entries"
                                    )
                                else:
                                    index_diagnostics.append(f"Empty index at {index_path}")
                            except Exception:
                                pass

                    if not index_found:
                        index_diagnostics.append(
                            "No index store found. Run 'swift build' to generate index"
                        )

                response_dict["diagnostics"] = {
                    "note": "No references found. This may be due to:",
                    "possible_causes": [
                        "Symbol genuinely has no references",
                        "Index store is incomplete (missing reference occurrences)",
                        "Test environment limitations (see project documentation)",
                        "Build was done without proper indexing flags",
                    ],
                    "recommendations": [
                        "Ensure project is built with: swift build -Xswiftc -index-store-path -Xswiftc .build/index/store",
                        "For production projects, use within Xcode or VS Code with Swift extension",
                        "Check that compile_commands.json uses absolute paths",
                    ],
                    "index_status": index_diagnostics
                    if index_diagnostics
                    else ["Index status unknown"],
                }
                return response_dict

            return response.model_dump()

    except Exception as e:
        return SymbolReferenceResponse(
            success=False,
            file_path=file_path,
            symbol_name=symbol_name,
            references=[],
            reference_count=0,
            error=str(e),
            error_type=ErrorType.LSP_ERROR,
        ).model_dump()
