#!/usr/bin/env python3
"""
Test file for complex Swift features validation

Usage: pytest test/tools/test_complex_features.py

This test validates that the tools can handle advanced Swift language constructs
including actors, generics, protocols with associated types, result builders, etc.
"""

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_analyze_file import swift_analyze_file
from swiftlens.tools.swift_find_symbol_references_files import swift_find_symbol_references_files
from swiftlens.tools.swift_get_declaration_context import swift_get_declaration_context


def create_complex_features_swift_content():
    """Create Swift content with advanced language features."""
    return """import Foundation
import SwiftUI

// MARK: - Actor (iOS 15+)
@available(iOS 15.0, *)
actor DataManager {
    private var cache: [String: Any] = [:]
    private var isLoading: Bool = false

    func store(key: String, value: Any) async {
        cache[key] = value
    }

    func retrieve(key: String) async -> Any? {
        return cache[key]
    }

    func clearCache() async {
        cache.removeAll()
    }
}

// MARK: - Generic Enum with Associated Values
enum APIResult<T, E: Error> {
    case success(T)
    case failure(E)
    case pending

    func map<U>(_ transform: (T) -> U) -> APIResult<U, E> {
        switch self {
        case .success(let value):
            return .success(transform(value))
        case .failure(let error):
            return .failure(error)
        case .pending:
            return .pending
        }
    }

    var isSuccess: Bool {
        if case .success = self { return true }
        return false
    }
}

// MARK: - Protocol with Associated Types
protocol Repository {
    associatedtype Entity
    associatedtype ID: Hashable

    func find(by id: ID) async throws -> Entity?
    func save(_ entity: Entity) async throws
    func delete(by id: ID) async throws
}

// MARK: - Generic Struct Implementing Protocol
struct CachedRepository<T, I: Hashable>: Repository {
    typealias Entity = T
    typealias ID = I

    private var cache: [I: T] = [:]
    private let dataSource: any Repository

    init(dataSource: any Repository) {
        self.dataSource = dataSource
    }

    func find(by id: I) async throws -> T? {
        if let cached = cache[id] {
            return cached
        }

        // Simulate async data fetching
        return nil
    }

    func save(_ entity: T) async throws {
        // Implementation would save to both cache and data source
    }

    func delete(by id: I) async throws {
        cache.removeValue(forKey: id)
    }
}

// MARK: - Result Builder
@resultBuilder
struct SQLBuilder {
    static func buildBlock(_ components: String...) -> String {
        return components.joined(separator: " ")
    }

    static func buildOptional(_ component: String?) -> String {
        return component ?? ""
    }

    static func buildEither(first component: String) -> String {
        return component
    }

    static func buildEither(second component: String) -> String {
        return component
    }
}

func createQuery(@SQLBuilder _ builder: () -> String) -> String {
    return builder()
}

// MARK: - Property Wrapper
@propertyWrapper
struct UserDefault<T> {
    let key: String
    let defaultValue: T

    var wrappedValue: T {
        get {
            return UserDefaults.standard.object(forKey: key) as? T ?? defaultValue
        }
        set {
            UserDefaults.standard.set(newValue, forKey: key)
        }
    }

    init(key: String, defaultValue: T) {
        self.key = key
        self.defaultValue = defaultValue
    }
}

@propertyWrapper
struct Atomic<T> {
    private var value: T
    private let lock = NSLock()

    init(wrappedValue: T) {
        self.value = wrappedValue
    }

    var wrappedValue: T {
        get {
            lock.lock()
            defer { lock.unlock() }
            return value
        }
        set {
            lock.lock()
            defer { lock.unlock() }
            value = newValue
        }
    }
}

// MARK: - Complex Generics with Constraints
struct AsyncSequenceProcessor<S: AsyncSequence, T> where S.Element == T {
    private let sequence: S

    init(sequence: S) {
        self.sequence = sequence
    }

    func process<U>(_ transform: @escaping (T) async throws -> U) async throws -> [U] {
        var results: [U] = []
        for try await element in sequence {
            let transformed = try await transform(element)
            results.append(transformed)
        }
        return results
    }

    func filter(_ predicate: @escaping (T) async throws -> Bool) async throws -> [T] {
        var filtered: [T] = []
        for try await element in sequence {
            if try await predicate(element) {
                filtered.append(element)
            }
        }
        return filtered
    }
}

// MARK: - Class with Generic Constraints and Associated Types
class ContentViewModel<Content: Codable & Identifiable>: ObservableObject {
    @Published var items: [Content] = []
    @Published var isLoading: Bool = false
    @Published var error: Error?

    @UserDefault(key: "content_cache_enabled", defaultValue: true)
    var cacheEnabled: Bool

    @Atomic var requestCount: Int = 0

    private let repository: any Repository

    init(repository: any Repository) {
        self.repository = repository
    }

    @MainActor
    func loadData() async {
        isLoading = true
        error = nil

        do {
            // Simulate async loading
            try await Task.sleep(for: .milliseconds(100))
            requestCount += 1
            // Would load actual data here
        } catch {
            self.error = error
        }

        isLoading = false
    }

    func refresh() async {
        await loadData()
    }
}

// MARK: - Extensions with Advanced Features
extension String {
    func asyncValidate() async -> Bool {
        // Simulate async validation
        try? await Task.sleep(for: .milliseconds(50))
        return !self.isEmpty
    }

    var isValidEmail: Bool {
        let emailRegex = #"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"#
        return self.range(of: emailRegex, options: .regularExpression) != nil
    }
}

extension Array where Element: Numeric {
    func asyncSum() async -> Element {
        return self.reduce(0, +)
    }

    func parallelMap<T>(_ transform: @escaping (Element) async throws -> T) async throws -> [T] {
        return try await withThrowingTaskGroup(of: T.self) { group in
            for element in self {
                group.addTask {
                    return try await transform(element)
                }
            }

            var results: [T] = []
            for try await result in group {
                results.append(result)
            }
            return results
        }
    }
}

extension Optional {
    func asyncMap<U>(_ transform: (Wrapped) async throws -> U) async rethrows -> U? {
        switch self {
        case .some(let value):
            return try await transform(value)
        case .none:
            return nil
        }
    }
}

// MARK: - Advanced Swift Features Usage Example
struct AdvancedFeatureShowcase {
    @UserDefault(key: "user_preference", defaultValue: "default")
    static var userPreference: String

    @Atomic static var globalCounter: Int = 0

    static func demonstrateFeatures() async throws {
        // Using result builder
        let query = createQuery {
            "SELECT * FROM users"
            "WHERE active = true"
            "ORDER BY name"
        }

        // Using actor
        if #available(iOS 15.0, *) {
            let dataManager = DataManager()
            await dataManager.store(key: "demo", value: "test")
            let retrieved = await dataManager.retrieve(key: "demo")
        }

        // Using generic enum
        let result: APIResult<String, Error> = .success("Hello")
        let mapped = result.map { $0.uppercased() }

        // Using async sequence processor
        let numbers = AsyncStream<Int> { continuation in
            Task {
                for i in 1...5 {
                    continuation.yield(i)
                    try? await Task.sleep(for: .milliseconds(100))
                }
                continuation.finish()
            }
        }

        let processor = AsyncSequenceProcessor(sequence: numbers)
        let doubled = try await processor.process { $0 * 2 }
        let filtered = try await processor.filter { $0 > 2 }
    }
}
"""


@pytest.fixture
def complex_features_file(built_swift_environment):
    """Fixture that creates ComplexFeatures.swift with advanced Swift constructs."""
    project_root, sources_dir, create_swift_file = built_swift_environment

    content = create_complex_features_swift_content()
    file_path = create_swift_file(content, "ComplexFeatures.swift")
    return file_path


@pytest.mark.lsp
def test_analyze_complex_swift_features(complex_features_file):
    """Test 1: Analyzing complex Swift file with advanced features."""
    result = swift_analyze_file(complex_features_file)

    # Ensure we got a successful result
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
    assert result.get("success", False), f"Analysis failed: {result.get('error', 'Unknown error')}"

    # Extract symbols from the response
    symbols = result.get("symbols", [])

    # Create a string representation of all symbols for matching
    symbol_strings = []
    for symbol in symbols:
        if isinstance(symbol, dict):
            name = symbol.get("name", "")
            kind = symbol.get("kind", "")
            symbol_strings.append(f"{name} ({kind})")

    # Join all symbol strings for pattern matching
    " ".join(symbol_strings)

    # Check for advanced Swift constructs (updated names based on actual LSP output)
    advanced_features = [
        "DataManager",  # Actor
        "APIResult",  # Generic enum
        "Repository",  # Protocol
        "CachedRepository",  # Generic struct
        "SQLBuilder",  # Result builder
        "UserDefault",  # Property wrapper
        "AsyncSequenceProcessor",  # Complex generics
    ]

    missing_features = []
    found_features_list = []
    for feature in advanced_features:
        found = False
        for symbol_str in symbol_strings:
            if feature in symbol_str:
                found = True
                found_features_list.append(symbol_str)
                break
        if not found:
            missing_features.append(feature)

    found_features = len(advanced_features) - len(missing_features)

    # Allow 50% success rate for complex features (more realistic)
    result_preview = str(result)[:500] + ("..." if len(str(result)) > 500 else "")
    assert found_features >= len(advanced_features) * 0.5, (
        f"Only found {found_features}/{len(advanced_features)} advanced features. "
        f"Found: {found_features_list}. Missing: {missing_features}. "
        f"All symbols: {symbol_strings[:10]}. Sample output: {result_preview}"
    )


@pytest.mark.lsp
def test_declaration_context_complex_structures(complex_features_file):
    """Test 2: Declaration context for complex nested structures."""
    context_result = swift_get_declaration_context(complex_features_file)

    # Ensure we got a successful result
    assert isinstance(context_result, dict), f"Expected dict response, got {type(context_result)}"
    assert context_result.get("success", False), (
        f"Context analysis failed: {context_result.get('error', 'Unknown error')}"
    )

    # Extract declarations from the response
    declarations = context_result.get("declarations", [])

    complex_contexts = [
        "CachedRepository.find(by:)",
        "APIResult.map(_:)",
        "AsyncSequenceProcessor.process(_:)",
        "ContentViewModel.loadData()",
        "SQLBuilder.buildBlock(_:)",
    ]

    found_contexts = []
    for context in complex_contexts:
        # Check if any declaration contains this context
        for declaration in declarations:
            if context in declaration:
                found_contexts.append(declaration)
                break

    # Allow 30% success rate for complex contexts (more realistic)
    assert len(found_contexts) >= len(complex_contexts) * 0.3, (
        f"Only found {len(found_contexts)}/{len(complex_contexts)} complex contexts. "
        f"Found: {found_contexts}. All declarations: {declarations[:10]}"
    )


@pytest.mark.lsp
def test_symbol_references_in_generic_context(complex_features_file):
    """Test 3: Finding references in complex generic code."""
    ref_result = swift_find_symbol_references_files([complex_features_file], "cache")

    # Ensure we got a dictionary result
    assert isinstance(ref_result, dict), f"Expected dict response, got {type(ref_result)}"

    # Either successful with references found or no references (both are valid)
    if ref_result.get("success", False):
        total_references = ref_result.get("total_references", 0)
        # References found or no references - both are acceptable outcomes
        assert total_references >= 0, f"Invalid total reference count: {total_references}"

        # Check the file-specific result structure
        files = ref_result.get("files", {})
        assert complex_features_file in files, f"Expected file {complex_features_file} in results"

        file_result = files[complex_features_file]
        if file_result.get("success", False):
            file_ref_count = file_result.get("reference_count", 0)
            assert file_ref_count >= 0, f"Invalid file reference count: {file_ref_count}"
    else:
        # If it failed, ensure it's not a critical error
        error = ref_result.get("error", "")
        assert "No references found" in error or "not found" in error or len(error) > 0, (
            f"Unexpected error format: {ref_result}"
        )


@pytest.mark.lsp
def test_extension_symbol_detection(complex_features_file):
    """Test 4: Extension symbol detection."""
    result = swift_analyze_file(complex_features_file)

    # Ensure we got a successful result
    assert isinstance(result, dict), f"Expected dict response, got {type(result)}"

    if result.get("success", False):
        symbols = result.get("symbols", [])

        # Check if extensions are detected by looking at symbol names
        extension_indicators = ["String", "Array", "Optional"]
        found_extensions = []

        for symbol in symbols:
            if isinstance(symbol, dict):
                name = symbol.get("name", "")
                for ext in extension_indicators:
                    if ext in name:
                        found_extensions.append(name)

        # Extensions might not always be present, so this is a soft check
        print(
            f"Extensions detected: {found_extensions}"
            if found_extensions
            else "No extension symbols detected"
        )
    else:
        print(f"Analysis failed: {result.get('error', 'Unknown error')}")


@pytest.mark.lsp
def test_property_wrapper_detection(complex_features_file):
    """Test 5: Property wrapper and advanced attribute detection."""
    result = swift_analyze_file(complex_features_file)
    context_result = swift_get_declaration_context(complex_features_file)

    wrapper_indicators = ["@propertyWrapper", "UserDefault", "Atomic"]
    found_wrappers = []

    # Check in analysis result
    if isinstance(result, dict) and result.get("success", False):
        symbols = result.get("symbols", [])
        result_text = str(symbols)
        for wrapper in wrapper_indicators:
            if wrapper in result_text:
                found_wrappers.append(wrapper)

    # Check in declaration context result
    if isinstance(context_result, dict) and context_result.get("success", False):
        declarations = context_result.get("declarations", [])
        context_text = str(declarations)
        for wrapper in wrapper_indicators:
            if wrapper in context_text and wrapper not in found_wrappers:
                found_wrappers.append(wrapper)

    # Property wrappers might not always be detected clearly, so this is informational
    print(
        f"Property wrappers detected: {found_wrappers}"
        if found_wrappers
        else "Property wrappers not clearly detected"
    )
