"""Wire protocols exposed by OpenCode Go and their Pi ``api`` names.

OpenCode Go serves three endpoints under ``/v1``:

============================ ==========================
OpenCode endpoint            Pi ``api`` value
============================ ==========================
``chat/completions``         ``openai-completions``
``responses``                ``openai-responses``
``messages``                 ``anthropic-messages``
============================ ==========================
"""

from __future__ import annotations

from enum import Enum


class Protocol(str, Enum):
    """A wire protocol (also the exact value used by Pi's ``api`` field)."""

    OPENAI_CHAT = "openai-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC = "anthropic-messages"

    @property
    def endpoint(self) -> str:
        """OpenCode endpoint path (relative to the ``/v1`` base URL)."""
        return PROTOCOL_TO_ENDPOINT[self]

    @property
    def label(self) -> str:
        return {
            Protocol.OPENAI_CHAT: "chat",
            Protocol.OPENAI_RESPONSES: "responses",
            Protocol.ANTHROPIC: "anthropic",
        }[self]


ENDPOINT_TO_PROTOCOL: dict[str, Protocol] = {
    "chat/completions": Protocol.OPENAI_CHAT,
    "responses": Protocol.OPENAI_RESPONSES,
    "messages": Protocol.ANTHROPIC,
}

PROTOCOL_TO_ENDPOINT: dict[Protocol, str] = {
    protocol: endpoint for endpoint, protocol in ENDPOINT_TO_PROTOCOL.items()
}
