"""Tests for API-key discovery helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opencode2others.credentials import (
    _from_claude,
    _from_codex,
    _from_pi,
    _from_zcode,
    _looks_like_key,
    _same_host,
    mask_secret,
)

BASE = "https://opencode.ai/zen/go/v1"


class MaskSecretTest(unittest.TestCase):
    def test_masks_long_secret(self) -> None:
        masked = mask_secret("oc_sk_1234567890abcdef")
        self.assertTrue(masked.startswith("oc_sk_12"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertNotIn("7890", masked)

    def test_short_secret_is_fully_hidden(self) -> None:
        self.assertEqual(mask_secret("short"), "****")

    def test_looks_like_key(self) -> None:
        self.assertTrue(_looks_like_key("sk-abc"))
        self.assertFalse(_looks_like_key(""))
        self.assertFalse(_looks_like_key("https://example.com"))
        self.assertFalse(_looks_like_key(None))

    def test_same_host(self) -> None:
        self.assertTrue(_same_host("https://opencode.ai/zen/go", BASE))
        self.assertFalse(_same_host("https://open.bigmodel.cn/api/anthropic", BASE))


class DiscoveryTest(unittest.TestCase):
    def test_pi_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auth = Path(tmp) / "auth.json"
            auth.write_text(
                json.dumps({"opencode-go": {"type": "api_key", "key": "oc_sk_pi"}}),
                encoding="utf-8",
            )
            self.assertEqual(
                _from_pi(auth, Path(tmp) / "models.json", "opencode-go"), "oc_sk_pi"
            )

    def test_pi_models_literal_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp) / "models.json"
            models.write_text(
                json.dumps({"providers": {"opencode-go": {"apiKey": "oc_sk_models"}}}),
                encoding="utf-8",
            )
            self.assertEqual(
                _from_pi(Path(tmp) / "auth.json", models, "opencode-go"), "oc_sk_models"
            )

    def test_pi_models_env_reference_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp) / "models.json"
            models.write_text(
                json.dumps({"providers": {"opencode-go": {"apiKey": "$OPENCODE_API_KEY"}}}),
                encoding="utf-8",
            )
            self.assertIsNone(
                _from_pi(Path(tmp) / "auth.json", models, "opencode-go")
            )

    def test_zcode_matching_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "provider": {
                            "opencode-go": {
                                "options": {
                                    "apiKey": "oc_sk_z",
                                    "baseURL": "https://opencode.ai/zen/go/v1",
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(_from_zcode(config, BASE), "oc_sk_z")

    def test_claude_requires_matching_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text(
                json.dumps(
                    {"env": {"ANTHROPIC_AUTH_TOKEN": "sk-x", "ANTHROPIC_BASE_URL": BASE}}
                ),
                encoding="utf-8",
            )
            self.assertEqual(_from_claude(settings, BASE), "sk-x")
            self.assertIsNone(_from_claude(settings, "https://other.example/v1"))

    def test_codex_ignores_url_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auth = Path(tmp) / "auth.json"
            auth.write_text(
                json.dumps({"OPENAI_API_KEY": "https://opencode.ai/zen/go/v1/chat/completions"}),
                encoding="utf-8",
            )
            self.assertIsNone(_from_codex(auth))


if __name__ == "__main__":
    unittest.main()
