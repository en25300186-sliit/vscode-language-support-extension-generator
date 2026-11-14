# VS Code Language Support Extension Generator

Generate a complete VS Code language extension from one readable Python
declaration. The generated extension includes TextMate syntax highlighting,
language configuration, snippets, a dependency-free Python Language Server
Protocol (LSP) server, navigation, refactoring, code actions, debugging/task
scaffolding, and embedded-language grammar mappings.

## Installation

```bash
pip install .
```

The package also exposes the `vscode-extgen` command.

## Quick start

```python
from pathlib import Path

from vscode_language_support_extension_generator import (
    LanguageSpec,
    Snippet,
    Symbol,
    VscodeExtensionBuilder,
)

language = LanguageSpec(
    language_id="mylang",
    display_name="MyLang",
    publisher="acme",
    extension_name="mylang-support",
    file_extensions=(".myl",),
    aliases=("MLang",),
    single_line_comment="//",
    block_comment_start="/*",
    block_comment_end="*/",
    keywords=("if", "else", "fn", "return", "import"),
    literals=("true", "false", "none"),
    operators=("=>", "==", "+", "-", "*"),
    snippets=(
        Snippet("Function", "fn", ("fn ${1:name}() {", "\t$0", "}")),
    ),
    symbols=(
        Symbol(
            "print",
            kind="function",
            signature="print(value: Any)",
            documentation="Write a value to the console.",
        ),
        Symbol("UserId", kind="type", type="str", documentation="A user identifier."),
    ),
    run_command="python ${file}",
    test_command="python -m pytest",
)

VscodeExtensionBuilder(language).generate(Path("generated/mylang"))
```

The generated directory contains an editable `language.py`. After installing
this library, users can edit that file directly and regenerate with:

```bash
cd generated/mylang
python language.py
```

## CLI

```bash
vscode-extgen \
  --language-id mylang \
  --display-name MyLang \
  --publisher acme \
  --extension-name mylang-support \
  --file-extension .myl \
  --alias MLang \
  --output-dir ./generated/mylang
```

The CLI is useful for bootstrapping. The generated `language.py` is the
recommended interface when a language needs richer declarations.

## Declarative editing

`LanguageSpec` configures:

- **Syntax highlighting:** keywords, strings, comments, operators, numbers,
  literals, and escape sequences through a TextMate grammar.
- **Bracket and pair handling:** bracket matching, quote/bracket auto-closing,
  and selection surrounding.
- **Comment toggling:** single-line and block comment delimiters used by VS
  Code's native comment commands.
- **Indentation and folding:** regular expressions for increase/decrease
  indentation and region markers for code folding.
- **Snippets:** named prefixes, tab stops, placeholders, and descriptions.

Relevant fields include `keywords`, `literals`, `operators`, `brackets`,
`auto_closing_pairs`, `surrounding_pairs`, `increase_indent_pattern`,
`decrease_indent_pattern`, `folding_start_marker`, `folding_end_marker`, and
`snippets`.

## Intelligence and LSP features

The generated `server/server.py` is a small, dependency-free Python LSP
implementation. It is intentionally easy to replace with a parser-backed
implementation as the language matures. It currently provides:

- **Completion and IntelliSense:** keyword, declared-symbol, discovered local
  symbol, and imported-symbol suggestions.
- **Signature help:** signatures and documentation from `Symbol` declarations.
- **Semantic highlighting:** keyword, variable, function, type, literal, and
  deprecated-symbol token categories.
- **Diagnostics and linting:** live unmatched-bracket diagnostics and TODO/FIXME
  warnings published through `textDocument/publishDiagnostics`.
- **Hover:** Markdown tooltips containing symbol kind, type, signature, and
  documentation.

Declare richer symbols in `language.py`:

```python
symbols = (
    Symbol(
        "connect",
        kind="function",
        signature="connect(host: str, port: int = 80) -> Client",
        documentation="Open a connection to a service.",
        deprecated=False,
    ),
)
```

## Navigation and structure

The Python LSP implements:

- **Go to definition / Peek Definition:** `textDocument/definition`.
- **Find all references:** `textDocument/references`, across open documents and
  readable workspace files.
- **Symbol outline and breadcrumbs:** `textDocument/documentSymbol`.
- **Workspace symbol search:** `workspace/symbol`.
- **Call hierarchy:** `textDocument/prepareCallHierarchy`,
  `callHierarchy/incomingCalls`, and `callHierarchy/outgoingCalls`.

The lightweight scanner recognizes common declarations such as `let`, `var`,
`const`, `def`, `function`, `class`, `type`, `interface`, and `enum`. For
production languages, replace that scanner with the language parser while
keeping the LSP transport and response shapes.

## Formatting, refactoring, and code actions

The generated server supports:

- **Document formatting:** trims trailing whitespace and normalizes the final
  newline through `textDocument/formatting`.
- **Safe rename:** `textDocument/rename` returns edits for every matching symbol
  occurrence across open/workspace documents.
- **Quick fixes:** `textDocument/codeAction` offers removal of TODO/FIXME
  markers and is designed for adding parser/type-checker fixes.

Formatting and rename logic are deliberately plain Python so they can be
extended with language-specific parsing and scope analysis.

## Execution, debugging, and embedded languages

The generated scaffold includes:

- `.vscode/launch.json` with a language debug configuration entry.
- `.vscode/tasks.json` with configurable `run_command` and `test_command`
  commands.
- A TypeScript client that starts and restarts the Python language server.
- `embedded_languages`, mapped into the generated TextMate grammar's
  `embeddedLanguages` contribution for mixed-language files.

Example:

```python
embedded_languages=(
    ("source.css", "css"),
    ("source.javascript", "javascript"),
)
```

The debug adapter remains an extension-specific integration point: use the
generated launch configuration as the DAP entry point and replace its
language-specific adapter settings when needed. Runner and test commands are
fully configurable in `language.py`.

## Generated files

| File | Purpose |
| --- | --- |
| `language.py` | Python-first language declaration and regeneration script |
| `language-configuration.json` | Comments, pairs, indentation, and folding |
| `syntaxes/<id>.tmLanguage.json` | TextMate grammar and embedded-language scopes |
| `snippets/<id>.json` | VS Code snippets |
| `server/server.py` | Dependency-free Python LSP |
| `client/extension.ts` | VS Code client process launcher |
| `.vscode/launch.json` | Debug configuration placeholder |
| `.vscode/tasks.json` | Run/test task placeholders |

## Development

Run the test suite with:

```bash
pytest -q
```

The project is intentionally dependency-light. The generated server uses only
the Python standard library, while the generated client remains a normal VS
Code TypeScript extension entry point.
