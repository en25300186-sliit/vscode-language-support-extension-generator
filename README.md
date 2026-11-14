# vscode-language-support-extension-generator

A pip-installable Python generator for building a full-featured VS Code language support extension scaffold entirely from Python.

## Install

```bash
pip install .
```

## Python API

```python
from vscode_language_support_extension_generator import generate_extension

generate_extension(
    language_id="mylang",
    display_name="MyLang",
    publisher="acme",
    extension_name="mylang-support",
    file_extensions=(".mlg",),
    aliases=("MLang",),
    output_dir="./generated/mylang",
)
```

## CLI

```bash
vscode-extgen \
  --language-id mylang \
  --display-name MyLang \
  --publisher acme \
  --extension-name mylang-support \
  --file-extension .mlg \
  --alias MLang \
  --output-dir ./generated/mylang
```

The generated extension scaffold includes:

- Declarative editing support (syntax grammar, snippets, comments, brackets, indentation/folding)
- Language-server scaffold for IntelliSense/diagnostics/hover/semantic tokens
- Navigation feature hooks (definition/references/symbols)
- Formatting/refactor/code-action hooks
- Debug and task scaffolding for execution integration

## Configure features in `language.py`

Every generated scaffold includes an editable `language.py`. Use it as the single,
friendly declaration point for your language's syntax:

```python
from pathlib import Path

from vscode_language_support_extension_generator import LanguageSpec, Snippet, VscodeExtensionBuilder

language = LanguageSpec(
    language_id="mylang",
    display_name="MyLang",
    publisher="acme",
    extension_name="mylang-support",
    file_extensions=(".mlg",),
    single_line_comment="//",
    block_comment_start="/*",
    block_comment_end="*/",
    keywords=("if", "else", "fn", "return"),
    literals=("true", "false", "none"),
    operators=("=>", "==", "+", "-"),
    snippets=(
        Snippet("Function", "fn", ("fn ${1:name}() {", "\t$0", "}")),
    ),
)

VscodeExtensionBuilder(language).generate(Path(__file__).parent)
```

Running `python language.py` regenerates TextMate color-coding for keywords,
strings, comments, operators, and literals, plus bracket/quote handling,
comment toggling metadata, indentation/folding rules, and snippets.

The generated `server/server.py` is a dependency-free Python LSP implementation.
It provides completion for declared and discovered symbols, parameter/signature
help, hover documentation and types, live unmatched-bracket/TODO diagnostics,
and semantic tokens. Add symbols directly in `language.py`:

```python
from vscode_language_support_extension_generator import Symbol

symbols=(
    Symbol("print", kind="function", signature="print(value: Any)", documentation="Writes a value."),
    Symbol("UserId", kind="type", type="str", documentation="The user identifier type."),
)
```
