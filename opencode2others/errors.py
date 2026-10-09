"""Package-wide exception hierarchy."""

from __future__ import annotations


class OpenCode2OthersError(Exception):
    """Base class for all errors raised by this package."""


class CatalogError(OpenCode2OthersError):
    """Raised when the upstream model catalog cannot be resolved."""


class TargetError(OpenCode2OthersError):
    """Raised by an output target when it cannot build/write its config."""


class TomlError(OpenCode2OthersError):
    """Raised for invalid TOML input when merging Codex configs."""
