"""Data models for Swift Context analysis."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def validate_swift_file_path(v: str, info) -> str:
    """Reusable validator to ensure a file path has a .swift extension on success."""
    # Only validate Swift extension for successful responses where file_path is not None
    if info.data.get("success", True) and v and not v.endswith(".swift"):
        raise ValueError("Must be a Swift file (.swift extension)")
    return v


@dataclass
class SwiftSymbol:
    """Represents a Swift code symbol with its metadata."""

    name: str
    kind: int
    kind_name: str
    children: list["SwiftSymbol"] = None
    range: dict[str, Any] | None = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class SwiftContextResult(BaseModel):
    """Result model for Swift context analysis."""

    file_path: str = Field(description="Path to the analyzed Swift file")
    symbols: list[dict[str, Any]] = Field(description="Hierarchical list of symbols found")
    symbol_count: int = Field(description="Total number of symbols found")
    success: bool = Field(description="Whether the analysis was successful")
    error_message: str | None = Field(default=None, description="Error message if analysis failed")


class SymbolReferenceResult(BaseModel):
    """Result model for symbol reference analysis."""

    file_path: str = Field(description="Path to the analyzed Swift file")
    symbol_name: str = Field(description="Name of the symbol being searched")
    references: list[dict[str, Any]] = Field(description="List of references found")
    reference_count: int = Field(description="Total number of references found")
    success: bool = Field(description="Whether the analysis was successful")
    error_message: str | None = Field(default=None, description="Error message if analysis failed")


class HoverInfoResult(BaseModel):
    """Result model for hover information analysis."""

    file_path: str = Field(description="Path to the analyzed Swift file")
    line: int = Field(description="Line number (1-based)")
    character: int = Field(description="Character position (1-based)")
    hover_info: str | None = Field(default=None, description="Hover information text")
    success: bool = Field(description="Whether the analysis was successful")
    error_message: str | None = Field(default=None, description="Error message if analysis failed")


# ===== ENUMS FOR STRICT VALIDATION =====


class ErrorType(str, Enum):
    """
    Structured error types for Swift tools with clear categorization.

    Categories:
    - Environment Issues (should skip tests): LSP problems, permissions
    - Tool Logic Issues (should fail tests): Symbol/file not found, invalid params
    - System Issues (context-dependent): Compilation errors, internal failures
    """

    # --- Skippable Environment Errors ---
    LSP_INITIALIZATION_FAILED = "lsp_initialization_failed"
    LSP_SERVER_UNAVAILABLE = "lsp_server_unavailable"
    PERMISSION_DENIED = "permission_denied"
    ENVIRONMENT_ERROR = "environment_error"  # Generic environment issue

    # --- Assertable Tool Failures ---
    SYMBOL_NOT_FOUND = "symbol_not_found"
    SYMBOL_AMBIGUOUS = "symbol_ambiguous"
    FILE_NOT_FOUND = "file_not_found"
    INVALID_PARAMETERS = "invalid_parameters"
    COMPILATION_ERROR = "compilation_error"
    TOOL_INTERNAL_ERROR = "tool_internal_error"
    BUILD_ERROR = "build_error"  # For swift build failures

    # --- Legacy/Compatibility ---
    LSP_ERROR = "lsp_error"  # Deprecated: use specific LSP error types
    VALIDATION_ERROR = "validation_error"  # Maps to INVALID_PARAMETERS
    OPERATION_ERROR = "operation_error"  # Maps to TOOL_INTERNAL_ERROR

    @classmethod
    def is_skippable_environment_error(cls, error_type: "ErrorType") -> bool:
        """Check if error type represents a skippable environment issue."""
        skippable_errors = {
            cls.LSP_INITIALIZATION_FAILED,
            cls.LSP_SERVER_UNAVAILABLE,
            cls.PERMISSION_DENIED,
            cls.ENVIRONMENT_ERROR,
            cls.LSP_ERROR,  # Legacy support
        }
        return error_type in skippable_errors

    @classmethod
    def is_tool_failure(cls, error_type: "ErrorType") -> bool:
        """Check if error type represents a tool logic failure."""
        tool_failures = {
            cls.SYMBOL_NOT_FOUND,
            cls.SYMBOL_AMBIGUOUS,
            cls.FILE_NOT_FOUND,
            cls.INVALID_PARAMETERS,
            cls.COMPILATION_ERROR,
            cls.TOOL_INTERNAL_ERROR,
            cls.VALIDATION_ERROR,  # Legacy support
            cls.OPERATION_ERROR,  # Legacy support
        }
        return error_type in tool_failures


class OperationType(str, Enum):
    """Types of file modification operations."""

    INSERT_BEFORE = "insert_before"
    INSERT_AFTER = "insert_after"
    REPLACE_BODY = "replace_body"
    REGEX_REPLACE = "regex_replace"


class SymbolKind(str, Enum):
    """Swift symbol kinds for type safety."""

    CLASS = "Class"
    STRUCT = "Struct"
    ENUM = "Enum"
    PROTOCOL = "Protocol"
    FUNCTION = "Function"
    METHOD = "Method"
    PROPERTY = "Property"
    VARIABLE = "Variable"
    CONSTANT = "Constant"
    INITIALIZER = "Initializer"
    EXTENSION = "Extension"
    # Additional LSP symbol kinds that might be returned
    FILE = "File"
    MODULE = "Module"
    NAMESPACE = "Namespace"
    PACKAGE = "Package"
    FIELD = "Field"
    CONSTRUCTOR = "Constructor"
    INTERFACE = "Interface"
    UNKNOWN = "Unknown"


# ===== CORE REFERENCE/SYMBOL MODELS =====


class SymbolReference(BaseModel):
    """Individual symbol reference with location and context."""

    file_path: str = Field(description="File containing the reference")
    line: int = Field(description="Line number (1-based)", ge=1)
    character: int = Field(description="Character position (0-based)", ge=0)
    context: str = Field(description="Code context around the reference")


class SwiftSymbolInfo(BaseModel):
    """Information about a Swift symbol."""

    name: str = Field(description="Symbol name", min_length=1)
    kind: SymbolKind = Field(description="Symbol type/kind")
    line: int = Field(description="Line number (1-based)", ge=1)
    character: int = Field(description="Character position (0-based)", ge=0)
    children: list["SwiftSymbolInfo"] = Field(default_factory=list, description="Child symbols")


class SymbolDefinition(BaseModel):
    """Symbol definition location."""

    file_path: str = Field(description="File containing the definition")
    line: int = Field(description="Line number (1-based)", ge=1)
    character: int = Field(description="Character position (0-based)", ge=0)
    context: str = Field(default="", description="Code context around definition")


# ===== TOOL RESPONSE MODELS =====


class SymbolReferenceResponse(BaseModel):
    """Response for swift_find_symbol_references tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    symbol_name: str = Field(description="Symbol being searched", min_length=1)
    references: list[SymbolReference] = Field(description="Found references")
    reference_count: int = Field(description="Number of references", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class FileAnalysisResponse(BaseModel):
    """Response for swift_analyze_file tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    symbols: list[SwiftSymbolInfo] = Field(description="Hierarchical symbol structure")
    symbol_count: int = Field(description="Total number of symbols", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class HoverInfoResponse(BaseModel):
    """Response for swift_get_hover_info tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    line: int = Field(description="Line number (1-based)", ge=1)
    character: int = Field(description="Character position (0-based)", ge=0)
    hover_info: str | None = Field(default=None, description="Hover information text")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class SymbolDefinitionResponse(BaseModel):
    """Response for swift_get_symbol_definition tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    symbol_name: str = Field(description="Symbol being searched", min_length=1)
    definitions: list[SymbolDefinition] = Field(description="Found definitions")
    definition_count: int = Field(description="Number of definitions", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class DeclarationContextResponse(BaseModel):
    """Response for swift_get_declaration_context tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    declarations: list[str] = Field(description="Fully-qualified declaration paths")
    declaration_count: int = Field(description="Number of declarations", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class FileSummaryResponse(BaseModel):
    """Response for swift_summarize_file tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    symbol_counts: dict[str, int] = Field(description="Count of each symbol type")
    total_symbols: int = Field(description="Total number of symbols", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class SymbolsOverviewResponse(BaseModel):
    """Response for swift_get_symbols_overview tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    top_level_symbols: list[SwiftSymbolInfo] = Field(description="Top-level symbols only")
    symbol_count: int = Field(description="Number of top-level symbols", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class EnvironmentCheckResponse(BaseModel):
    """Response for swift_check_environment tool."""

    success: bool = Field(description="Operation success status")
    environment: dict[str, bool | str] = Field(description="Environment status details")
    ready: bool = Field(description="Overall environment readiness")
    recommendations: list[str] = Field(default_factory=list, description="Setup recommendations")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")


class FileImportsResponse(BaseModel):
    """Response for swift_get_file_imports tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Analyzed file path")
    imports: list[str] = Field(description="Import statements")
    import_count: int = Field(description="Number of imports", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class FileValidationResponse(BaseModel):
    """Response for swift_validate_file tool."""

    success: bool = Field(description="Operation success status")
    file_path: str = Field(description="Validated file path")
    validation_result: str = Field(description="Validation output from compiler")
    has_errors: bool = Field(description="Whether file has compilation errors")
    error_count: int = Field(description="Number of compilation errors", ge=0)
    warning_count: int = Field(description="Number of warnings", ge=0)
    error: str | None = Field(default=None, description="Error message if validation failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class MultiFileAnalysisResponse(BaseModel):
    """Response for swift_analyze_multiple_files tool."""

    success: bool = Field(description="Operation success status")
    files: dict[str, FileAnalysisResponse] = Field(description="Analysis results per file")
    total_files: int = Field(description="Number of files analyzed", ge=0)
    total_symbols: int = Field(description="Total symbols across all files", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")


class MultiFileSymbolReferenceResponse(BaseModel):
    """Response for swift_find_symbol_references_files tool."""

    success: bool = Field(description="Operation success status")
    symbol_name: str = Field(description="Symbol being searched")
    files: dict[str, SymbolReferenceResponse] = Field(description="Reference results per file")
    total_files: int = Field(description="Number of files searched", ge=0)
    total_references: int = Field(description="Total references across all files", ge=0)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    @model_validator(mode="after")
    def validate_symbol_name(self):
        """Only require non-empty symbol_name when success is True."""
        if self.success and (not self.symbol_name or not self.symbol_name.strip()):
            raise ValueError("symbol_name cannot be empty when success is True")
        return self


class PatternMatch(BaseModel):
    """Individual pattern match result."""

    line: int = Field(description="Line number (1-based)", ge=1)
    character: int = Field(description="Character position (0-based)", ge=0)
    match_text: str = Field(description="Matched text")
    context: str = Field(default="", description="Surrounding context")


class PatternSearchResponse(BaseModel):
    """Response for swift_search_pattern tool."""

    success: bool = Field(description="Operation success status")
    file_path: str | None = Field(default=None, description="Searched file path")
    pattern: str | None = Field(default=None, description="Search pattern used", min_length=1)
    matches: list[PatternMatch] | None = Field(default=None, description="Pattern matches found")
    match_count: int | None = Field(default=None, description="Number of matches", ge=0)
    is_regex: bool | None = Field(default=None, description="Whether pattern was treated as regex")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class InsertOperationResponse(BaseModel):
    """Response for swift_insert_before_symbol and swift_insert_after_symbol tools."""

    success: bool = Field(description="Operation success status")
    file_path: str | None = Field(default=None, description="Modified file path")
    symbol_name: str | None = Field(default=None, description="Target symbol name")
    operation: OperationType | None = Field(default=None, description="Type of insert operation")
    lines_inserted: int | None = Field(default=None, description="Number of lines inserted", ge=0)
    insertion_line: int | None = Field(
        default=None, description="Line where insertion occurred", ge=1
    )
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class ReplaceOperationResponse(BaseModel):
    """Response for swift_replace_symbol_body tool."""

    success: bool = Field(description="Operation success status")
    file_path: str | None = Field(default=None, description="Modified file path")
    symbol_name: str | None = Field(default=None, description="Target symbol name")
    operation: OperationType | None = Field(default=None, description="Type of replace operation")
    lines_modified: int | None = Field(default=None, description="Number of lines modified", ge=0)
    symbol_line: int | None = Field(default=None, description="Line where symbol starts", ge=1)
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class RegexReplaceResponse(BaseModel):
    """Response for swift_replace_regex tool."""

    success: bool = Field(description="Operation success status")
    file_path: str | None = Field(default=None, description="Modified file path")
    pattern: str | None = Field(default=None, description="Regex pattern used", min_length=1)
    replacement: str | None = Field(default=None, description="Replacement text")
    replacements: int | None = Field(default=None, description="Number of replacements made", ge=0)
    flags: str | None = Field(default=None, description="Regex flags used")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")

    _validate_file_path = field_validator("file_path")(validate_swift_file_path)


class ToolHelpInfo(BaseModel):
    """Information about a specific tool."""

    name: str = Field(description="Tool name", min_length=1)
    purpose: str = Field(description="Tool purpose and functionality")
    parameters: dict[str, str] = Field(description="Parameter names and descriptions")
    use_cases: list[str] = Field(description="Common use cases")
    output_format: dict[str, str] = Field(description="Expected output structure")
    examples: list[str] = Field(description="Usage examples")


class ToolHelpResponse(BaseModel):
    """Response for get_tool_help tool."""

    success: bool = Field(description="Operation success status")
    tool_name: str | None = Field(default=None, description="Specific tool name if requested")
    tools: list[ToolHelpInfo] | ToolHelpInfo = Field(description="Tool help information")
    available_tools: list[str] = Field(description="List of all available tool names")
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")


class BuildIndexResponse(BaseModel):
    """Response for swift_build_index tool."""

    success: bool = Field(description="Operation success status")
    project_path: str = Field(description="Path to the Swift project")
    index_path: str | None = Field(default=None, description="Path to generated index store")
    build_output: str | None = Field(default=None, description="Build command output")
    build_time: float | None = Field(default=None, description="Build duration in seconds")
    project_type: str | None = Field(
        default=None, description="Detected project type (spm or xcode)"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    error_type: ErrorType | None = Field(default=None, description="Error category")
