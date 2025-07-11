"""File analysis coordination between LSP operations and symbol analysis."""

import os
import re
from typing import Any

from lsp.client import SwiftLSPClient
from lsp.operations import (
    DefinitionOperation,
    DocumentSymbolsOperation,
    HoverOperation,
    ReferencesOperation,
)
from lsp.protocol import LSPProtocol

from .result_builders import ResultBuilder
from .symbol_analyzer import SymbolAnalyzer


class FileAnalyzer:
    """Coordinates file analysis using LSP operations and symbol analysis."""

    def __init__(self, client: SwiftLSPClient):
        self.client = client
        self.document_symbols_op = DocumentSymbolsOperation(client)
        self.references_op = ReferencesOperation(client)
        self.hover_op = HoverOperation(client)
        self.definition_op = DefinitionOperation(client)
        self.symbol_analyzer = SymbolAnalyzer()
        self.result_builder = ResultBuilder()

    def _find_symbol_declaration_position(
        self, file_lines: list[str], symbol_name: str
    ) -> tuple[int, int]:
        """Find the best position for a symbol, prioritizing declarations over comments/usage.

        Args:
            file_lines: Lines of the Swift file
            symbol_name: Symbol name to find (already sanitized)

        Returns:
            Tuple of (line_num, char_num) both 0-based, or (-1, -1) if not found
        """

        # Define declaration patterns in priority order
        declaration_patterns = [
            (r"class\s+" + re.escape(symbol_name) + r"\b", "class"),
            (r"struct\s+" + re.escape(symbol_name) + r"\b", "struct"),
            (r"enum\s+" + re.escape(symbol_name) + r"\b", "enum"),
            (r"protocol\s+" + re.escape(symbol_name) + r"\b", "protocol"),
            (r"func\s+" + re.escape(symbol_name) + r"\b", "function"),
            (r"var\s+" + re.escape(symbol_name) + r"\b", "variable"),
            (r"let\s+" + re.escape(symbol_name) + r"\b", "constant"),
            (r"typealias\s+" + re.escape(symbol_name) + r"\b", "typealias"),
            (r"extension\s+" + re.escape(symbol_name) + r"\b", "extension"),
        ]

        # First pass: Look for actual declarations (with optional access modifiers)
        for pattern, _decl_type in declaration_patterns:
            # Add support for access modifiers
            full_pattern = r"(?:public\s+|private\s+|internal\s+|fileprivate\s+|open\s+)?" + pattern

            for i, line_text in enumerate(file_lines):
                # Skip comment lines
                stripped = line_text.strip()
                if (
                    stripped.startswith("//")
                    or stripped.startswith("/*")
                    or stripped.startswith("*")
                ):
                    continue

                # Skip string literals - check if we're inside quotes
                # This is a simple heuristic that helps avoid matching symbol names in strings
                quote_count_before = line_text.count(
                    '"', 0, line_text.find(symbol_name) if symbol_name in line_text else 0
                )
                if quote_count_before % 2 == 1:  # Odd number means we're inside a string
                    continue

                match = re.search(full_pattern, line_text)
                if match:
                    # Find the exact position of the symbol name within the match
                    symbol_pos = line_text.find(symbol_name, match.start())
                    if symbol_pos != -1:
                        return (i, symbol_pos)

        # Second pass: Look for type annotations (e.g., ": User")
        type_pattern = r":\s*" + re.escape(symbol_name) + r"\b"
        for i, line_text in enumerate(file_lines):
            # Skip comment lines
            stripped = line_text.strip()
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            match = re.search(type_pattern, line_text)
            if match:
                # Find the exact position of the symbol name
                symbol_pos = line_text.find(symbol_name, match.start())
                if symbol_pos != -1:
                    return (i, symbol_pos)

        # Third pass: Look for any word boundary match (excluding comments and strings)
        pattern = r"\b" + re.escape(symbol_name) + r"\b"
        for i, line_text in enumerate(file_lines):
            # Skip comment lines
            stripped = line_text.strip()
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            # Skip string literals
            quote_count_before = line_text.count(
                '"', 0, line_text.find(symbol_name) if symbol_name in line_text else 0
            )
            if quote_count_before % 2 == 1:
                continue

            match = re.search(pattern, line_text)
            if match:
                return (i, match.start())

        # Fourth pass: Fallback to first occurrence (including comments) for backward compatibility
        for i, line_text in enumerate(file_lines):
            match = re.search(pattern, line_text)
            if match:
                return (i, match.start())

        return (-1, -1)

    def validate_swift_file(self, file_path: str) -> tuple[bool, str | None]:
        """Validate that a file exists and is a Swift file.

        Args:
            file_path: Path to the file to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        if not file_path.endswith(".swift"):
            return False, "File must be a Swift file (.swift extension)"

        return True, None

    def _prepare_lsp_analysis(self, file_path: str) -> tuple[str | None, str | None, str | None]:
        """Validate file, read content, and open in LSP. Returns (file_uri, content, error_message)."""
        is_valid, error_msg = self.validate_swift_file(file_path)
        if not is_valid:
            return None, None, error_msg

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            file_uri = LSPProtocol.create_file_uri(file_path)
            self.client.open_document(file_uri, content)
            return file_uri, content, None
        except Exception as e:
            return None, None, str(e)

    def analyze_file_symbols(self, file_path: str) -> dict[str, Any]:
        """Analyze symbols in a Swift file.

        Args:
            file_path: Path to the Swift file to analyze

        Returns:
            SwiftContextResult-compatible dictionary
        """
        file_uri, content, error_msg = self._prepare_lsp_analysis(file_path)
        if error_msg:
            return self.result_builder.build_error_result(
                file_path=file_path,
                error_message=error_msg,
                result_type="SwiftContextResult",
            )

        try:
            # Get document symbols
            raw_symbols = self.document_symbols_op.execute(file_uri)

            if raw_symbols is not None:
                # Format symbols and count
                formatted_symbols, total_count = self.symbol_analyzer.format_symbols_list(
                    raw_symbols
                )

                return self.result_builder.build_symbol_result(
                    file_path=file_path,
                    symbols=formatted_symbols,
                    symbol_count=total_count,
                )
            else:
                # Check if it's a genuine empty file or LSP failure
                # Try to read the file to verify it exists and has content
                try:
                    with open(file_path, encoding="utf-8") as f:
                        file_content = f.read().strip()
                        if not file_content:
                            # Empty file
                            return self.result_builder.build_symbol_result(
                                file_path=file_path,
                                symbols=[],
                                symbol_count=0,
                            )
                        else:
                            # File has content but LSP failed
                            return self.result_builder.build_error_result(
                                file_path=file_path,
                                error_message="LSP request failed - ensure Swift project is properly built with index store",
                                result_type="SwiftContextResult",
                            )
                except Exception:
                    # File read error
                    return self.result_builder.build_error_result(
                        file_path=file_path,
                        error_message="LSP request failed",
                        result_type="SwiftContextResult",
                    )

        except Exception as e:
            return self.result_builder.build_error_result(
                file_path=file_path,
                error_message=str(e),
                result_type="SwiftContextResult",
            )

    def find_symbol_references(self, file_path: str, symbol_name: str) -> dict[str, Any]:
        """Find references to a symbol in a Swift file.

        Args:
            file_path: Path to the Swift file
            symbol_name: Name of the symbol to find references for

        Returns:
            SymbolReferenceResult-compatible dictionary
        """
        file_uri, content, error_msg = self._prepare_lsp_analysis(file_path)
        if error_msg:
            return self.result_builder.build_error_result(
                file_path=file_path,
                symbol_name=symbol_name,
                error_message=error_msg,
                result_type="SymbolReferenceResult",
            )

        try:
            file_lines = content.split("\n")

            # Sanitize symbol name, removing parentheses for functions/methods
            symbol_to_find = symbol_name.replace("()", "")

            # Use improved symbol position finding that prioritizes declarations
            line_num, char_num = self._find_symbol_declaration_position(file_lines, symbol_to_find)

            if line_num == -1:
                # Symbol not found in file - this is a valid result with 0 references
                return self.result_builder.build_reference_result(
                    file_path=file_path, symbol_name=symbol_name, references=[]
                )

            symbol_position = LSPProtocol.create_position(line_num, char_num)

            # Get references to the symbol
            raw_references = self.references_op.execute(file_uri, symbol_position)

            if raw_references is None:
                return self.result_builder.build_error_result(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    error_message="Failed to get symbol references",
                    result_type="SymbolReferenceResult",
                )

            # Filter references to only those in the current file
            # This ensures we only return references within the requested file
            filtered_references = []
            import os

            normalized_file_path = os.path.abspath(file_path)

            for ref in raw_references:
                ref_uri = ref.get("uri", "")
                # Check if the reference is in the current file
                if ref_uri == file_uri:
                    filtered_references.append(ref)
                elif ref_uri.startswith("file://"):
                    # Extract path from file URI and normalize it
                    ref_path = ref_uri.replace("file://", "")
                    ref_path = os.path.abspath(ref_path)
                    if ref_path == normalized_file_path:
                        filtered_references.append(ref)

            # Format references
            formatted_references = self.references_op.format_references(
                filtered_references, file_lines
            )

            return self.result_builder.build_reference_result(
                file_path=file_path,
                symbol_name=symbol_name,
                references=formatted_references,
            )

        except Exception as e:
            return self.result_builder.build_error_result(
                file_path=file_path,
                symbol_name=symbol_name,
                error_message=str(e),
                result_type="SymbolReferenceResult",
            )

    def get_hover_info(self, file_path: str, line: int, character: int) -> dict[str, Any]:
        """Get hover information for a position in a Swift file.

        Args:
            file_path: Path to the Swift file
            line: Line number (1-based)
            character: Character position (1-based)

        Returns:
            HoverInfoResult-compatible dictionary
        """
        file_uri, content, error_msg = self._prepare_lsp_analysis(file_path)
        if error_msg:
            return self.result_builder.build_error_result(
                file_path=file_path,
                line=line,
                character=character,
                error_message=error_msg,
                result_type="HoverInfoResult",
            )

        try:
            # Add delay for LSP server to process the document
            import time

            time.sleep(0.2)

            # Debug logging
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"Getting hover info for {file_path} at line {line}, character {character}"
            )

            # Convert 1-based line and character to 0-based for LSP
            position = LSPProtocol.create_position(line - 1, character - 1)

            # Get hover information from LSP
            hover_data = self.hover_op.execute(file_uri, position)

            logger.debug(f"Hover data received: {hover_data}")

            if hover_data:
                hover_content = self.hover_op.extract_hover_content(hover_data)

                return self.result_builder.build_hover_result(
                    file_path=file_path,
                    line=line,
                    character=character,
                    hover_info=hover_content,
                )
            else:
                return self.result_builder.build_error_result(
                    file_path=file_path,
                    line=line,
                    character=character,
                    error_message="No hover information available at this position",
                    result_type="HoverInfoResult",
                )

        except Exception as e:
            return self.result_builder.build_error_result(
                file_path=file_path,
                line=line,
                character=character,
                error_message=str(e),
                result_type="HoverInfoResult",
            )

    def get_symbol_definition(self, file_path: str, symbol_name: str) -> dict[str, Any]:
        """Get definition location for a symbol in a Swift file.

        Args:
            file_path: Path to the Swift file containing the symbol
            symbol_name: Name of the symbol to find definition for

        Returns:
            SymbolDefinitionResult-compatible dictionary
        """
        file_uri, content, error_msg = self._prepare_lsp_analysis(file_path)
        if error_msg:
            return self.result_builder.build_error_result(
                file_path=file_path,
                symbol_name=symbol_name,
                error_message=error_msg,
                result_type="SymbolDefinitionResult",
            )

        try:
            # Use improved symbol position finding that prioritizes declarations
            file_lines = content.split("\n")
            line_num, char_num = self._find_symbol_declaration_position(file_lines, symbol_name)

            if line_num == -1:
                return self.result_builder.build_error_result(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    error_message=f"Symbol '{symbol_name}' not found in file",
                    result_type="SymbolDefinitionResult",
                )

            symbol_position = LSPProtocol.create_position(line_num, char_num)

            # Get definition for the symbol
            raw_definitions = self.definition_op.execute(file_uri, symbol_position)

            if raw_definitions is None:
                return self.result_builder.build_error_result(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    error_message="Failed to get symbol definition",
                    result_type="SymbolDefinitionResult",
                )

            # Format definitions
            formatted_definitions = self.definition_op.format_definition(raw_definitions)

            return self.result_builder.build_definition_result(
                file_path=file_path,
                symbol_name=symbol_name,
                definitions=formatted_definitions,
            )

        except Exception as e:
            return self.result_builder.build_error_result(
                file_path=file_path,
                symbol_name=symbol_name,
                error_message=str(e),
                result_type="SymbolDefinitionResult",
            )
