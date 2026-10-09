"""Tests for the mini TOML reader/writer."""

from __future__ import annotations

import unittest

from opencode2others import toml_io
from opencode2others.errors import TomlError


SAMPLE = """\
model = "gpt-5"
model_provider = "opencode-go"

[model_providers.opencode-go]
name = "OpenCode Go"
base_url = "https://opencode.ai/zen/go/v1"
env_key = "OPENCODE_API_KEY"
wire_api = "chat"

[projects.'c:\\users\\admin']
trust_level = "trusted"

[tui.model_availability_nux]
"gpt-5.6-sol" = 2
"""


class TomlLoadTest(unittest.TestCase):
    def test_parses_scalars_and_tables(self) -> None:
        data = toml_io.loads(SAMPLE)
        self.assertEqual(data["model"], "gpt-5")
        self.assertEqual(data["model_provider"], "opencode-go")
        self.assertEqual(data["model_providers"]["opencode-go"]["wire_api"], "chat")
        self.assertEqual(data["projects"]["c:\\users\\admin"]["trust_level"], "trusted")
        self.assertEqual(data["tui"]["model_availability_nux"]["gpt-5.6-sol"], 2)

    def test_parses_arrays_and_inline_tables(self) -> None:
        data = toml_io.loads(
            'a = [1, 2, 3]\nb = { x = 1, y = "z" }\nc = "a\\nb"\n'
        )
        self.assertEqual(data["a"], [1, 2, 3])
        self.assertEqual(data["b"], {"x": 1, "y": "z"})
        self.assertEqual(data["c"], "a\nb")

    def test_parses_multiline_strings(self) -> None:
        data = toml_io.loads('x = """\nhello\nworld"""\n')
        self.assertEqual(data["x"], "hello\nworld")
        data = toml_io.loads("y = '''literal\nvalue'''\n")
        self.assertEqual(data["y"], "literal\nvalue")

    def test_bad_input_raises(self) -> None:
        with self.assertRaises(TomlError):
            toml_io.loads("key = \n")


class TomlDumpTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        data = toml_io.loads(SAMPLE)
        dumped = toml_io.dumps(data)
        again = toml_io.loads(dumped)
        self.assertEqual(data, again)

    def test_quotes_keys_with_dots(self) -> None:
        data = {"profiles": {"opencode-go-glm-5.3": {"model": "glm-5.3"}}}
        text = toml_io.dumps(data)
        self.assertIn("[profiles.'opencode-go-glm-5.3']", text)
        self.assertEqual(toml_io.loads(text), data)

    def test_emits_scalars_before_tables(self) -> None:
        data = {
            "model_providers": {"p": {"name": "P"}},
            "model": "m",
        }
        text = toml_io.dumps(data)
        self.assertLess(text.index('model = "m"'), text.index("[model_providers"))


if __name__ == "__main__":
    unittest.main()
