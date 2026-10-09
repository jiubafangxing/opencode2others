"""Claude Code target (``~/.claude/settings.json``).

Claude Code only speaks the Anthropic Messages protocol, so this target keeps
the ``anthropic-messages`` models and writes the ``ANTHROPIC_*`` environment
variables that Claude Code reads from its settings file.
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

#: Token-ish substrings used to guess a small/fast model for the "haiku" slot.
_SMALL_HINTS = ("haiku", "flash", "air", "mini", "small", "turbo", "free")


class ClaudeCodeTarget(Target):
    key = "claude-code"
    label = "Claude Code"
    protocols = (Protocol.ANTHROPIC,)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        group = parser.add_argument_group("claude-code target")
        group.add_argument("--claude-output", type=Path, default=None,
                           help="override the settings.json path")
        group.add_argument("--claude-model", default=None,
                           help="model id for ANTHROPIC_MODEL (default: first anthropic model)")
        group.add_argument("--claude-opus-model", default=None,
                           help="model id for ANTHROPIC_DEFAULT_OPUS_MODEL")
        group.add_argument("--claude-sonnet-model", default=None,
                           help="model id for ANTHROPIC_DEFAULT_SONNET_MODEL")
        group.add_argument("--claude-haiku-model", default=None,
                           help="model id for ANTHROPIC_DEFAULT_HAIKU_MODEL")
        group.add_argument("--claude-subagent-model", default=None,
                           help="model id for CLAUDE_CODE_SUBAGENT_MODEL")
        group.add_argument("--claude-timeout-ms", type=int, default=None,
                           help="value for API_TIMEOUT_MS (e.g. 3000000)")

    def default_path(self) -> Path:
        override = env_path("CLAUDE_CONFIG_DIR")
        base = override if override else home_dir() / ".claude"
        return base / "settings.json"

    def render(self, models: list[Model], ctx: Context, path: Path) -> str:
        models = self.filter(models)
        if not models:
            raise TargetError(
                "no anthropic-messages models are available for Claude Code"
            )

        args = self.args
        requested_main = args.claude_model
        if not requested_main and args.default_model:
            if args.default_model in {m.id for m in models}:
                requested_main = args.default_model
            else:
                print(
                    f"[warn] claude-code: default model {args.default_model!r} is not "
                    "available over the Anthropic protocol; using the first "
                    "Anthropic model instead",
                    file=sys.stderr,
                )
        main = self._pick(models, requested_main, (), default_first=True)
        opus = self._pick(models, args.claude_opus_model, (), fallback=main)
        sonnet = self._pick(models, args.claude_sonnet_model, (), fallback=main)
        subagent = self._pick(models, args.claude_subagent_model, (), fallback=main)
        haiku = self._pick(models, args.claude_haiku_model, _SMALL_HINTS, fallback=main)

        env = {
            # Claude Code appends /v1/messages, so strip a trailing /v1 here.
            "ANTHROPIC_BASE_URL": strip_api_suffix(ctx.base_url),
            "ANTHROPIC_AUTH_TOKEN": ctx.resolved_key or f"${{{ctx.api_key_env}}}",
            "ANTHROPIC_MODEL": main,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": opus,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": sonnet,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": haiku,
            "CLAUDE_CODE_SUBAGENT_MODEL": subagent,
        }
        if args.claude_timeout_ms:
            env["API_TIMEOUT_MS"] = str(args.claude_timeout_ms)

        config: dict = {"env": env}
        if ctx.merge and path.exists():
            existing = load_json(path)
            deep_merge(existing, config)
            config = existing
        return dump_json(config)

    @staticmethod
    def _pick(
        models: list[Model],
        explicit: str | None,
        hints: tuple[str, ...],
        *,
        fallback: str | None = None,
        default_first: bool = False,
    ) -> str:
        """Resolve a model id from an explicit value, hints, or fallbacks."""
        ids = {m.id for m in models}
        if explicit:
            if explicit not in ids:
                raise TargetError(
                    f"model {explicit!r} is not available over the Anthropic "
                    f"protocol (available: {', '.join(sorted(ids))})"
                )
            return explicit
        for hint in hints:
            for model in models:
                if hint in model.id.lower():
                    return model.id
        if fallback:
            return fallback
        if default_first:
            return models[0].id
        raise TargetError("could not choose a model")
