"""Tests for the four output targets (no network access required)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opencode2others import toml_io
from opencode2others.cli import build_parser
from opencode2others.model import Model
from opencode2others.protocol import Protocol
from opencode2others.targets import (
    ClaudeCodeTarget,
    CodexTarget,
    Context,
    PiTarget,
    ZcodeTarget,
)


def make_models() -> list[Model]:
    return [
        Model(
            id="minimax-m3",
            name="MiniMax-M3",
            protocol=Protocol.ANTHROPIC,
            context_window=1_000_000,
            max_tokens=131_072,
            reasoning=True,
            vision=True,
            cost={"input": 0.3, "output": 1.2, "cacheRead": 0.06, "cacheWrite": 0},
        ),
        Model(
            id="glm-5.3",
            name="GLM-5.3",
            protocol=Protocol.OPENAI_CHAT,
            context_window=1_000_000,
            max_tokens=131_072,
            reasoning=True,
            cost={"input": 0.5, "output": 2.0, "cacheRead": 0.1, "cacheWrite": 0},
        ),
        Model(
            id="glm-5.3-flash",
            name="GLM-5.3-Flash",
            protocol=Protocol.OPENAI_CHAT,
            context_window=1_000_000,
            max_tokens=131_072,
        ),
        Model(
            id="gpt-6-luna",
            name="GPT-6 Luna",
            protocol=Protocol.OPENAI_RESPONSES,
            context_window=1_050_000,
            max_tokens=128_000,
            reasoning=True,
        ),
    ]


def make_context(**overrides) -> Context:
    base = dict(
        provider_id="opencode-go",
        provider_name="OpenCode Go",
        base_url="https://opencode.ai/zen/go/v1",
        api_key_env="OPENCODE_API_KEY",
        resolved_key="sk-test",
        merge=False,
    )
    base.update(overrides)
    return Context(**base)


def default_args():
    return build_parser().parse_args([])


class PiTargetTest(unittest.TestCase):
    def test_renders_every_model(self) -> None:
        target = PiTarget(default_args())
        ctx = make_context()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            data = json.loads(target.render(make_models(), ctx, path))

        provider = data["providers"]["opencode-go"]
        self.assertEqual(provider["apiKey"], "sk-test")
        self.assertEqual(len(provider["models"]), 4)
        # The dominant protocol (chat, 2 models) becomes the provider default.
        self.assertEqual(provider["api"], "openai-completions")
        anthropic = next(m for m in provider["models"] if m["id"] == "minimax-m3")
        self.assertEqual(anthropic["api"], "anthropic-messages")

    def test_merge_preserves_other_providers(self) -> None:
        target = PiTarget(default_args())
        ctx = make_context(merge=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text(
                json.dumps({"providers": {"other": {"name": "Other"}}}),
                encoding="utf-8",
            )
            data = json.loads(target.render(make_models(), ctx, path))
        self.assertIn("other", data["providers"])
        self.assertIn("opencode-go", data["providers"])

    def test_additional_files_writes_default_model(self) -> None:
        args = build_parser().parse_args(["--model", "glm-5.3"])
        target = PiTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            extras = target.additional_files(make_models(), make_context(), Path(tmp) / "models.json")
        self.assertEqual(len(extras), 1)
        settings_path, content = extras[0]
        self.assertEqual(settings_path.name, "settings.json")
        data = json.loads(content)
        self.assertEqual(data["defaultProvider"], "opencode-go")
        self.assertEqual(data["defaultModel"], "glm-5.3")

    def test_additional_files_empty_without_default_model(self) -> None:
        target = PiTarget(default_args())
        self.assertEqual(target.additional_files(make_models(), make_context(), Path("x")), [])


class ClaudeCodeTargetTest(unittest.TestCase):
    def test_writes_anthropic_env(self) -> None:
        target = ClaudeCodeTarget(default_args())
        ctx = make_context()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            data = json.loads(target.render(make_models(), ctx, path))

        env = data["env"]
        # /v1 is stripped because Claude Code appends /v1/messages itself.
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://opencode.ai/zen/go")
        self.assertEqual(env["ANTHROPIC_MODEL"], "minimax-m3")
        self.assertEqual(env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "minimax-m3")

    def test_rejects_non_anthropic_model(self) -> None:
        args = default_args()
        args.claude_model = "glm-5.3"
        target = ClaudeCodeTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                target.render(make_models(), make_context(), Path(tmp) / "s.json")

    def test_uses_anthropic_default_model(self) -> None:
        args = build_parser().parse_args(["--model", "minimax-m3"])
        target = ClaudeCodeTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(target.render(make_models(), make_context(), Path(tmp) / "s.json"))
        self.assertEqual(data["env"]["ANTHROPIC_MODEL"], "minimax-m3")

    def test_non_anthropic_default_falls_back(self) -> None:
        args = build_parser().parse_args(["--model", "glm-5.3"])
        target = ClaudeCodeTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(target.render(make_models(), make_context(), Path(tmp) / "s.json"))
        self.assertEqual(data["env"]["ANTHROPIC_MODEL"], "minimax-m3")


class CodexTargetTest(unittest.TestCase):
    def test_groups_providers_by_wire_api(self) -> None:
        target = CodexTarget(default_args())
        ctx = make_context()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            text = target.render(make_models(), ctx, path)
            data = toml_io.loads(text)

        providers = data["model_providers"]
        self.assertEqual(providers["opencode-go"]["wire_api"], "chat")
        self.assertEqual(providers["opencode-go-responses"]["wire_api"], "responses")
        # Anthropic models must not leak into a Codex config.
        self.assertNotIn("minimax-m3", data["profiles"])
        self.assertIn("opencode-go-glm-5.3", data["profiles"])

    def test_merge_preserves_existing_tables(self) -> None:
        target = CodexTarget(default_args())
        ctx = make_context(merge=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                "[projects.'c:\\users\\admin']\ntrust_level = \"trusted\"\n",
                encoding="utf-8",
            )
            data = toml_io.loads(target.render(make_models(), ctx, path))
        self.assertEqual(data["projects"]["c:\\users\\admin"]["trust_level"], "trusted")
        self.assertIn("model_providers", data)

    def test_uses_default_model(self) -> None:
        args = build_parser().parse_args(["--model", "glm-5.3"])
        target = CodexTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            data = toml_io.loads(target.render(make_models(), make_context(), Path(tmp) / "config.toml"))
        self.assertEqual(data["model"], "glm-5.3")
        self.assertEqual(data["model_provider"], "opencode-go")

    def test_non_openai_default_falls_back(self) -> None:
        args = build_parser().parse_args(["--model", "minimax-m3"])
        target = CodexTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            data = toml_io.loads(target.render(make_models(), make_context(), Path(tmp) / "config.toml"))
        self.assertEqual(data["model"], "glm-5.3")


class ZcodeTargetTest(unittest.TestCase):
    def test_splits_anthropic_and_openai(self) -> None:
        target = ZcodeTarget(default_args())
        ctx = make_context()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            data = json.loads(target.render(make_models(), ctx, path))

        providers = data["provider"]
        self.assertEqual(providers["opencode-go"]["kind"], "anthropic")
        self.assertEqual(providers["opencode-go"]["options"]["baseURL"],
                         "https://opencode.ai/zen/go")
        self.assertEqual(providers["opencode-go-openai"]["kind"], "openai")
        self.assertIn("glm-5.3", providers["opencode-go-openai"]["models"])
        self.assertNotIn("gpt-6-luna", providers["opencode-go-openai"]["models"])

    def test_default_model_is_promoted(self) -> None:
        args = build_parser().parse_args(["--model", "glm-5.3-flash"])
        target = ZcodeTarget(args)
        with tempfile.TemporaryDirectory() as tmp:
            data = json.loads(target.render(make_models(), make_context(), Path(tmp) / "config.json"))
        models = data["provider"]["opencode-go-openai"]["models"]
        self.assertEqual(next(iter(models)), "glm-5.3-flash")


if __name__ == "__main__":
    unittest.main()
