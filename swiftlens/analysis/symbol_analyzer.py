"""Symbol analysis utilities for processing LSP symbol data."""

from typing import Any

from lsp.constants import SymbolKind


class SymbolAnalyzer:
    """Analyzes and formats Swift symbols from LSP data."""

    @staticmethod
    def format_symbol(symbol_data: dict[str, Any]) -> dict[str, Any]:
        """Convert LSP symbol data to our formatted symbol structure.

        Args:
            symbol_data: Raw symbol data from LSP

        Returns:
            Formatted symbol dictionary
        """
        name = symbol_data.get("name", "Unknown")
        kind = symbol_data.get("kind", 0)
        kind_name = SymbolKind.get_name(kind)

        # Extract position information from range or selectionRange
        line = 1  # Default to line 1
        character = 0  # Default to character 0

        # Try to get position from selectionRange first (more precise)
        selection_range = symbol_data.get("selectionRange", {})
        if selection_range and "start" in selection_range:
            line = selection_range["start"].get("line", 0) + 1  # Convert to 1-based
            character = selection_range["start"].get("character", 0)
        else:
            # Fall back to range if selectionRange not available
            range_data = symbol_data.get("range", {})
            if range_data and "start" in range_data:
                line = range_data["start"].get("line", 0) + 1  # Convert to 1-based
                character = range_data["start"].get("character", 0)

        # Process children recursively
        children = []
        for child_data in symbol_data.get("children", []):
            children.append(SymbolAnalyzer.format_symbol(child_data))

        return {
            "name": name,
            "kind": kind,
            "kind_name": kind_name,
            "line": line,
            "character": character,
            "children": children,
            "child_count": len(children),
        }

    @staticmethod
    def count_symbols(symbol: dict[str, Any]) -> int:
        """Recursively count all symbols including children.

        Args:
            symbol: Formatted symbol dictionary

        Returns:
            Total count of symbols in the tree
        """
        count = 1  # Count this symbol
        for child in symbol.get("children", []):
            count += SymbolAnalyzer.count_symbols(child)
        return count

    @staticmethod
    def format_symbols_list(
        raw_symbols: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        """Format a list of raw LSP symbols and count total symbols.

        Args:
            raw_symbols: List of raw symbol data from LSP

        Returns:
            Tuple of (formatted_symbols_list, total_symbol_count)
        """
        formatted_symbols = []
        total_count = 0

        for symbol_data in raw_symbols:
            formatted_symbol = SymbolAnalyzer.format_symbol(symbol_data)
            formatted_symbols.append(formatted_symbol)
            total_count += SymbolAnalyzer.count_symbols(formatted_symbol)

        return formatted_symbols, total_count

    @staticmethod
    def find_symbol_in_tree(
        symbols: list[dict[str, Any]], symbol_name: str
    ) -> dict[str, Any] | None:
        """Find a symbol by name in a symbol tree.

        Args:
            symbols: List of formatted symbols to search
            symbol_name: Name of symbol to find

        Returns:
            Symbol dictionary if found, None otherwise
        """
        for symbol in symbols:
            if symbol.get("name") == symbol_name:
                return symbol

            # Search in children
            children = symbol.get("children", [])
            if children:
                result = SymbolAnalyzer.find_symbol_in_tree(children, symbol_name)
                if result:
                    return result

        return None

    @staticmethod
    def get_symbol_path(
        symbols: list[dict[str, Any]], symbol_name: str, current_path: list[str] = None
    ) -> list[str] | None:
        """Get the path to a symbol in the symbol tree.

        Args:
            symbols: List of formatted symbols to search
            symbol_name: Name of symbol to find
            current_path: Current path being built (for recursion)

        Returns:
            List of symbol names representing the path, or None if not found
        """
        if current_path is None:
            current_path = []

        for symbol in symbols:
            symbol_path = current_path + [symbol.get("name", "")]

            if symbol.get("name") == symbol_name:
                return symbol_path

            # Search in children
            children = symbol.get("children", [])
            if children:
                result = SymbolAnalyzer.get_symbol_path(children, symbol_name, symbol_path)
                if result:
                    return result

        return None

    @staticmethod
    def get_all_declaration_contexts(
        symbols: list[dict[str, Any]], parent_path: str = ""
    ) -> list[dict[str, Any]]:
        """Get all declaration contexts (fully-qualified names) for symbols in a tree.

        Args:
            symbols: List of formatted symbols to process
            parent_path: Current parent path for building qualified names

        Returns:
            List of dictionaries with 'qualified_name', 'name', and 'kind_name' keys
        """
        contexts = []

        for symbol in symbols:
            name = symbol.get("name", "")
            kind_name = symbol.get("kind_name", "unknown")

            # Build the qualified name
            if parent_path:
                qualified_name = f"{parent_path}.{name}"
            else:
                qualified_name = name

            # Add this symbol's context
            contexts.append(
                {"qualified_name": qualified_name, "name": name, "kind_name": kind_name}
            )

            # Recursively process children
            children = symbol.get("children", [])
            if children:
                child_contexts = SymbolAnalyzer.get_all_declaration_contexts(
                    children, qualified_name
                )
                contexts.extend(child_contexts)

        return contexts
