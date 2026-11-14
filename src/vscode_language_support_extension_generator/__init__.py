"""Python-first generator for VS Code language support extensions."""

from .core import (
    Feature,
    FeatureMeta,
    FeatureSet,
    LanguageSpec,
    Snippet,
    Symbol,
    VscodeExtensionBuilder,
    generate_extension,
)

__all__ = [
    "Feature",
    "FeatureMeta",
    "FeatureSet",
    "LanguageSpec",
    "Snippet",
    "Symbol",
    "VscodeExtensionBuilder",
    "generate_extension",
]
