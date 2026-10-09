"""Discover an OpenCode Go API key from existing local configuration.

Fetching the model catalog never needs a key; a key is only required when we
want to *embed* it into generated config files. To save the user from passing
``--api-key`` on every run, this module can recover the key from configs that
already exist on the machine.

Resolution order:

1. the environment variable named by ``--api-key-env``
2. Pi ``auth.json`` / ``models.json`` (provider entry)
3. ZCode ``config.json`` (provider entry)
4. Claude Code ``settings.json`` (only if its base URL matches)
5. Codex ``auth.json`` (only if it looks like a token, not a URL)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .util import env_path, home_dir, load_json


def mask_secret(secret: str) -> str:
    """Return a display-safe form of ``secret`` (never the full value)."""
    if len(secret) <= 12:
        return "****"
    return f"{secret[:8]}...{secret[-4:]}"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001 - a broken file just means "no key here"
        return {}


def _looks_like_key(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and "://" not in value


def _same_host(left: str, right: str) -> bool:
    try:
        return urlparse(left).hostname == urlparse(right).hostname
    except ValueError:
        return False


def _from_pi(auth_path: Path, models_path: Path, provider_id: str) -> str | None:
    auth = _safe_json(auth_path)
    entry = auth.get(provider_id)
    if isinstance(entry, dict):
        key = entry.get("key") or entry.get("apiKey")
        if _looks_like_key(key):
            return key

    models = _safe_json(models_path)
    provider = (models.get("providers") or {}).get(provider_id) or {}
    key = provider.get("apiKey")
    if _looks_like_key(key) and not str(key).startswith("$"):
        return key
    return None


def _from_zcode(path: Path, base_url: str) -> str | None:
    data = _safe_json(path)
    for entry in (data.get("provider") or {}).values():
        options = (entry or {}).get("options") or {}
        key = options.get("apiKey")
        if not _looks_like_key(key):
            continue
        stored_url = options.get("baseURL") or ""
        if not stored_url or _same_host(stored_url, base_url):
            return key
    return None


def _from_claude(path: Path, base_url: str) -> str | None:
    data = _safe_json(path)
    env = data.get("env") or {}
    key = env.get("ANTHROPIC_AUTH_TOKEN")
    if not _looks_like_key(key):
        return None
    if _same_host(env.get("ANTHROPIC_BASE_URL", ""), base_url):
        return key
    return None


def _from_codex(path: Path) -> str | None:
    data = _safe_json(path)
    key = data.get("OPENAI_API_KEY")
    return key if _looks_like_key(key) else None


def discover_api_key(
    provider_id: str,
    base_url: str,
    api_key_env: str = "OPENCODE_API_KEY",
) -> tuple[str | None, str | None]:
    """Return ``(key, source_description)`` or ``(None, None)``."""
    import os

    env_value = os.environ.get(api_key_env, "").strip()
    if env_value:
        return env_value, f"environment ${api_key_env}"

    pi_dir = env_path("PI_CODING_AGENT_DIR") or (home_dir() / ".pi" / "agent")
    key = _from_pi(pi_dir / "auth.json", pi_dir / "models.json", provider_id)
    if key:
        return key, str(pi_dir / "auth.json")

    zcode_dir = env_path("ZCODE_HOME") or (home_dir() / ".zcode")
    zcode_config = zcode_dir / "v2" / "config.json"
    key = _from_zcode(zcode_config, base_url)
    if key:
        return key, str(zcode_config)

    claude_dir = env_path("CLAUDE_CONFIG_DIR") or (home_dir() / ".claude")
    claude_settings = claude_dir / "settings.json"
    key = _from_claude(claude_settings, base_url)
    if key:
        return key, str(claude_settings)

    codex_dir = env_path("CODEX_HOME") or (home_dir() / ".codex")
    codex_auth = codex_dir / "auth.json"
    key = _from_codex(codex_auth)
    if key:
        return key, str(codex_auth)

    return None, None
