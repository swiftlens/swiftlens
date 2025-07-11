"""Atomic file modification utilities for Swift code insertion operations."""

import os
import shutil
import tempfile
import time
from dataclasses import dataclass


@dataclass
class IndentationInfo:
    """Information about indentation style in a Swift file."""

    type: str  # 'spaces', 'tabs', 'mixed'
    size: int  # Number of spaces or 1 for tabs
    detected_from_line: int


@dataclass
class OperationResult:
    """Result of a file modification operation."""

    success: bool
    message: str
    backup_path: str | None = None


class SwiftFileModifier:
    """Safe atomic file modification utilities with backup/restore capabilities."""

    def __init__(self, file_path: str, operation_timeout: float = 30.0):
        """Initialize file modifier with comprehensive security validation.

        Args:
            file_path: Path to the Swift file to modify
            operation_timeout: Maximum time for file operations in seconds

        Raises:
            ValueError: If file path validation fails
        """
        # Security and safety limits - set before validation
        self.max_file_size = 10 * 1024 * 1024  # 10MB limit
        self.max_content_size = 10 * 1024  # 10KB per insertion
        self.max_line_length = 500  # Maximum line length
        self.operation_timeout = max(5.0, min(operation_timeout, 60.0))  # 5-60 seconds

        self._file_path = self._validate_and_resolve_path(file_path)
        self._backup_path = None
        self._original_content = None
        self._modified = False
        self._operation_start_time = None

    def _validate_and_resolve_path(self, file_path: str) -> str:
        """Validate and resolve file path with comprehensive security checks.

        Args:
            file_path: Input file path to validate

        Returns:
            Validated absolute file path

        Raises:
            ValueError: If validation fails
        """
        if not file_path or not isinstance(file_path, str):
            raise ValueError("File path must be a non-empty string")

        # Prevent null byte injection
        if "\0" in file_path:
            raise ValueError("Invalid file path contains null bytes")

        # Convert to absolute path and resolve symlinks
        try:
            abs_path = os.path.abspath(file_path)
            real_path = os.path.realpath(abs_path)
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid file path: {str(e)}") from e

        # Validate path length
        if len(real_path) > 4096:
            raise ValueError("File path too long")

        # Ensure file exists and is a regular file
        if not os.path.exists(real_path):
            raise ValueError(f"File not found: {file_path}")

        if not os.path.isfile(real_path):
            raise ValueError(f"Not a regular file: {file_path}")

        # Validate Swift file extension
        if not real_path.endswith(".swift"):
            raise ValueError(f"Not a Swift file: {file_path}")

        # Check file size limits
        try:
            file_size = os.path.getsize(real_path)
            if file_size > self.max_file_size:
                size_mb = file_size / (1024 * 1024)
                limit_mb = self.max_file_size / (1024 * 1024)
                raise ValueError(f"File too large: {size_mb:.1f}MB (limit: {limit_mb:.1f}MB)")
        except OSError as e:
            raise ValueError(f"Cannot access file: {str(e)}") from e

        # Check file permissions
        if not os.access(real_path, os.R_OK | os.W_OK):
            raise ValueError(f"Insufficient file permissions: {file_path}")

        return real_path

    def _check_operation_timeout(self) -> None:
        """Check if operation has exceeded timeout limit.

        Raises:
            TimeoutError: If operation timeout exceeded
        """
        if self._operation_start_time is None:
            return

        elapsed = time.time() - self._operation_start_time
        if elapsed > self.operation_timeout:
            raise TimeoutError(f"File operation timeout after {elapsed:.1f} seconds")

    def _start_operation_timer(self) -> None:
        """Start timing a file operation."""
        self._operation_start_time = time.time()

    def _validate_content(self, content: str) -> None:
        """Validate insertion content for security and safety.

        Args:
            content: Content to validate

        Raises:
            ValueError: If content validation fails
        """
        if not isinstance(content, str):
            raise ValueError("Content must be a string")

        # Check content size
        if len(content.encode("utf-8")) > self.max_content_size:
            size_kb = len(content.encode("utf-8")) / 1024
            limit_kb = self.max_content_size / 1024
            raise ValueError(f"Content too large: {size_kb:.1f}KB (limit: {limit_kb:.1f}KB)")

        # Check for null bytes
        if "\0" in content:
            raise ValueError("Content contains null bytes")

        # Check line length limits
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if len(line) > self.max_line_length:
                raise ValueError(
                    f"Line {i + 1} too long: {len(line)} chars (limit: {self.max_line_length})"
                )

        # Basic Swift syntax safety checks
        dangerous_patterns = [
            "system(",
            "dlopen(",
            "dlsym(",
            "__bridge",
            "UnsafePointer",
            "UnsafeMutablePointer",
        ]

        content_lower = content.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in content_lower:
                raise ValueError(
                    f"Content contains potentially dangerous Swift construct: {pattern}"
                )

    def _create_backup(self) -> str:
        """Create a secure backup of the original file.

        Returns:
            Path to the backup file

        Raises:
            IOError: If backup creation fails
        """
        try:
            # Create backup in secure temporary directory
            backup_dir = tempfile.mkdtemp(prefix="swift_backup_")
            backup_filename = f"{os.path.basename(self._file_path)}.backup.{int(time.time())}"
            backup_path = os.path.join(backup_dir, backup_filename)

            # Copy original file to backup
            shutil.copy2(self._file_path, backup_path)

            # Verify backup integrity
            if not os.path.exists(backup_path):
                raise OSError("Backup file was not created")

            original_size = os.path.getsize(self._file_path)
            backup_size = os.path.getsize(backup_path)

            if original_size != backup_size:
                os.remove(backup_path)
                raise OSError("Backup file size mismatch")

            self._backup_path = backup_path
            return backup_path

        except (OSError, shutil.Error) as e:
            raise OSError(f"Failed to create backup: {str(e)}") from e

    def _read_file_content(self) -> str:
        """Read and cache the original file content.

        Returns:
            File content as string

        Raises:
            IOError: If file reading fails
        """
        if self._original_content is not None:
            return self._original_content

        try:
            with open(self._file_path, encoding="utf-8") as f:
                content = f.read()

            self._original_content = content
            return content

        except (OSError, UnicodeDecodeError) as e:
            raise OSError(f"Failed to read file: {str(e)}") from e

    def detect_indentation(self, around_line: int = 0) -> IndentationInfo:
        """Detect indentation style from the Swift file.

        Args:
            around_line: Line number to focus detection around (0-based)

        Returns:
            IndentationInfo with detected style
        """
        content = self._read_file_content()
        lines = content.split("\n")

        # Count indentation patterns
        space_count = 0
        tab_count = 0
        space_sizes = {}

        # Look for indented lines around the target area
        start_line = max(0, around_line - 10)
        end_line = min(len(lines), around_line + 10)

        for i in range(start_line, end_line):
            if i >= len(lines):
                break

            line = lines[i]
            if not line.strip():  # Skip empty lines
                continue

            # Count leading whitespace
            leading_spaces = len(line) - len(line.lstrip(" "))
            leading_tabs = len(line) - len(line.lstrip("\t"))

            if leading_tabs > 0:
                tab_count += 1
            elif leading_spaces > 0:
                space_count += 1
                # Track space group sizes
                if leading_spaces not in space_sizes:
                    space_sizes[leading_spaces] = 0
                space_sizes[leading_spaces] += 1

        # Determine indentation style
        if tab_count > space_count:
            return IndentationInfo("tabs", 1, around_line)
        elif space_count > 0:
            # Find most common space size
            if space_sizes:
                most_common_size = max(space_sizes.keys(), key=lambda x: space_sizes[x])
                # Infer indentation size (commonly 2 or 4 spaces)
                indent_size = 4 if most_common_size >= 4 else 2
            else:
                indent_size = 4  # Default
            return IndentationInfo("spaces", indent_size, around_line)
        else:
            # No indentation detected, use default
            return IndentationInfo("spaces", 4, around_line)

    def insert_before_line(
        self, line_number: int, content: str, preserve_indentation: bool = True
    ) -> OperationResult:
        """Insert content before a specific line with proper indentation.

        Args:
            line_number: Line number to insert before (1-based)
            content: Content to insert
            preserve_indentation: Whether to match surrounding indentation

        Returns:
            OperationResult with operation status
        """
        try:
            self._start_operation_timer()
            self._validate_content(content)
            self._check_operation_timeout()

            # Create backup before any modifications
            backup_path = self._create_backup()
            self._check_operation_timeout()

            # Read original content
            original_content = self._read_file_content()
            lines = original_content.split("\n")
            self._check_operation_timeout()

            # Validate line number
            if line_number < 1 or line_number > len(lines) + 1:
                return OperationResult(
                    False,
                    f"Invalid line number: {line_number} (file has {len(lines)} lines)",
                )

            # Prepare content with proper indentation
            if preserve_indentation and line_number <= len(lines):
                indent_info = self.detect_indentation(line_number - 1)
                content = self._apply_indentation(content, indent_info, lines, line_number - 1)
            self._check_operation_timeout()

            # Insert content
            insert_index = line_number - 1
            content_lines = content.split("\n")

            # Insert new lines
            new_lines = lines[:insert_index] + content_lines + lines[insert_index:]
            new_content = "\n".join(new_lines)
            self._check_operation_timeout()

            # Write atomically
            self._write_content_atomically(new_content)
            self._modified = True

            return OperationResult(
                True,
                f"Inserted {len(content_lines)} lines before line {line_number}",
                backup_path,
            )

        except (OSError, ValueError, TimeoutError) as e:
            return OperationResult(False, f"Error: {str(e)}")

    def insert_after_line(
        self, line_number: int, content: str, preserve_indentation: bool = True
    ) -> OperationResult:
        """Insert content after a specific line with proper indentation.

        Args:
            line_number: Line number to insert after (1-based)
            content: Content to insert
            preserve_indentation: Whether to match surrounding indentation

        Returns:
            OperationResult with operation status
        """
        try:
            self._start_operation_timer()
            self._validate_content(content)
            self._check_operation_timeout()

            # Create backup before any modifications
            backup_path = self._create_backup()
            self._check_operation_timeout()

            # Read original content
            original_content = self._read_file_content()
            lines = original_content.split("\n")
            self._check_operation_timeout()

            # Validate line number
            if line_number < 0 or line_number > len(lines):
                return OperationResult(
                    False,
                    f"Invalid line number: {line_number} (file has {len(lines)} lines)",
                )

            # Prepare content with proper indentation
            if preserve_indentation and line_number > 0:
                indent_info = self.detect_indentation(line_number - 1)
                content = self._apply_indentation(content, indent_info, lines, line_number - 1)
            self._check_operation_timeout()

            # Insert content
            insert_index = line_number
            content_lines = content.split("\n")

            # Insert new lines
            new_lines = lines[:insert_index] + content_lines + lines[insert_index:]
            new_content = "\n".join(new_lines)
            self._check_operation_timeout()

            # Write atomically
            self._write_content_atomically(new_content)
            self._modified = True

            return OperationResult(
                True,
                f"Inserted {len(content_lines)} lines after line {line_number}",
                backup_path,
            )

        except (OSError, ValueError, TimeoutError) as e:
            return OperationResult(False, f"Error: {str(e)}")

    def replace_symbol_body(
        self,
        body_start_line: int,
        body_end_line: int,
        new_body_content: str,
        preserve_indentation: bool = True,
        body_start_char: int = None,
        body_end_char: int = None,
    ) -> OperationResult:
        """Replace the body content of a symbol while preserving the declaration.

        Args:
            body_start_line: Start line of body content to replace (1-based, inclusive)
            body_end_line: End line of body content to replace (1-based, inclusive)
            new_body_content: New body content to insert
            preserve_indentation: Whether to match surrounding indentation
            body_start_char: For single-line bodies, character position of opening brace (0-based)
            body_end_char: For single-line bodies, character position of closing brace (0-based)

        Returns:
            OperationResult with operation status
        """
        try:
            self._start_operation_timer()
            self._validate_content(new_body_content)
            self._check_operation_timeout()

            # Create backup before any modifications
            backup_path = self._create_backup()
            self._check_operation_timeout()

            # Read original content
            original_content = self._read_file_content()
            lines = original_content.split("\n")
            self._check_operation_timeout()

            # Validate line numbers
            if body_start_line < 1 or body_end_line < 1:
                return OperationResult(
                    False,
                    f"Invalid line numbers: start={body_start_line}, end={body_end_line} (must be >= 1)",
                )

            if body_start_line > len(lines) + 1 or body_end_line > len(lines) + 1:
                return OperationResult(
                    False,
                    f"Line numbers out of range: start={body_start_line}, end={body_end_line} (file has {len(lines)} lines)",
                )

            if body_start_line > body_end_line:
                return OperationResult(
                    False,
                    f"Invalid range: start line ({body_start_line}) cannot be greater than end line ({body_end_line})",
                )

            # Handle single-line body replacement (e.g., single-line computed properties)
            # This is only for cases where the entire symbol (declaration + body) is on one line
            single_line_handled = False
            if (
                body_start_line == body_end_line
                and body_start_char is not None
                and body_end_char is not None
            ):
                # Replace content between braces on the same line
                line_idx = body_start_line - 1  # Convert to 0-based
                if line_idx < len(lines):
                    original_line = lines[line_idx]
                    
                    # Validate that the character positions are within the line bounds
                    # and that we actually have braces at those positions
                    if (body_start_char < len(original_line) and 
                        body_end_char < len(original_line) and
                        body_start_char < body_end_char):
                        # Extract the content before and after the body
                        before_body = original_line[: body_start_char + 1]  # Include the opening brace
                        after_body = original_line[body_end_char:]  # From closing brace onwards

                        # Construct new line with replaced body
                        new_line = before_body + " " + new_body_content + " " + after_body

                        # Replace the line
                        lines[line_idx] = new_line
                        new_content = "\n".join(lines)

                        self._check_operation_timeout()

                        # Write atomically
                        self._write_content_atomically(new_content)
                        self._modified = True

                        return OperationResult(
                            True,
                            f"Replaced single-line body on line {body_start_line}",
                            backup_path,
                        )
            
            # If single-line replacement wasn't handled, fall through to multi-line logic

            # Multi-line body replacement (original logic)
            # Prepare new body content with proper indentation
            if preserve_indentation and body_start_line <= len(lines):
                # Use the line before body start as reference for indentation
                reference_line_idx = max(
                    0, body_start_line - 2
                )  # Convert to 0-based and go one line up
                indent_info = self.detect_indentation(reference_line_idx)
                new_body_content = self._apply_indentation(
                    new_body_content, indent_info, lines, reference_line_idx
                )
            self._check_operation_timeout()

            # Replace the body content (convert to 0-based indices)
            start_idx = body_start_line - 1
            end_idx = body_end_line  # end_line is inclusive, so we don't subtract 1

            # Split new content into lines
            new_body_lines = new_body_content.split("\n")

            # Replace the range with new content
            new_lines = lines[:start_idx] + new_body_lines + lines[end_idx:]
            new_content = "\n".join(new_lines)
            self._check_operation_timeout()

            # Write atomically
            self._write_content_atomically(new_content)
            self._modified = True

            # Calculate metrics for response
            old_line_count = end_idx - start_idx
            new_line_count = len(new_body_lines)

            return OperationResult(
                True,
                f"Replaced {old_line_count} lines with {new_line_count} lines (lines {body_start_line}-{body_end_line})",
                backup_path,
            )

        except (OSError, ValueError, TimeoutError) as e:
            return OperationResult(False, f"Error: {str(e)}")

    def _apply_indentation(
        self,
        content: str,
        indent_info: IndentationInfo,
        lines: list,
        reference_line: int,
    ) -> str:
        """Apply proper indentation to content based on surrounding context.

        Args:
            content: Content to indent
            indent_info: Detected indentation information
            lines: All lines in the file
            reference_line: Line to use as indentation reference (0-based)

        Returns:
            Content with proper indentation applied
        """
        if reference_line < 0 or reference_line >= len(lines):
            return content

        reference = lines[reference_line]

        # Calculate base indentation from reference line
        if indent_info.type == "tabs":
            base_indent = "\t" * (len(reference) - len(reference.lstrip("\t")))
        else:
            leading_spaces = len(reference) - len(reference.lstrip(" "))
            base_indent = " " * leading_spaces

        # Apply indentation to each line of content
        content_lines = content.split("\n")
        indented_lines = []

        for line in content_lines:
            if line.strip():  # Only indent non-empty lines
                indented_lines.append(base_indent + line.lstrip())
            else:
                indented_lines.append(line)  # Keep empty lines as-is

        return "\n".join(indented_lines)

    def _write_content_atomically(self, content: str) -> None:
        """Write content to file atomically to prevent corruption.

        Args:
            content: Content to write

        Raises:
            IOError: If atomic write fails
        """
        try:
            # Write to temporary file first
            temp_dir = os.path.dirname(self._file_path)
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp", prefix="swift_modify_", dir=temp_dir
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
                    temp_file.write(content)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())

                # Atomic move to final location
                if os.name == "nt":  # Windows
                    # On Windows, need to remove target first
                    if os.path.exists(self._file_path):
                        os.remove(self._file_path)

                shutil.move(temp_path, self._file_path)

            except Exception:
                # Clean up temp file on error
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                raise

        except OSError as e:
            raise OSError(f"Failed to write file atomically: {str(e)}") from e

    def rollback(self) -> bool:
        """Restore file from backup if available.

        Returns:
            True if rollback successful, False otherwise
        """
        if not self._backup_path or not os.path.exists(self._backup_path):
            return False

        try:
            shutil.copy2(self._backup_path, self._file_path)
            self._modified = False
            return True
        except (OSError, shutil.Error):
            return False

    def cleanup(self) -> None:
        """Clean up temporary files and backups."""
        if self._backup_path and os.path.exists(self._backup_path):
            try:
                # Remove backup file
                os.remove(self._backup_path)
                # Remove backup directory if empty
                backup_dir = os.path.dirname(self._backup_path)
                try:
                    os.rmdir(backup_dir)
                except OSError:
                    pass  # Directory not empty or other issue
            except OSError:
                pass  # Best effort cleanup

        self._backup_path = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        if exc_type is not None and self._modified:
            # Exception occurred, attempt rollback
            self.rollback()

        self.cleanup()

        # Don't suppress exceptions
        return False
