"""ZCode target (``~/.zcode/v2/config.json``).

ZCode stores providers under a top-level ``provider`` object. Each provider has
a ``kind`` (``anthropic`` or ``openai``) and its own base URL, so this target
emits one provider per supported protocol group.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..errors import TargetError
from ..model import Model
from ..protocol import Protocol
from ..util import deep_merge, dump_json, env_path, home_dir, load_json, strip_api_suffix
from .base import Context, Target


def _promote(models: list[Model], preferred: str | None) -> list[Model]:
    """Move ``preferred`` to the front so ZCode lists it first."""
    if not preferred:
        return models
    first = [m for m in models if m.id == preferred]
    if not first:
        return models
    return first + [m for m in models if m.id != preferred]


class ZcodeTarget(Target):
    key = "zcode"
    label = "ZCode"
    protocols = None  # handles anthropic + openai-completions explicitly

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("zcode target")
        group.add_argument("--zcode-output", type=Path, default=None,
                           help="override the ZCode config.json path")

    def default_path(self) -> Path:
        override = env_path("ZCODE_HOME")
        base = override if override else home_dir() / ".zcode"
        return base / "v2" / "config.json"

    def render(self, models: list[Model], ctx: Context, path: Path) -> str:
        preferred = self.args.default_model
        anthropic = _promote(
            [m for m in models if m.protocol == Protocol.ANTHROPIC], preferred
        )
        chat = _promote(
            [m for m in models if m.protocol == Protocol.OPENAI_CHAT], preferred
        )
        responses = [m for m in models if m.protocol == Protocol.OPENAI_RESPONSES]

        if responses:
            print(
                f"[warn] zcode: skipping {len(responses)} responses-only model(s) "
                "(zcode has no responses wire kind): "
                + ", ".join(m.id for m in responses),
                file=sys.stderr,
            )

        providers: dict[str, dict] = {}
        if anthropic:
            providers[ctx.provider_id] = self._provider(
                ctx.provider_name,
                "anthropic",
                strip_api_suffix(ctx.base_url),
                anthropic,
                ctx,
            )
        if chat:
            providers[f"{ctx.provider_id}-openai"] = self._provider(
                f"{ctx.provider_name} (OpenAI)",
                "openai",
                ctx.base_url,
                chat,
                ctx,
            )

        if not providers:
            raise TargetError("no models are available for ZCode")

        config: dict = {"provider": providers}
        if ctx.merge and path.exists():
            existing = load_json(path)
            deep_merge(existing, config)
            config = existing
        return dump_json(config)

    def _provider(
        self,
        name: str,
        kind: str,
        base_url: str,
        models: list[Model],
        ctx: Context,
    ) -> dict:
        options: dict = {"apiKey": ctx.resolved_key or "", "baseURL": base_url}
        if not ctx.resolved_key:
            options["apiKeyRequired"] = True

        entries: dict[str, dict] = {}
        for priority, model in enumerate(models, start=1):
            entries[model.id] = self._entry(model, priority)

        return {
            "name": name,
            "kind": kind,
            "options": options,
            "enabled": True,
            "source": "custom",
            "models": entries,
        }

    @staticmethod
    def _entry(model: Model, priority: int) -> dict:
        entry: dict = {"name": model.name}
        if model.reasoning:
            entry["reasoning"] = {
                "enabled": True,
                "variants": ["enabled", "off"],
                "defaultVariant": "enabled",
            }
        limit: dict = {}
        if model.context_window:
            limit["context"] = model.context_window
        if model.max_tokens:
            limit["output"] = model.max_tokens
        if limit:
            entry["limit"] = limit
        entry["modalities"] = {
            "input": ["text"] + (["image"] if model.vision else []),
            "output": ["text"],
        }
        entry["zcode"] = {"modified": False, "priority": priority}
        return entry
