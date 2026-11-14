from __future__ import annotations

import argparse
from pathlib import Path

from .core import generate_extension


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a VS Code language support extension scaffold.")
    parser.add_argument("--language-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--extension-name", required=True)
    parser.add_argument("--file-extension", action="append", default=[])
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    file_extensions = tuple(args.file_extension or [".txt"])
    output = generate_extension(
        language_id=args.language_id,
        display_name=args.display_name,
        publisher=args.publisher,
        extension_name=args.extension_name,
        file_extensions=file_extensions,
        aliases=tuple(args.alias),
        output_dir=Path(args.output_dir),
    )
    print(f"Generated extension scaffold at: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
