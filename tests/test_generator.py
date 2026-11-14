from __future__ import annotations

import json

from vscode_language_support_extension_generator.core import (
    FeatureMeta,
    LanguageSpec,
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
