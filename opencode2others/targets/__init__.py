"""Output targets (config-file generators) for the supported coding agents."""

from __future__ import annotations

from .base import Context, Target
from .claude_code import ClaudeCodeTarget
from .codex import CodexTarget
from .pi import PiTarget, write_auth_file
from .zcode import ZcodeTarget

#: Ordered registry used by the CLI and for ``--target all``.
TARGET_CLASSES: tuple[type[Target], ...] = (
    PiTarget,
    ClaudeCodeTarget,
    CodexTarget,
    ZcodeTarget,
)

TARGETS: dict[str, type[Target]] = {cls.key: cls for cls in TARGET_CLASSES}

__all__ = [
    "Context",
    "Target",
    "PiTarget",
    "ClaudeCodeTarget",
    "CodexTarget",
    "ZcodeTarget",
    "TARGET_CLASSES",
    "TARGETS",
    "write_auth_file",
]
