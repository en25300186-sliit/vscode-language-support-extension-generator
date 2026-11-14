from __future__ import annotations

import json

from vscode_language_support_extension_generator.core import (
    FeatureMeta,
    LanguageSpec,
    Snippet,
    Symbol,
    VscodeExtensionBuilder,
    generate_extension,
)


def test_generator_creates_full_support_scaffold(tmp_path):
    spec = LanguageSpec(
        language_id="mylang",
        display_name="MyLang",
        publisher="acme",
        extension_name="mylang-support",
        file_extensions=(".mlg", ".myl"),
        aliases=("MLang",),
    )

    target = VscodeExtensionBuilder(spec).generate(tmp_path / "out")

    expected_files = [
        "package.json",
        "language-configuration.json",
        "snippets/mylang.json",
        "syntaxes/mylang.tmLanguage.json",
        "client/extension.ts",
        "server/server.py",
        ".vscode/launch.json",
        ".vscode/tasks.json",
    ]
    for relative in expected_files:
        assert (target / relative).exists(), relative

    package_json = json.loads((target / "package.json").read_text(encoding="utf-8"))
    contributes = package_json["contributes"]
    assert contributes["languages"][0]["id"] == "mylang"
    assert contributes["languages"][0]["extensions"] == [".mlg", ".myl"]
    assert package_json["contributesConfiguration"]["lsp"]["hover"] is True
    assert (target / "language.py").exists()


def test_declarative_editing_uses_language_spec(tmp_path):
    spec = LanguageSpec(
        language_id="toy",
        display_name="Toy",
        publisher="acme",
        extension_name="toy-support",
        single_line_comment="//",
        block_comment_start="/*",
        block_comment_end="*/",
        keywords=("let", "match"),
        literals=("yes", "no"),
        operators=("=>", "=="),
        snippets=(Snippet("Match", "match", ("match ${1:value} {", "\t$0", "}")),),
    )

    target = VscodeExtensionBuilder(spec).generate(tmp_path / "toy")
    grammar = json.loads((target / "syntaxes/toy.tmLanguage.json").read_text(encoding="utf-8"))
    configuration = json.loads((target / "language-configuration.json").read_text(encoding="utf-8"))
    snippets = json.loads((target / "snippets/toy.json").read_text(encoding="utf-8"))

    assert "let" in grammar["repository"]["keywords"]["patterns"][0]["match"]
    assert "yes" in grammar["repository"]["literals"]["patterns"][0]["match"]
    assert "=>" in grammar["repository"]["operators"]["patterns"][0]["match"]
    assert grammar["repository"]["comments"]["patterns"][1]["name"] == "comment.block"
    assert configuration["comments"]["lineComment"] == "//"
    assert snippets["Match"]["prefix"] == "match"


def test_generate_extension_function_api(tmp_path):
    target = generate_extension(
        language_id="dsl",
        display_name="DSL",
        publisher="acme",
        extension_name="dsl-support",
        output_dir=tmp_path / "dsl-out",
    )

    package_json = json.loads((target / "package.json").read_text(encoding="utf-8"))
    assert package_json["name"] == "dsl-support"


def test_feature_metaclass_registry_contains_builtin_features():
    registry = FeatureMeta.registered()
    assert "declarative_editing" in registry
    assert "lsp_intelligence" in registry
    assert "navigation" in registry


def test_generated_python_lsp_exposes_intelligence_handlers(tmp_path):
    spec = LanguageSpec(
        language_id="smart",
        display_name="Smart",
        publisher="acme",
        extension_name="smart-support",
        symbols=(Symbol("print", kind="function", signature="print(value)", documentation="Write a value."),),
    )

    target = VscodeExtensionBuilder(spec).generate(tmp_path / "smart")
    server = (target / "server/server.py").read_text(encoding="utf-8")
    language = (target / "language.py").read_text(encoding="utf-8")

    for handler in ("textDocument/completion", "textDocument/signatureHelp", "textDocument/hover", "textDocument/semanticTokens/full"):
        assert handler in server
    assert "textDocument/publishDiagnostics" in server
    assert "Symbol(name='print'" in language
