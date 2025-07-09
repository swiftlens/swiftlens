"""Result builders for creating standardized result objects."""

from typing import Any


class ResultBuilder:
    """Builds standardized result dictionaries compatible with existing models."""

    @staticmethod
    def build_symbol_result(
        file_path: str, symbols: list[dict[str, Any]], symbol_count: int
    ) -> dict[str, Any]:
        """Build a successful SwiftContextResult-compatible dictionary.

        Args:
            file_path: Path to the analyzed file
            symbols: List of formatted symbols
            symbol_count: Total count of symbols

        Returns:
            SwiftContextResult-compatible dictionary
        """
        return {
            "file_path": file_path,
            "symbols": symbols,
            "symbol_count": symbol_count,
            "success": True,
            "error_message": None,
        }

    @staticmethod
    def build_reference_result(
        file_path: str, symbol_name: str, references: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a successful SymbolReferenceResult-compatible dictionary.

        Args:
            file_path: Path to the analyzed file
            symbol_name: Name of the symbol
            references: List of formatted references

        Returns:
            SymbolReferenceResult-compatible dictionary
        """
        return {
            "file_path": file_path,
            "symbol_name": symbol_name,
            "references": references,
            "reference_count": len(references),
            "success": True,
            "error_message": None,
        }

    @staticmethod
    def build_hover_result(
        file_path: str, line: int, character: int, hover_info: str | None
    ) -> dict[str, Any]:
        """Build a successful HoverInfoResult-compatible dictionary.

        Args:
            file_path: Path to the analyzed file
            line: Line number (1-based)
            character: Character position (1-based)
            hover_info: Hover information text

        Returns:
            HoverInfoResult-compatible dictionary
        """
        return {
            "file_path": file_path,
            "line": line,
            "character": character,
            "hover_info": hover_info,
            "success": True,
            "error_message": None,
        }

    @staticmethod
    def build_definition_result(
        file_path: str, symbol_name: str, definitions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a successful SymbolDefinitionResult-compatible dictionary.

        Args:
            file_path: Path to the analyzed file
            symbol_name: Name of the symbol
            definitions: List of formatted definition locations

        Returns:
            SymbolDefinitionResult-compatible dictionary
        """
        return {
            "file_path": file_path,
            "symbol_name": symbol_name,
            "definitions": definitions,
            "definition_count": len(definitions),
            "success": True,
            "error_message": None,
        }

    @staticmethod
    def build_error_result(
        file_path: str, error_message: str, result_type: str, **kwargs
    ) -> dict[str, Any]:
        """Build an error result dictionary.

        Args:
            file_path: Path to the file that caused the error
            error_message: Error message describing what went wrong
            result_type: Type of result being built (for proper structure)
            **kwargs: Additional fields specific to the result type

        Returns:
            Error result dictionary compatible with the specified result type
        """
        base_result = {
            "file_path": file_path,
            "success": False,
            "error_message": error_message,
        }

        # Add type-specific fields with default values
        if result_type == "SwiftContextResult":
            base_result.update(
                {
                    "symbols": [],
                    "symbol_count": 0,
                }
            )
        elif result_type == "SymbolReferenceResult":
            base_result.update(
                {
                    "symbol_name": kwargs.get("symbol_name", ""),
                    "references": [],
                    "reference_count": 0,
                }
            )
        elif result_type == "HoverInfoResult":
            base_result.update(
                {
                    "line": kwargs.get("line", 0),
                    "character": kwargs.get("character", 0),
                    "hover_info": None,
                }
            )
        elif result_type == "SymbolDefinitionResult":
            base_result.update(
                {
                    "symbol_name": kwargs.get("symbol_name", ""),
                    "definitions": [],
                    "definition_count": 0,
                }
            )

        return base_result
