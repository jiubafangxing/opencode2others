"""OpenAI Codex CLI target (``~/.codex/config.toml``).

Codex can talk to OpenAI-compatible endpoints over either ``chat``
(``/chat/completions``) or ``responses`` (``/responses``). Because a single
Codex ``model_provider`` has exactly one ``wire_api``, this target emits one
provider per protocol plus a ``profile`` per model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..errors import TargetError
from ..model import Model
from ..protocol import Protocol
from ..toml_io import dumps as toml_dumps
from ..toml_io import loads as toml_loads
from ..util import env_path, home_dir
from .base import Context, Target


class CodexTarget(Target):
    key = "codex"
    label = "OpenAI Codex CLI"
    protocols = (Protocol.OPENAI_CHAT, Protocol.OPENAI_RESPONSES)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("codex target")
        group.add_argument("--codex-output", type=Path, default=None,
                           help="override the config.toml path")
        group.add_argument("--codex-model", default=None,
                           help="default model id written to the top-level `model`")
        group.add_argument("--codex-api-key-env", default=None,
                           help="env var name Codex reads the key from (default: --api-key-env)")

    def default_path(self) -> Path:
        override = env_path("CODEX_HOME")
        base = override if override else home_dir() / ".codex"
        return base / "config.toml"

    def render(self, models: list[Model], ctx: Context, path: Path) -> str:
        models = self.filter(models)
        if not models:
            raise TargetError("no OpenAI-protocol models are available for Codex")

        chat = [m for m in models if m.protocol == Protocol.OPENAI_CHAT]
        responses = [m for m in models if m.protocol == Protocol.OPENAI_RESPONSES]

        env_key = self.args.codex_api_key_env or ctx.api_key_env
        providers: dict[str, dict] = {}
        profiles: dict[str, dict] = {}
        provider_by_protocol: dict[Protocol, str] = {}

        if chat:
            provider_id = ctx.provider_id
            provider_by_protocol[Protocol.OPENAI_CHAT] = provider_id
            providers[provider_id] = self._provider(ctx.provider_name, ctx.base_url, env_key, "chat")
            profiles.update(self._profiles(provider_id, chat))
        if responses:
            provider_id = f"{ctx.provider_id}-responses"
            provider_by_protocol[Protocol.OPENAI_RESPONSES] = provider_id
            providers[provider_id] = self._provider(
                f"{ctx.provider_name} (Responses)", ctx.base_url, env_key, "responses"
            )
            profiles.update(self._profiles(provider_id, responses))

        chosen = self._choose_model(models, ctx)
        chosen_provider = provider_by_protocol[chosen.protocol]

        config: dict = {
            "model": chosen.id,
            "model_provider": chosen_provider,
            "model_providers": providers,
            "profiles": profiles,
        }

        if ctx.merge and path.exists():
            existing = toml_loads(path.read_text(encoding="utf-8"))
            existing["model"] = config["model"]
            existing["model_provider"] = config["model_provider"]
            existing.setdefault("model_providers", {}).update(providers)
            existing.setdefault("profiles", {}).update(profiles)
            config = existing

        return toml_dumps(config)

    def _choose_model(self, models: list[Model], ctx: Context) -> Model:
        explicit = self.args.codex_model
        if explicit:
            for model in models:
                if model.id == explicit:
                    return model
            available = ", ".join(sorted(m.id for m in models))
            raise TargetError(
                f"model {explicit!r} is not available over an OpenAI protocol "
                f"(available: {available})"
            )

        preferred = self.args.default_model
        if preferred:
            for model in models:
                if model.id == preferred:
                    return model
            print(
                f"[warn] codex: default model {preferred!r} is not available over an "
                "OpenAI protocol; using the first available model",
                file=sys.stderr,
            )
        return models[0]

    @staticmethod
    def _provider(name: str, base_url: str, env_key: str, wire_api: str) -> dict:
        return {
            "name": name,
            "base_url": base_url,
            "env_key": env_key,
            "wire_api": wire_api,
        }

    @staticmethod
    def _profiles(provider_id: str, models: list[Model]) -> dict[str, dict]:
        return {
            f"{provider_id}-{model.id}": {
                "model": model.id,
                "model_provider": provider_id,
            }
            for model in models
        }
