"""Tests for the catalog helpers (no network access required)."""

from __future__ import annotations

import unittest

from opencode2others.catalog import parse_endpoint_table
from opencode2others.protocol import ENDPOINT_TO_PROTOCOL, Protocol

DOCS_HTML = """
<html><body>
<table>
  <tr><th>Model</th><th>Model ID</th><th>Endpoint</th></tr>
  <tr><td>GLM-5.3</td><td>glm-5.3</td>
      <td>https://opencode.ai/zen/go/v1/chat/completions</td></tr>
  <tr><td>MiniMax-M3</td><td>minimax-m3</td>
      <td>https://opencode.ai/zen/go/v1/messages</td></tr>
  <tr><td>GPT-6 Luna</td><td>gpt-6-luna</td>
      <td>https://opencode.ai/zen/go/v1/responses</td></tr>
</table>
<table><tr><td>unrelated</td></tr></table>
</body></html>
"""


class ParseEndpointTableTest(unittest.TestCase):
    def test_extracts_and_strips_endpoints(self) -> None:
        endpoints = parse_endpoint_table(DOCS_HTML)
        self.assertEqual(
            endpoints,
            {
                "glm-5.3": "chat/completions",
                "minimax-m3": "messages",
                "gpt-6-luna": "responses",
            },
        )

    def test_endpoint_mapping_covers_all_protocols(self) -> None:
        self.assertEqual(
            set(ENDPOINT_TO_PROTOCOL.values()),
            {Protocol.OPENAI_CHAT, Protocol.OPENAI_RESPONSES, Protocol.ANTHROPIC},
        )
        self.assertEqual(Protocol.ANTHROPIC.endpoint, "messages")


if __name__ == "__main__":
    unittest.main()
