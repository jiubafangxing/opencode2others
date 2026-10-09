"""opencode2others.

Fetch the models served by an OpenCode Go subscription and translate the
catalog into configuration files for several coding agents.

Supported targets
-----------------
* ``pi``          -> Pi coding agent ``models.json``
* ``claude-code`` -> Claude Code ``settings.json``
* ``codex``       -> OpenAI Codex CLI ``config.toml``
* ``zcode``       -> ZCode ``config.json``

The package is intentionally dependency free (Python standard library only).
"""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["__version__"]
