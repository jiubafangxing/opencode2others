"""The provider-neutral model description shared by every target."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .protocol import Protocol


@dataclass
class Model:
    """A single model offered by OpenCode Go.

    Attributes
    ----------
    id:
        The upstream model id (what goes on the wire).
    name:
        Human readable name (from models.dev, falls back to ``id``).
    protocol:
        Which OpenCode endpoint serves this model.
    context_window / max_tokens:
        Token limits, when known.
    reasoning:
        Whether the model exposes reasoning / thinking.
    vision:
        Whether the model accepts image input.
    cost:
        ``input`` / ``output`` / ``cacheRead`` / ``cacheWrite`` prices per
        million tokens (models.dev units, may all be zero).
    input_modalities:
        Raw input modalities reported by models.dev (``text``, ``image`` ...).
    """

    id: str
    name: str
    protocol: Protocol
    context_window: int | None = None
    max_tokens: int | None = None
    reasoning: bool = False
    vision: bool = False
    cost: dict[str, float] = field(default_factory=dict)
    input_modalities: list[str] = field(default_factory=lambda: ["text"])

    @classmethod
    def from_metadata(
        cls,
        model_id: str,
        meta: dict[str, Any] | None,
        protocol: Protocol,
    ) -> "Model":
        """Build a :class:`Model` from a models.dev metadata entry."""
        meta = meta or {}
        limit = meta.get("limit") or {}
        modalities = ((meta.get("modalities") or {}).get("input")) or ["text"]
        cost = meta.get("cost") or {}
        return cls(
            id=model_id,
            name=meta.get("name") or model_id,
            protocol=protocol,
            context_window=limit.get("context"),
            max_tokens=limit.get("output"),
            reasoning=bool(meta.get("reasoning")),
            vision=any(m in ("image", "audio", "video") for m in modalities),
            cost={
                "input": cost.get("input", 0),
                "output": cost.get("output", 0),
                "cacheRead": cost.get("cache_read", 0),
                "cacheWrite": cost.get("cache_write", 0),
            },
            input_modalities=list(modalities),
        )
