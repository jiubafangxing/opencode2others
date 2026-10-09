"""Pi coding agent target (``~/.pi/agent/models.json``)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..model import Model
from ..protocol import Protocol
from ..util import deep_merge, dump_json, env_path, home_dir, load_json
from .base import Context, Target


class PiTarget(Target):
    key = "pi"
    label = "Pi coding agent"
    protocols = None  # Pi understands every protocol

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("pi target")
        group.add_argument(
            "--pi-output",
            type=Path,
            default=None,
            help="override the models.json path for the pi target",
        )
        group.add_argument(
            "--auth-file",
            "--pi-auth-file",
            dest="pi_auth_file",
            type=Path,
            default=None,
            help="override the auth.json path used by --write-auth",
        )
        group.add_argument(
            "--write-auth",
            action="store_true",
            help="also store the key in Pi's auth.json so /login is not needed",
        )

    # -- paths -------------------------------------------------------------- #
    def _base_dir(self) -> Path:
        override = env_path("PI_CODING_AGENT_DIR")
        return override if override else home_dir() / ".pi" / "agent"

    def default_path(self) -> Path:
        return self._base_dir() / "models.json"

    def default_auth_path(self) -> Path:
        return self._base_dir() / "auth.json"

    def default_settings_path(self) -> Path:
        return self._base_dir() / "settings.json"

    # -- rendering ---------------------------------------------------------- #
    def render(self, models: list[Model], ctx: Context, path: Path) -> str:
        provider_api = _dominant_protocol(models)
        entries = [self._entry(m, provider_api) for m in models]
        provider = {
            "name": ctx.provider_name,
            "baseUrl": ctx.base_url,
            "apiKey": ctx.api_key_value,
            "api": provider_api.value,
            "models": entries,
        }
        config: dict = {"providers": {ctx.provider_id: provider}}

        if ctx.merge and path.exists():
            existing = load_json(path)
            deep_merge(existing, config)
            config = existing
        return dump_json(config)

    def additional_files(
        self, models: list[Model], ctx: Context, path: Path
    ) -> list[tuple[Path, str]]:
        """Also pin Pi's startup model via ``settings.json`` when requested."""
        default_model = self.args.default_model
        if not default_model:
            return []
        if default_model not in {m.id for m in models}:
            print(
                f"[warn] pi: default model {default_model!r} is not in the catalog; "
                "settings.json not updated",
                file=sys.stderr,
            )
            return []

        settings_path = self.default_settings_path()
        settings: dict = {}
        if ctx.merge and settings_path.exists():
            settings = load_json(settings_path)
        settings["defaultProvider"] = ctx.provider_id
        settings["defaultModel"] = default_model
        return [(settings_path, dump_json(settings))]

    def _entry(self, model: Model, provider_api: Protocol) -> dict:
        entry: dict = {"id": model.id, "name": model.name}
        if model.reasoning:
            entry["reasoning"] = True
        if model.vision:
            entry["input"] = ["text", "image"]
        if model.context_window:
            entry["contextWindow"] = model.context_window
        if model.max_tokens:
            entry["maxTokens"] = model.max_tokens
        if model.cost:
            entry["cost"] = model.cost
        if model.protocol != provider_api:
            entry["api"] = model.protocol.value
        return entry


def _dominant_protocol(models: list[Model]) -> Protocol:
    counts: dict[Protocol, int] = {}
    for model in models:
        counts[model.protocol] = counts.get(model.protocol, 0) + 1
    if not counts:
        return Protocol.OPENAI_CHAT
    return max(counts, key=counts.get)


def write_auth_file(path: Path, provider_id: str, api_key: str) -> None:
    """Merge an API-key credential into Pi's ``auth.json``."""
    data: dict = {}
    if path.exists():
        try:
            data = load_json(path)
        except Exception:  # noqa: BLE001 - a broken auth file should not be fatal
            data = {}
    data[provider_id] = {"type": "api_key", "key": api_key}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if os.name != "nt":  # POSIX only; chmod is a no-op on Windows
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
