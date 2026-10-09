"""Base class shared by all output targets."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..model import Model
from ..protocol import Protocol


@dataclass
class Context:
    """Values every target needs when rendering a configuration."""

    provider_id: str
    provider_name: str
    base_url: str
    api_key_env: str
    resolved_key: str | None
    merge: bool
    verbose: bool = False

    @property
    def api_key_value(self) -> str:
        """The literal key if known, otherwise an env-var reference."""
        return self.resolved_key or f"${self.api_key_env}"


class Target(ABC):
    """A configuration file generator for one coding agent.

    Subclasses declare which wire protocols they can consume and how to turn
    a list of :class:`~opencode2others.model.Model` into a config file.
    """

    key: str = ""
    label: str = ""
    #: Protocols this target understands; ``None`` means "all of them".
    protocols: tuple[Protocol, ...] | None = None

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    # -- CLI integration ---------------------------------------------------- #
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Register target specific options. Override as needed."""

    # -- core API ----------------------------------------------------------- #
    @abstractmethod
    def default_path(self) -> Path:
        """Absolute path of the config file this target writes."""

    @abstractmethod
    def render(self, models: list[Model], ctx: Context, path: Path) -> str:
        """Return the full file contents for ``models``."""

    def additional_files(
        self, models: list[Model], ctx: Context, path: Path
    ) -> list[tuple[Path, str]]:
        """Extra ``(path, content)`` files this target also wants to write.

        The default is none. Targets that need a second file (for example Pi's
        ``settings.json`` for the default model) override this.
        """
        return []

    def filter(self, models: list[Model]) -> list[Model]:
        """Drop models whose protocol this target cannot speak."""
        if self.protocols is None:
            return list(models)
        return [m for m in models if m.protocol in self.protocols]
