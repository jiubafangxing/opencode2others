"""Small filesystem / JSON helpers shared across targets."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .errors import OpenCode2OthersError


def home_dir() -> Path:
    """Return the user's home directory, with a helpful error if unavailable."""
    try:
        return Path.home()
    except RuntimeError as exc:  # no HOME / USERPROFILE set
        raise OpenCode2OthersError(
            "cannot determine the home directory; set PI_CODING_AGENT_DIR, "
            "CLAUDE_CONFIG_DIR, CODEX_HOME or HOME/USERPROFILE"
        ) from exc


def env_path(name: str) -> Path | None:
    """Return ``$NAME`` as an expanded :class:`Path`, or ``None`` if unset."""
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else None


def dump_json(data: Any) -> str:
    """Serialise ``data`` as pretty JSON with a trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from ``path`` (empty dict if the file is missing)."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise OpenCode2OthersError(f"failed to read {path}: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenCode2OthersError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OpenCode2OthersError(f"expected a JSON object in {path}")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` into ``base`` (mutates and returns base)."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def write_text(path: Path, content: str, *, backup: bool = True) -> None:
    """Write ``content`` to ``path``, optionally keeping a ``.bak`` copy first."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass
    path.write_text(content, encoding="utf-8")


def strip_api_suffix(base_url: str, suffix: str = "/v1") -> str:
    """Strip a trailing API version segment used by Anthropic-style clients."""
    base_url = base_url.rstrip("/")
    if base_url.endswith(suffix):
        return base_url[: -len(suffix)].rstrip("/")
    return base_url
