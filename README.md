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
