from __future__ import annotations

import json
import re
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
    keywords: tuple[str, ...] = (
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "function",
        "import",
        "export",
    )
    literals: tuple[str, ...] = ("true", "false", "null")
    operators: tuple[str, ...] = ("+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">=")
    brackets: tuple[tuple[str, str], ...] = (("{", "}"), ("[", "]"), ("(", ")"))
    auto_closing_pairs: tuple[tuple[str, str], ...] = ()
    surrounding_pairs: tuple[tuple[str, str], ...] = ()
    increase_indent_pattern: str = r"^.*(\{[^}]*|\([^)]*|\[[^\]]*)$"
    decrease_indent_pattern: str = r"^\s*[}\])]$"
    folding_start_marker: str = r"^\s*#region\b"
    folding_end_marker: str = r"^\s*#endregion\b"
    snippets: tuple["Snippet", ...] = ()
    symbols: tuple["Symbol", ...] = ()
    embedded_languages: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Snippet:
    """A friendly, declarative VS Code snippet definition."""

    name: str
    prefix: str
    body: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True)
class Symbol:
    """A declared symbol exposed by the generated Python language server."""

    name: str
    kind: str = "variable"
    type: str = ""
    signature: str = ""
    documentation: str = ""
    deprecated: bool = False


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
        self._write_text(target / "language.py", self._language_script())
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
                "language.py",
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
        auto_closing = self.spec.auto_closing_pairs or self.spec.brackets + (("\"", "\""), ("'", "'"))
        surrounding = self.spec.surrounding_pairs or auto_closing
        return {
            "comments": {
                "lineComment": self.spec.single_line_comment,
                "blockComment": [self.spec.block_comment_start, self.spec.block_comment_end],
            },
            "brackets": [list(pair) for pair in self.spec.brackets],
            "autoClosingPairs": [list(pair) for pair in auto_closing],
            "surroundingPairs": [list(pair) for pair in surrounding],
            "folding": {
                "offSide": False,
                "markers": {
                    "start": self.spec.folding_start_marker,
                    "end": self.spec.folding_end_marker,
                },
            },
            "indentationRules": {
                "increaseIndentPattern": self.spec.increase_indent_pattern,
                "decreaseIndentPattern": self.spec.decrease_indent_pattern,
            },
        }

    def _grammar_template(self) -> dict[str, Any]:
        scope_name = f"source.{self.spec.language_id}"
        return {
            "name": self.spec.display_name,
            "scopeName": scope_name,
            "embeddedLanguages": dict(self.spec.embedded_languages),
            "patterns": [
                {"include": "#comments"},
                {"include": "#strings"},
                {"include": "#keywords"},
                {"include": "#literals"},
                {"include": "#numbers"},
                {"include": "#operators"},
            ],
            "repository": {
                "keywords": {
                    "patterns": [
                        {
                            "name": "keyword.control",
                            "match": self._word_pattern(self.spec.keywords),
                        }
                    ]
                },
                "literals": {
                    "patterns": [
                        {
                            "name": "constant.language",
                            "match": self._word_pattern(self.spec.literals),
                        }
                    ]
                },
                "numbers": {
                    "patterns": [
                        {"name": "constant.numeric", "match": r"\b(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?)\b"}
                    ]
                },
                "operators": {
                    "patterns": [
                        {
                            "name": "keyword.operator",
                            "match": self._operator_pattern(self.spec.operators),
                        }
                    ]
                },
                "strings": {
                    "patterns": [
                        {
                            "name": "string.quoted.double",
                            "begin": '"',
                            "end": '"',
                            "patterns": [{"include": "#escape"}],
                        },
                        {
                            "name": "string.quoted.single",
                            "begin": "'",
                            "end": "'",
                            "patterns": [{"include": "#escape"}],
                        },
                    ]
                },
                "escape": {
                    "patterns": [{"name": "constant.character.escape", "match": r"\\."}],
                },
                "comments": {
                    "patterns": [
                        {
                            "name": "comment.line",
                            "match": rf"{re.escape(self.spec.single_line_comment)}.*$",
                        },
                        {
                            "name": "comment.block",
                            "begin": re.escape(self.spec.block_comment_start),
                            "end": re.escape(self.spec.block_comment_end),
                        },
                    ]
                },
            },
        }

    def _snippet_template(self) -> dict[str, Any]:
        snippets = self.spec.snippets or (
            Snippet("If block", "if", ("if ${1:condition} {", "\t$0", "}"), "Insert an if statement"),
            Snippet(
                "Function",
                "fn",
                ("function ${1:name}(${2:args}) {", "\t$0", "}"),
                "Insert a function declaration",
            ),
        )
        return {
            snippet.name: {
                "prefix": snippet.prefix,
                "body": list(snippet.body),
                "description": snippet.description or f"Insert a {snippet.name.lower()}",
            }
            for snippet in snippets
        }

    @staticmethod
    def _word_pattern(words: tuple[str, ...]) -> str:
        if not words:
            return r"(?!)"
        return r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\b"

    @staticmethod
    def _operator_pattern(operators: tuple[str, ...]) -> str:
        if not operators:
            return r"(?!)"
        escaped = sorted((re.escape(operator) for operator in operators), key=len, reverse=True)
        return "(?:" + "|".join(escaped) + ")"

    def _language_script(self) -> str:
        return f'''"""Edit this file to describe your language, then run: python language.py."""

from pathlib import Path

from vscode_language_support_extension_generator import LanguageSpec, Snippet, Symbol, VscodeExtensionBuilder


language = LanguageSpec(
    language_id={self.spec.language_id!r},
    display_name={self.spec.display_name!r},
    publisher={self.spec.publisher!r},
    extension_name={self.spec.extension_name!r},
    file_extensions={self.spec.file_extensions!r},
    aliases={self.spec.aliases!r},
    single_line_comment={self.spec.single_line_comment!r},
    block_comment_start={self.spec.block_comment_start!r},
    block_comment_end={self.spec.block_comment_end!r},
    # Add your language's words and operators here.
    keywords={self.spec.keywords!r},
    literals={self.spec.literals!r},
    operators={self.spec.operators!r},
    brackets={self.spec.brackets!r},
    auto_closing_pairs={self.spec.auto_closing_pairs!r},
    surrounding_pairs={self.spec.surrounding_pairs!r},
    increase_indent_pattern={self.spec.increase_indent_pattern!r},
    decrease_indent_pattern={self.spec.decrease_indent_pattern!r},
    folding_start_marker={self.spec.folding_start_marker!r},
    folding_end_marker={self.spec.folding_end_marker!r},
    snippets={self.spec.snippets!r},
    symbols={self.spec.symbols!r},
    embedded_languages={self.spec.embedded_languages!r},
)


if __name__ == "__main__":
    VscodeExtensionBuilder(language).generate(Path(__file__).parent)
'''

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
        content = '''"""Small, dependency-free Python LSP for the generated language.

Edit language.py to add keywords, symbols, signatures, documentation, and types.
Replace the lightweight declaration scanner with a parser when the language grows.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from language import language
except ImportError:
    language = None

documents: dict[str, str] = {}
workspace_root: Path | None = None
word_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
declaration_pattern = re.compile(
    r"\\b(?:let|var|const|def|function|class|type|interface|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)"
)
import_pattern = re.compile(r"\\b(?:import|from)\\s+([A-Za-z_][A-Za-z0-9_]*)")
token_types = ["keyword", "variable", "function", "type", "number", "string", "comment"]


def send(message: dict[str, Any]) -> None:
    payload = json.dumps(message, separators=(",", ":"))
    sys.stdout.write(f"Content-Length: {len(payload.encode('utf-8'))}\\r\\n\\r\\n{payload}")
    sys.stdout.flush()


def reply(request_id: Any, result: Any) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def configured_symbols() -> dict[str, Any]:
    return {item.name: item for item in getattr(language, "symbols", ())}


def document_symbols(text: str) -> dict[str, dict[str, Any]]:
    symbols = {
        name: {
            "name": name,
            "kind": getattr(item, "kind", "variable"),
            "type": getattr(item, "type", ""),
            "signature": getattr(item, "signature", ""),
            "documentation": getattr(item, "documentation", ""),
            "deprecated": getattr(item, "deprecated", False),
        }
        for name, item in configured_symbols().items()
    }
    for match in declaration_pattern.finditer(text):
        name = match.group(1)
        prefix = text[max(0, match.start() - 20):match.start()]
        kind = "function" if re.search(r"\\b(?:def|function)\\s*$", prefix) else "variable"
        symbols.setdefault(name, {"name": name, "kind": kind, "type": "", "signature": "", "documentation": "", "deprecated": False})
    for match in import_pattern.finditer(text):
        name = match.group(1)
        symbols.setdefault(name, {"name": name, "kind": "variable", "type": "imported", "signature": "", "documentation": "Imported symbol", "deprecated": False})
    return symbols


def position_offset(text: str, position: dict[str, int]) -> int:
    lines = text.splitlines(keepends=True)
    return sum(len(line) for line in lines[:position.get("line", 0)]) + position.get("character", 0)


def word_at(text: str, position: dict[str, int]) -> str:
    offset = position_offset(text, position)
    for match in word_pattern.finditer(text):
        if match.start() <= offset <= match.end():
            return match.group()
    return ""


def diagnostics(uri: str, text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    stack: list[tuple[str, int]] = []
    pairs = {"{": "}", "[": "]", "(": ")"}
    closing = {value: key for key, value in pairs.items()}
    for index, character in enumerate(text):
        if character in pairs:
            stack.append((character, index))
        elif character in closing:
            if not stack or stack[-1][0] != closing[character]:
                result.append({"range": {"start": {"line": 0, "character": index}, "end": {"line": 0, "character": index + 1}}, "severity": 1, "message": f"Unexpected '{character}'", "source": "language.py"})
            else:
                stack.pop()
    for opening, index in stack:
        result.append({"range": {"start": {"line": 0, "character": index}, "end": {"line": 0, "character": index + 1}}, "severity": 1, "message": f"Unclosed '{opening}'", "source": "language.py"})
    for match in re.finditer(r"\\b(TODO|FIXME)\\b", text):
        result.append({"range": {"start": {"line": 0, "character": match.start()}, "end": {"line": 0, "character": match.end()}}, "severity": 2, "message": f"{match.group()} needs attention", "source": "language.py"})
    return result


def semantic_tokens(text: str) -> list[int]:
    keywords = set(getattr(language, "keywords", ()))
    literals = set(getattr(language, "literals", ()))
    symbols = document_symbols(text)
    raw: list[tuple[int, int, int, int]] = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines):
        for match in word_pattern.finditer(line):
            name = match.group()
            if name in keywords:
                token_type = 0
            elif name in symbols:
                token_type = {"function": 2, "type": 3}.get(symbols[name]["kind"], 1)
            elif name in literals:
                token_type = 1
            else:
                continue
            raw.append((line_number, match.start(), len(name), token_type))
    encoded: list[int] = []
    previous_line = 0
    previous_start = 0
    for line, start, length, token_type in raw:
        encoded.extend([line - previous_line, start - previous_start if line == previous_line else start, length, token_type, 0])
        previous_line, previous_start = line, start
    return encoded


def publish_diagnostics(uri: str, text: str) -> None:
    send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": diagnostics(uri, text)}})


def lsp_symbol_kind(kind: str) -> int:
    return {"file": 1, "module": 2, "namespace": 3, "class": 5, "method": 6, "function": 12, "variable": 13, "constant": 14, "string": 15, "number": 16, "type": 22}.get(kind, 13)


def line_position(text: str, offset: int) -> dict[str, int]:
    before = text[:offset]
    return {"line": before.count("\\n"), "character": offset - before.rfind("\\n") - 1}


def symbol_location(uri: str, text: str, name: str) -> dict[str, Any] | None:
    match = re.search(r"\\b" + re.escape(name) + r"\\b", text)
    if not match:
        return None
    return {"uri": uri, "range": {"start": line_position(text, match.start()), "end": line_position(text, match.end())}}


def files_in_workspace() -> dict[str, str]:
    result = dict(documents)
    if workspace_root and workspace_root.exists():
        extensions = tuple(getattr(language, "file_extensions", ()))
        for path in workspace_root.rglob("*"):
            if path.is_file() and (not extensions or path.suffix in extensions):
                uri = path.as_uri()
                try:
                    result.setdefault(uri, path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
    return result


def all_symbols() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for uri, text in files_in_workspace().items():
        for name, item in document_symbols(text).items():
            result.setdefault(name, []).append({"uri": uri, "text": text, "item": item})
    return result


def full_document_range(text: str) -> dict[str, dict[str, int]]:
    lines = text.splitlines()
    return {"start": {"line": 0, "character": 0}, "end": {"line": len(lines), "character": len(lines[-1]) if lines else 0}}


def format_document(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\\n".join(lines) + ("\\n" if lines else "")


def code_actions(uri: str, text: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for match in re.finditer(r"\\b(TODO|FIXME)\\b[^\\n]*", text):
        actions.append({
            "title": f"Remove {match.group(1)} marker",
            "kind": "quickfix",
            "edit": {"changes": {uri: [{"range": {"start": line_position(text, match.start()), "end": line_position(text, match.end())}, "newText": ""}]}},
        })
    return actions


def call_hierarchy_item(uri: str, text: str, name: str) -> dict[str, Any] | None:
    location = symbol_location(uri, text, name)
    if not location:
        return None
    item = document_symbols(text).get(name, {})
    return {"name": name, "kind": lsp_symbol_kind(item.get("kind", "function")), "uri": uri, "range": location["range"], "selectionRange": location["range"], "detail": item.get("signature") or item.get("type", "")}


def handle(message: dict[str, Any]) -> bool:
    global workspace_root
    method = message.get("method")
    params = message.get("params", {})
    request_id = message.get("id")
    if method == "initialize":
        root_uri = params.get("rootUri")
        if root_uri and root_uri.startswith("file://"):
            workspace_root = Path(root_uri[7:])
        reply(request_id, {"capabilities": {
            "textDocumentSync": 1,
            "completionProvider": {"triggerCharacters": [".", ":"]},
            "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
            "hoverProvider": True,
            "definitionProvider": True,
            "referencesProvider": True,
            "documentSymbolProvider": True,
            "workspaceSymbolProvider": True,
            "documentFormattingProvider": True,
            "renameProvider": True,
            "codeActionProvider": {"codeActionKinds": ["quickfix", "source"]},
            "callHierarchyProvider": True,
            "diagnosticProvider": {"interFileDependencies": True, "workspaceDiagnostics": False},
            "semanticTokensProvider": {"legend": {"tokenTypes": token_types, "tokenModifiers": ["deprecated"]}, "full": True},
        }})
    elif method == "textDocument/didOpen":
        document = params["textDocument"]
        documents[document["uri"]] = document["text"]
        publish_diagnostics(document["uri"], document["text"])
    elif method == "textDocument/didChange":
        document = params["textDocument"]
        documents[document["uri"]] = params["contentChanges"][-1]["text"]
        publish_diagnostics(document["uri"], documents[document["uri"]])
    elif method == "textDocument/completion":
        uri = params["textDocument"]["uri"]
        symbols = document_symbols(documents.get(uri, ""))
        items = [{"label": word, "kind": 14} for word in getattr(language, "keywords", ())]
        items += [{"label": name, "kind": 3 if item["kind"] == "function" else 6, "detail": item["type"] or item["signature"], "deprecated": item["deprecated"]} for name, item in symbols.items()]
        reply(request_id, {"isIncomplete": False, "items": items})
    elif method == "textDocument/signatureHelp":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        offset = position_offset(text, params["position"])
        before = text[:offset]
        call = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\\s*\\([^()]*$", before)
        signature = configured_symbols().get(call.group(1)) if call else None
        if signature:
            label = getattr(signature, "signature", "") or f"{call.group(1)}(...)"
            reply(request_id, {"signatures": [{"label": label, "documentation": getattr(signature, "documentation", "")}], "activeSignature": 0, "activeParameter": 0})
        else:
            reply(request_id, None)
    elif method == "textDocument/hover":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        name = word_at(text, params["position"])
        item = document_symbols(text).get(name)
        if item:
            detail = item["signature"] or item["type"] or item["kind"]
            value = f"**{name}**\\n\\n`{detail}`" if detail else f"**{name}**"
            if item["documentation"]:
                value += f"\\n\\n{item['documentation']}"
            reply(request_id, {"contents": {"kind": "markdown", "value": value}})
        else:
            reply(request_id, None)
    elif method == "textDocument/semanticTokens/full":
        uri = params["textDocument"]["uri"]
        reply(request_id, {"data": semantic_tokens(documents.get(uri, ""))})
    elif method == "textDocument/definition":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        name = word_at(text, params["position"])
        candidates = all_symbols().get(name, [])
        location = symbol_location(candidates[0]["uri"], candidates[0]["text"], name) if candidates else None
        reply(request_id, [location] if location else [])
    elif method == "textDocument/references":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        name = word_at(text, params["position"])
        references = []
        for candidate_uri, candidate_text in files_in_workspace().items():
            for match in re.finditer(r"\\b" + re.escape(name) + r"\\b", candidate_text):
                references.append({"uri": candidate_uri, "range": {"start": line_position(candidate_text, match.start()), "end": line_position(candidate_text, match.end())}})
        reply(request_id, references)
    elif method == "textDocument/documentSymbol":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        result = []
        for name, item in document_symbols(text).items():
            location = symbol_location(uri, text, name)
            if location:
                result.append({"name": name, "kind": lsp_symbol_kind(item["kind"]), "detail": item["signature"] or item["type"], "range": location["range"], "selectionRange": location["range"]})
        reply(request_id, result)
    elif method == "workspace/symbol":
        query = params.get("query", "").lower()
        result = []
        for name, candidates in all_symbols().items():
            if query in name.lower():
                candidate = candidates[0]
                location = symbol_location(candidate["uri"], candidate["text"], name)
                if location:
                    result.append({"name": name, "kind": lsp_symbol_kind(candidate["item"]["kind"]), "location": location})
        reply(request_id, result)
    elif method == "textDocument/formatting":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        reply(request_id, [{"range": full_document_range(text), "newText": format_document(text)}])
    elif method == "textDocument/rename":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        old_name = word_at(text, params["position"])
        new_name = params["newName"]
        changes = {}
        for candidate_uri, candidate_text in files_in_workspace().items():
            edits = [{"range": {"start": line_position(candidate_text, match.start()), "end": line_position(candidate_text, match.end())}, "newText": new_name} for match in re.finditer(r"\\b" + re.escape(old_name) + r"\\b", candidate_text)]
            if edits:
                changes[candidate_uri] = edits
        reply(request_id, {"changes": changes})
    elif method == "textDocument/codeAction":
        uri = params["textDocument"]["uri"]
        reply(request_id, code_actions(uri, documents.get(uri, "")))
    elif method == "textDocument/prepareCallHierarchy":
        uri = params["textDocument"]["uri"]
        text = documents.get(uri, "")
        name = word_at(text, params["position"])
        item = call_hierarchy_item(uri, text, name)
        reply(request_id, [item] if item else [])
    elif method in ("callHierarchy/incomingCalls", "callHierarchy/outgoingCalls"):
        item = params.get("item", {})
        uri = item.get("uri", "")
        name = item.get("name", "")
        text = documents.get(uri, "")
        calls = []
        for match in re.finditer(r"\\b" + re.escape(name) + r"\\s*\\(", text):
            range_ = {"start": line_position(text, match.start()), "end": line_position(text, match.end())}
            if method.endswith("incomingCalls"):
                calls.append({"from": {"name": name, "kind": 12, "uri": uri, "range": range_, "selectionRange": range_}, "fromRanges": [range_]})
            else:
                calls.append({"to": {"name": name, "kind": 12, "uri": uri, "range": range_, "selectionRange": range_}, "fromRanges": [range_]})
        reply(request_id, calls)
    elif method == "shutdown":
        reply(request_id, None)
        return False
    elif request_id is not None:
        reply(request_id, None)
    return True


def main() -> None:
    while True:
        header = sys.stdin.buffer.readline()
        if not header:
            return
        if not header.lower().startswith(b"content-length:"):
            continue
        content_length = int(header.split(b":", 1)[1].strip())
        while sys.stdin.buffer.readline().strip():
            pass
        message = json.loads(sys.stdin.buffer.read(content_length))
        if not handle(message):
            return


if __name__ == "__main__":
    main()
'''
        self._write_text(path, content)

    def _write_readme(self, target: Path) -> None:
        readme = f"""# {self.spec.display_name} VS Code Extension\n\nGenerated scaffold for `{self.spec.language_id}` with:\n\n        - Declarative editing support (grammar, pairs, indentation, snippets)\n- Language Server integration scaffold (completion-ready architecture)\n- Code navigation hooks (definition/references/workspace symbols)\n- Formatting, rename and code action hooks\n- Debug/task integration and embedded language support entry points\n\n## Next Steps\n\n1. Implement compile/build in `package.json` scripts.\n2. Expand TextMate grammar and snippets for your language.\n3. Replace `server/server.py` handlers with parser and type-system logic.\n"""
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
    keywords: tuple[str, ...] = LanguageSpec.keywords,
    literals: tuple[str, ...] = LanguageSpec.literals,
    operators: tuple[str, ...] = LanguageSpec.operators,
    snippets: tuple[Snippet, ...] = (),
) -> Path:
    spec = LanguageSpec(
        language_id=language_id,
        display_name=display_name,
        publisher=publisher,
        extension_name=extension_name,
        file_extensions=file_extensions,
        aliases=aliases,
        keywords=keywords,
        literals=literals,
        operators=operators,
        snippets=snippets,
    )
    return VscodeExtensionBuilder(spec).generate(output_dir)
