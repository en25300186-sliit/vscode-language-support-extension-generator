from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


class FeatureMeta(type):
    """Registers feature classes declaratively for discoverability."""

    _registry: dict[str, type["Feature"]] = {}

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, namespace)
        feature_name = namespace.get("feature_name")
        if feature_name:
            mcls._registry[feature_name] = cls
        return cls

    @classmethod
    def registered(mcls) -> dict[str, type["Feature"]]:
        return dict(mcls._registry)


class Feature(metaclass=FeatureMeta):
    feature_name: str = ""

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        raise NotImplementedError


class DeclarativeEditingFeature(Feature):
    feature_name = "declarative_editing"

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        draft.include_snippets = True
        draft.include_language_configuration = True
        draft.include_grammar = True


class LspIntelligenceFeature(Feature):
    feature_name = "lsp_intelligence"

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        draft.include_lsp = True
        draft.semantic_tokens = True
        draft.diagnostics = True
        draft.hover = True


class NavigationFeature(Feature):
    feature_name = "navigation"

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        draft.goto_definition = True
        draft.find_references = True
        draft.workspace_symbols = True


class RefactorAndActionsFeature(Feature):
    feature_name = "format_refactor_actions"

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        draft.document_formatting = True
        draft.code_actions = True
        draft.rename_symbol = True


class ExecutionAndDebugFeature(Feature):
    feature_name = "execution_debug_embedded"

    def apply(self, spec: "LanguageSpec", draft: "FeatureSet") -> None:
        draft.include_debug_configuration = True
        draft.include_tasks_configuration = True


@dataclass(frozen=True)
class LanguageSpec:
    language_id: str
    display_name: str
    publisher: str
    extension_name: str
    file_extensions: tuple[str, ...] = (".txt",)
    single_line_comment: str = "//"
    block_comment_start: str = "/*"
    block_comment_end: str = "*/"
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class FeatureSet:
    include_snippets: bool = False
    include_language_configuration: bool = False
    include_grammar: bool = False
    include_lsp: bool = False
    semantic_tokens: bool = False
    diagnostics: bool = False
    hover: bool = False
    goto_definition: bool = False
    find_references: bool = False
    workspace_symbols: bool = False
    document_formatting: bool = False
    code_actions: bool = False
    rename_symbol: bool = False
    include_debug_configuration: bool = False
    include_tasks_configuration: bool = False


DEFAULT_FEATURES = (
    DeclarativeEditingFeature,
    LspIntelligenceFeature,
    NavigationFeature,
    RefactorAndActionsFeature,
    ExecutionAndDebugFeature,
)


class VscodeExtensionBuilder:
    """Builds a VS Code extension scaffold from Python declarations."""

    def __init__(self, spec: LanguageSpec, features: Iterable[type[Feature] | Feature] | None = None):
        self.spec = spec
        self._features = tuple(features) if features is not None else DEFAULT_FEATURES

    def generate(self, output_dir: str | Path) -> Path:
        target = Path(output_dir).resolve()
        target.mkdir(parents=True, exist_ok=True)

        resolved_features = self._resolve_feature_set()
        self._write_json(target / "package.json", self._build_package_json(resolved_features))
        self._write_readme(target)

        if resolved_features.include_language_configuration:
            self._write_json(target / "language-configuration.json", self._language_configuration())

        if resolved_features.include_grammar:
            self._write_json(
                target / "syntaxes" / f"{self.spec.language_id}.tmLanguage.json",
                self._grammar_template(),
            )

        if resolved_features.include_snippets:
            self._write_json(
                target / "snippets" / f"{self.spec.language_id}.json",
                self._snippet_template(),
            )

        if resolved_features.include_lsp:
            self._write_client_extension_ts(target / "client" / "extension.ts")
            self._write_server_stub(target / "server" / "server.py")

        if resolved_features.include_debug_configuration:
            self._write_json(target / ".vscode" / "launch.json", self._launch_json())

        if resolved_features.include_tasks_configuration:
            self._write_json(target / ".vscode" / "tasks.json", self._tasks_json())

        return target

    def _resolve_feature_set(self) -> FeatureSet:
        draft = FeatureSet()
        for feature in self._features:
            instance = feature() if isinstance(feature, type) else feature
            instance.apply(self.spec, draft)
        return draft

    def _build_package_json(self, feature_set: FeatureSet) -> dict[str, Any]:
        language_id = self.spec.language_id
        extension_globs = [f"*{ext}" for ext in self.spec.file_extensions]

        package: dict[str, Any] = {
            "name": self.spec.extension_name,
            "displayName": self.spec.display_name,
            "publisher": self.spec.publisher,
            "version": "0.1.0",
            "engines": {"vscode": "^1.85.0"},
            "activationEvents": [f"onLanguage:{language_id}"],
            "main": "./client/extension.js",
            "contributes": {
                "languages": [
                    {
                        "id": language_id,
                        "aliases": [self.spec.display_name, *self.spec.aliases],
                        "extensions": list(self.spec.file_extensions),
                        "configuration": "./language-configuration.json",
                    }
                ],
                "grammars": [
                    {
                        "language": language_id,
                        "scopeName": f"source.{language_id}",
                        "path": f"./syntaxes/{language_id}.tmLanguage.json",
                    }
                ],
                "snippets": [
                    {
                        "language": language_id,
                        "path": f"./snippets/{language_id}.json",
                    }
                ],
                "configurationDefaults": {
                    f"[{language_id}]": {
                        "editor.defaultFormatter": f"{self.spec.publisher}.{self.spec.extension_name}",
                        "editor.semanticHighlighting.enabled": True,
                    }
                },
                "commands": [
                    {
                        "command": f"{self.spec.extension_name}.restartLanguageServer",
                        "title": f"Restart {self.spec.display_name} Language Server",
                    }
                ],
                "debuggers": [
                    {
                        "type": language_id,
                        "label": f"{self.spec.display_name} Debug",
                        "languages": [language_id],
                        "configurationAttributes": {
                            "launch": {
                                "required": ["program"],
                                "properties": {
                                    "program": {
                                        "type": "string",
                                        "description": "Program to debug",
                                    }
                                },
                            }
                        },
                        "initialConfigurations": [
                            {
                                "name": f"Run {self.spec.display_name} file",
                                "type": language_id,
                                "request": "launch",
                                "program": "${file}",
                            }
                        ],
                    }
                ],
                "taskDefinitions": [
                    {
                        "type": language_id,
                        "required": ["task"],
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Build, run, or test",
                            }
                        },
                    }
                ],
            },
            "scripts": {
                "compile": "echo \"Compile client extension.ts as needed\"",
                "build": "echo \"Build extension\"",
                "test": "echo \"Run extension tests\"",
            },
            "files": [
                "client",
                "server",
                "syntaxes",
                "snippets",
                "language-configuration.json",
                ".vscode",
            ],
            "categories": ["Programming Languages"],
            "extensionKind": ["workspace"],
            "extensionDependencies": [],
            "enabledApiProposals": [],
            "contributesConfiguration": {
                "fileMatch": extension_globs,
                "lsp": {
                    "semanticTokens": feature_set.semantic_tokens,
                    "diagnostics": feature_set.diagnostics,
                    "hover": feature_set.hover,
                    "goToDefinition": feature_set.goto_definition,
                    "findReferences": feature_set.find_references,
                    "workspaceSymbols": feature_set.workspace_symbols,
                    "documentFormatting": feature_set.document_formatting,
                    "codeActions": feature_set.code_actions,
                    "rename": feature_set.rename_symbol,
                },
            },
        }
        return package

    def _language_configuration(self) -> dict[str, Any]:
        return {
            "comments": {
                "lineComment": self.spec.single_line_comment,
                "blockComment": [self.spec.block_comment_start, self.spec.block_comment_end],
            },
            "brackets": [["{", "}"], ["[", "]"], ["(", ")"]],
            "autoClosingPairs": [
                ["{", "}"],
                ["[", "]"],
                ["(", ")"],
                ["\"", "\""],
                ["'", "'"],
            ],
            "surroundingPairs": [
                ["{", "}"],
                ["[", "]"],
                ["(", ")"],
                ["\"", "\""],
                ["'", "'"],
            ],
            "folding": {
                "offSide": False,
                "markers": {
                    "start": "^\\s*#region\\b",
                    "end": "^\\s*#endregion\\b",
                },
            },
            "indentationRules": {
                "increaseIndentPattern": "^.*(\\{[^}]*|\\([^)]*|\\[[^\\]]*)$",
                "decreaseIndentPattern": "^\\s*[}\\])]",
            },
        }

    def _grammar_template(self) -> dict[str, Any]:
        scope_name = f"source.{self.spec.language_id}"
        return {
            "name": self.spec.display_name,
            "scopeName": scope_name,
            "patterns": [{"include": "#keywords"}, {"include": "#strings"}, {"include": "#comments"}],
            "repository": {
                "keywords": {
                    "patterns": [
                        {
                            "name": "keyword.control",
                            "match": "\\b(if|else|for|while|return|class|function|import|export)\\b",
                        }
                    ]
                },
                "strings": {
                    "patterns": [
                        {"name": "string.quoted.double", "begin": "\"", "end": "\""},
                        {"name": "string.quoted.single", "begin": "'", "end": "'"},
                    ]
                },
                "comments": {
                    "patterns": [
                        {
                            "name": "comment.line",
                            "match": rf"{self.spec.single_line_comment}.*$",
                        }
                    ]
                },
            },
        }

    def _snippet_template(self) -> dict[str, Any]:
        return {
            "If block": {
                "prefix": "if",
                "body": ["if ${1:condition} {", "\t$0", "}"],
                "description": "Insert an if statement",
            },
            "Function": {
                "prefix": "fn",
                "body": ["function ${1:name}(${2:args}) {", "\t$0", "}"],
                "description": "Insert a function declaration",
            },
        }

    def _launch_json(self) -> dict[str, Any]:
        return {
            "version": "0.2.0",
            "configurations": [
                {
                    "name": f"Debug {self.spec.display_name}",
                    "type": self.spec.language_id,
                    "request": "launch",
                    "program": "${file}",
                }
            ],
        }

    def _tasks_json(self) -> dict[str, Any]:
        return {
            "version": "2.0.0",
            "tasks": [
                {
                    "label": f"Run {self.spec.display_name} file",
                    "type": self.spec.language_id,
                    "task": "run",
                    "command": "echo Run current file",
                    "group": "build",
                },
                {
                    "label": f"Test {self.spec.display_name}",
                    "type": self.spec.language_id,
                    "task": "test",
                    "command": "echo Run tests",
                    "group": "test",
                },
            ],
        }

    def _write_client_extension_ts(self, path: Path) -> None:
        content = f'''import * as vscode from "vscode";
import * as path from "path";
import * as cp from "child_process";

let serverProcess: cp.ChildProcess | undefined;

export function activate(context: vscode.ExtensionContext) {{
  const startServer = () => {{
    const serverPath = path.join(context.extensionPath, "server", "server.py");
    serverProcess = cp.spawn("python", [serverPath], {{ stdio: "pipe" }});
  }};

  startServer();

  const restart = vscode.commands.registerCommand("{self.spec.extension_name}.restartLanguageServer", () => {{
    serverProcess?.kill();
    startServer();
  }});

  context.subscriptions.push(restart);
}}

export function deactivate() {{
  serverProcess?.kill();
}}
'''
        self._write_text(path, content)

    def _write_server_stub(self, path: Path) -> None:
        content = '''"""Minimal stdio language server scaffold.

Replace handlers with parser/type-system backed logic.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class ServerCapabilities:
    hoverProvider: bool = True
    definitionProvider: bool = True
    referencesProvider: bool = True
    renameProvider: bool = True
    documentFormattingProvider: bool = True
    codeActionProvider: bool = True
    semanticTokensProvider: dict[str, Any] | None = None


def _send(message: dict[str, Any]) -> None:
    payload = json.dumps(message)
    sys.stdout.write(f"Content-Length: {len(payload)}\\r\\n\\r\\n{payload}")
    sys.stdout.flush()


def _initialize(request_id: int) -> None:
    capabilities = ServerCapabilities(
        semanticTokensProvider={"legend": {"tokenTypes": ["variable", "function", "type"], "tokenModifiers": []}, "full": True}
    )
    _send({"jsonrpc": "2.0", "id": request_id, "result": {"capabilities": capabilities.__dict__}})


def main() -> None:
    while True:
        header = sys.stdin.readline()
        if not header:
            return
        if not header.startswith("Content-Length:"):
            continue
        content_length = int(header.split(":", 1)[1].strip())
        sys.stdin.readline()
        payload = sys.stdin.read(content_length)
        message = json.loads(payload)
        method = message.get("method")
        if method == "initialize":
            _initialize(message.get("id", 0))
        elif method == "shutdown":
            _send({"jsonrpc": "2.0", "id": message.get("id", 0), "result": None})
            return


if __name__ == "__main__":
    main()
'''
        self._write_text(path, content)

    def _write_readme(self, target: Path) -> None:
        readme = f"""# {self.spec.display_name} VS Code Extension\n\nGenerated scaffold for `{self.spec.language_id}` with:\n\n- Declarative editing support (grammar, pairs, indentation, snippets)\n- Language Server integration scaffold (completion-ready architecture)\n- Code navigation hooks (definition/references/workspace symbols)\n- Formatting, rename and code action hooks\n- Debug/task integration and embedded language support entry points\n\n## Next Steps\n\n1. Implement compile/build in `package.json` scripts.\n2. Expand TextMate grammar and snippets for your language.\n3. Replace `server/server.py` handlers with parser and type-system logic.\n"""
        self._write_text(target / "README.md", readme)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def generate_extension(
    *,
    language_id: str,
    display_name: str,
    publisher: str,
    extension_name: str,
    output_dir: str | Path,
    file_extensions: tuple[str, ...] = (".txt",),
    aliases: tuple[str, ...] = (),
) -> Path:
    spec = LanguageSpec(
        language_id=language_id,
        display_name=display_name,
        publisher=publisher,
        extension_name=extension_name,
        file_extensions=file_extensions,
        aliases=aliases,
    )
    return VscodeExtensionBuilder(spec).generate(output_dir)
