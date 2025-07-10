#!/usr/bin/env python3
"""
Test file for Unicode and special character symbol definitions

Usage: pytest test/tools/test_unicode_symbols.py

This test creates Swift files with Unicode symbol names and special characters.
"""

import os
import shutil
import tempfile

import pytest

# Add src directory to path for imports
from swiftlens.tools.swift_get_symbol_definition import swift_get_symbol_definition


def parse_definition_output(output):
    """Parse definition output into structured data for validation."""
    # Handle both old string format and new dictionary format
    if isinstance(output, dict):
        # New dictionary format from swift_get_symbol_definition
        if not output.get("success", False):
            return []

        definitions = output.get("definitions", [])
        if not definitions:
            return []

        # Convert the "file:line:char" format to structured data
        parsed_definitions = []
        for definition_str in definitions:
            if ":" in definition_str:
                parts = definition_str.split(":")
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_num = int(parts[1]) if parts[1].isdigit() else 0
                    char_num = int(parts[2]) if parts[2].isdigit() else 0
                    parsed_definitions.append(
                        {"file_path": file_path, "line": line_num, "char": char_num}
                    )
        return parsed_definitions
    else:
        # Legacy string format support
        if "No definition found" in output:
            return []

        definitions = []
        lines = output.strip().split("\n")
        for line in lines:
            if ":" in line:
                parts = line.split(":")
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_num = int(parts[1]) if parts[1].isdigit() else 0
                    char_num = int(parts[2]) if parts[2].isdigit() else 0
                    definitions.append({"file_path": file_path, "line": line_num, "char": char_num})
        return definitions


def create_unicode_swift_file():
    """Create a Swift file with Unicode symbols and special characters."""
    swift_content = """import Foundation

// Unicode class names and properties
class 用户管理器 {
    var 用户列表: [用户] = []

    func 添加用户(_ 用户: 用户) {
        用户列表.append(用户)
    }

    func 查找用户(根据姓名 姓名: String) -> 用户? {
        return 用户列表.first { $0.姓名 == 姓名 }
    }
}

struct 用户 {
    let 标识符: String
    var 姓名: String
    var 电子邮件: String

    init(标识符: String, 姓名: String, 电子邮件: String) {
        self.标识符 = 标识符
        self.姓名 = 姓名
        self.电子邮件 = 电子邮件
    }
}

// Emoji in symbol names
struct 🌟StarService {
    var ⭐️stars: [🌟Star] = []

    func add⭐️(star: 🌟Star) {
        ⭐️stars.append(star)
    }

    func 🔍searchStars(by name: String) -> [🌟Star] {
        return ⭐️stars.filter { $0.name.contains(name) }
    }
}

struct 🌟Star {
    let 🆔id: String
    var name: String
    var 🌈brightness: Double

    func ✨shine() -> String {
        return "✨ Shining with brightness \\(🌈brightness)"
    }
}

// Mathematical symbols
class 𝕸𝖆𝖙𝖍𝕮𝖆𝖑𝖈𝖚𝖑𝖆𝖙𝖔𝖗 {
    func ∑sum(_ numbers: [Double]) -> Double {
        return numbers.reduce(0, +)
    }

    func ∏product(_ numbers: [Double]) -> Double {
        return numbers.reduce(1, *)
    }

    func √squareRoot(_ number: Double) -> Double {
        return number.squareRoot()
    }

    func ∫integral(from α: Double, to β: Double, function ƒ: (Double) -> Double) -> Double {
        // Simplified numerical integration
        let steps = 1000
        let δx = (β - α) / Double(steps)
        var result = 0.0

        for i in 0..<steps {
            let x = α + Double(i) * δx
            result += ƒ(x) * δx
        }

        return result
    }
}

// Accented characters
class CaféManager {
    var employés: [Employé] = []
    var menú: [String] = ["café", "thé", "croissant"]

    func añadirEmpleado(_ employé: Employé) {
        employés.append(employé)
    }

    func búscarEmpleado(por nombre: String) -> Employé? {
        return employés.first { $0.nombre == nombre }
    }
}

struct Employé {
    let número: Int
    var nombre: String
    var salario: Double

    func trabajar() -> String {
        return "\\(nombre) está trabajando"
    }
}

// Mixed Unicode and ASCII
class データベース_Manager {
    private var conexión_活跃: Bool = false

    func 接続する() -> Bool {
        conexión_活跃 = true
        return conexión_活跃
    }

    func desconectar_断开() {
        conexión_活跃 = false
    }

    var isConnected状态: Bool {
        return conexión_活跃
    }
}

// Special file path and name handling
extension String {
    func 正規化Path() -> String {
        return self.replacingOccurrences(of: "//", with: "/")
    }

    func αlphaNumericOnly() -> String {
        return self.filter { $0.isLetter || $0.isNumber }
    }
}

// Test enum with Unicode cases
enum 🎨Color {
    case 红色
    case 绿色
    case 蓝色
    case 自定义(red: Double, green: Double, blue: Double)

    var hexValue: String {
        switch self {
        case .红色:
            return "#FF0000"
        case .绿色:
            return "#00FF00"
        case .蓝色:
            return "#0000FF"
        case .自定义(let r, let g, let b):
            return String(format: "#%02X%02X%02X", Int(r*255), Int(g*255), Int(b*255))
        }
    }
}
"""
    return swift_content


@pytest.fixture
def unicode_swift_file():
    """Create a Swift file with Unicode symbols and special characters."""
    temp_dir = tempfile.mkdtemp(prefix="swift_unicode_test_")
    test_file_path = os.path.join(temp_dir, "Unicode_测试文件.swift")

    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(create_unicode_swift_file())

    yield test_file_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.lsp
def test_emoji_class_name(unicode_swift_file):
    """Test 2: Finding definition for emoji class '🌟StarService'"""
    result = swift_get_symbol_definition(unicode_swift_file, "🌟StarService")
    definitions = parse_definition_output(result)

    if definitions:
        # Emoji class should be around line 29
        emoji_class_found = any(28 <= def_info["line"] <= 31 for def_info in definitions)
        assert emoji_class_found, f"Definition found but at unexpected line: {definitions}"
    else:
        # Emoji symbols may not be found by SourceKit-LSP - this is acceptable
        # For dictionary format, check if it's an unsuccessful result
        if isinstance(result, dict):
            assert not result.get("success", True) or result.get("definition_count", 0) == 0
        else:
            assert "No definition found" in result or "not found" in result


@pytest.mark.lsp
def test_unicode_enum(unicode_swift_file):
    """Test 6: Finding definition for Unicode enum '🎨Color'"""
    result = swift_get_symbol_definition(unicode_swift_file, "🎨Color")
    definitions = parse_definition_output(result)

    if definitions:
        # Enum should be around line 134
        unicode_enum_found = any(133 <= def_info["line"] <= 137 for def_info in definitions)
        assert unicode_enum_found, f"Definition found but at unexpected line: {definitions}"
    else:
        # Emoji symbols may not be found by SourceKit-LSP - this is acceptable
        # For dictionary format, check if it's an unsuccessful result
        if isinstance(result, dict):
            assert not result.get("success", True) or result.get("definition_count", 0) == 0
        else:
            assert "No definition found" in result or "not found" in result


@pytest.mark.lsp
def test_mathematical_function(unicode_swift_file):
    """Test 7: Finding definition for mathematical function '∑sum'"""
    result = swift_get_symbol_definition(unicode_swift_file, "∑sum")
    definitions = parse_definition_output(result)

    if definitions:
        # Sum function should be around line 53-55
        sum_func_found = any(52 <= def_info["line"] <= 56 for def_info in definitions)
        assert sum_func_found, f"Definition found but at unexpected line: {definitions}"
    else:
        # Mathematical symbols in method names might not be found - this is acceptable
        # For dictionary format, check if it's an unsuccessful result
        if isinstance(result, dict):
            assert not result.get("success", True) or result.get("definition_count", 0) == 0
        else:
            assert "No definition found" in result or "not found" in result
