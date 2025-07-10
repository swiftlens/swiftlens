"""Parser for Swift compiler diagnostic output."""

import re
from dataclasses import dataclass


@dataclass
class SwiftDiagnostic:
    """Represents a Swift compiler diagnostic (error, warning, note)."""

    line: int
    column: int
    type: str  # 'error', 'warning', 'note'
    message: str
    file_path: str | None = None


class SwiftErrorParser:
    """Parser for Swift compiler diagnostic output."""

    def __init__(self):
        """Initialize the error parser with regex patterns."""
        # Standard Swift diagnostic pattern:
        # /path/to/file.swift:line:column: type: message
        self.diagnostic_pattern = re.compile(
            r"^(.+?):(\d+):(\d+):\s+(error|warning|note):\s+(.+)$", re.MULTILINE
        )

        # Alternative pattern for diagnostics without file path:
        # <stdin>:line:column: type: message
        self.stdin_pattern = re.compile(
            r"^<stdin>:(\d+):(\d+):\s+(error|warning|note):\s+(.+)$", re.MULTILINE
        )

        # Pattern for multi-line diagnostics with suggestions
        self.suggestion_pattern = re.compile(r"^\s*\^.*$", re.MULTILINE)

        # Pattern for "help:" or "note:" follow-up messages
        self.followup_pattern = re.compile(r"^\s*(help|note):\s+(.+)$", re.MULTILINE)

    def parse_diagnostics(
        self, stderr_output: str, target_file: str = None
    ) -> list[SwiftDiagnostic]:
        """Parse Swift compiler stderr output into structured diagnostics.

        Args:
            stderr_output: Raw stderr output from swiftc
            target_file: Optional target file path to filter diagnostics

        Returns:
            List of parsed SwiftDiagnostic objects
        """
        diagnostics = []

        if not stderr_output or not stderr_output.strip():
            return diagnostics

        # Parse standard diagnostics with file paths
        for match in self.diagnostic_pattern.finditer(stderr_output):
            file_path, line_str, col_str, diag_type, message = match.groups()

            # Skip if target_file specified and doesn't match
            if target_file and not self._is_target_file(file_path, target_file):
                continue

            try:
                line = int(line_str)
                column = int(col_str)

                diagnostic = SwiftDiagnostic(
                    line=line,
                    column=column,
                    type=diag_type,
                    message=message.strip(),
                    file_path=file_path,
                )
                diagnostics.append(diagnostic)

            except ValueError:
                # Skip if line/column not parseable
                continue

        # Parse stdin diagnostics (when file is passed as stdin)
        for match in self.stdin_pattern.finditer(stderr_output):
            line_str, col_str, diag_type, message = match.groups()

            try:
                line = int(line_str)
                column = int(col_str)

                diagnostic = SwiftDiagnostic(
                    line=line,
                    column=column,
                    type=diag_type,
                    message=message.strip(),
                    file_path=None,
                )
                diagnostics.append(diagnostic)

            except ValueError:
                continue

        # If no structured diagnostics found but stderr has content,
        # try to extract any error information
        if not diagnostics and stderr_output.strip():
            fallback_diagnostic = self._parse_fallback_error(stderr_output)
            if fallback_diagnostic:
                diagnostics.append(fallback_diagnostic)

        return diagnostics

    def format_diagnostics(
        self, diagnostics: list[SwiftDiagnostic], include_summary: bool = True
    ) -> str:
        """Format diagnostics into token-optimized output.

        Args:
            diagnostics: List of SwiftDiagnostic objects
            include_summary: Whether to include summary line

        Returns:
            Formatted diagnostic output
        """
        if not diagnostics:
            return "No errors"

        # Format each diagnostic
        formatted_lines = []
        for diag in diagnostics:
            # Use minimal format: line:col type: message
            line = f"{diag.line}:{diag.column} {diag.type}: {diag.message}"
            formatted_lines.append(line)

        # Add summary if requested
        if include_summary:
            error_count = sum(1 for d in diagnostics if d.type == "error")
            warning_count = sum(1 for d in diagnostics if d.type == "warning")
            note_count = sum(1 for d in diagnostics if d.type == "note")

            summary_parts = []
            if error_count > 0:
                summary_parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            if warning_count > 0:
                summary_parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
            if note_count > 0:
                summary_parts.append(f"{note_count} note{'s' if note_count != 1 else ''}")

            if summary_parts:
                summary = "Summary: " + ", ".join(summary_parts)
                formatted_lines.append(summary)

        return "\n".join(formatted_lines)

    def get_diagnostic_summary(self, diagnostics: list[SwiftDiagnostic]) -> dict[str, int]:
        """Get summary counts of diagnostic types.

        Args:
            diagnostics: List of SwiftDiagnostic objects

        Returns:
            Dictionary with counts by diagnostic type
        """
        summary = {"error": 0, "warning": 0, "note": 0}

        for diag in diagnostics:
            if diag.type in summary:
                summary[diag.type] += 1

        return summary

    def has_errors(self, diagnostics: list[SwiftDiagnostic]) -> bool:
        """Check if diagnostics contain any errors.

        Args:
            diagnostics: List of SwiftDiagnostic objects

        Returns:
            True if any errors are present
        """
        return any(diag.type == "error" for diag in diagnostics)

    def _is_target_file(self, diagnostic_file: str, target_file: str) -> bool:
        """Check if diagnostic file matches target file.

        Args:
            diagnostic_file: File path from diagnostic
            target_file: Target file we're interested in

        Returns:
            True if files match
        """
        # Simple filename comparison (could be made more sophisticated)
        import os

        return os.path.basename(diagnostic_file) == os.path.basename(target_file)

    def _parse_fallback_error(self, stderr_output: str) -> SwiftDiagnostic | None:
        """Parse unstructured error output as fallback.

        Args:
            stderr_output: Raw stderr output

        Returns:
            SwiftDiagnostic object or None
        """
        # Look for common error patterns
        error_patterns = [
            r"error:\s+(.+)",
            r"fatal error:\s+(.+)",
            r"compilation failed:\s+(.+)",
            r"(.+error.+)",  # Generic error detection
        ]

        for pattern in error_patterns:
            match = re.search(pattern, stderr_output, re.IGNORECASE)
            if match:
                message = match.group(1).strip()
                return SwiftDiagnostic(
                    line=0, column=0, type="error", message=message, file_path=None
                )

        # If nothing else, return the first line as a generic error
        first_line = stderr_output.strip().split("\n")[0]
        if first_line:
            return SwiftDiagnostic(
                line=0, column=0, type="error", message=first_line, file_path=None
            )

        return None
