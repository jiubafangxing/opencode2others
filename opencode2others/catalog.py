"""Resolve the live OpenCode Go catalog into a list of :class:`Model`."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from .errors import CatalogError
from .model import Model
from .protocol import ENDPOINT_TO_PROTOCOL, Protocol

OPENCODE_MODELS_URL = "https://opencode.ai/zen/go/v1/models"
OPENCODE_DOCS_URL = "https://opencode.ai/docs/go/"
MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_PROVIDER = "opencode-go"

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_PROVIDER_ID = "opencode-go"
DEFAULT_PROVIDER_NAME = "OpenCode Go"
DEFAULT_API_KEY_ENV = "OPENCODE_API_KEY"
USER_AGENT = "opencode2others/0.2.0"


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get_text(url: str, timeout: float, *, retries: int = 2) -> str:
    """GET ``url`` and return the decoded body, retrying transient failures."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def http_get_json(url: str, timeout: float, *, retries: int = 2) -> Any:
    return json.loads(http_get_text(url, timeout, retries=retries))


def fetch_model_ids(base_url: str, timeout: float) -> list[str]:
    """Return the model ids currently served by OpenCode Go."""
    payload = http_get_json(f"{base_url.rstrip('/')}/models", timeout)
    return [m["id"] for m in payload.get("data", []) if m.get("id")]


# --------------------------------------------------------------------------- #
# Docs endpoint table
# --------------------------------------------------------------------------- #
class _HtmlTableParser(HTMLParser):
    """Collect every ``<table>`` as a list of rows (list of cell strings)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._in_cell = False
        self._cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._table is not None:
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._in_cell = False
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data)


def parse_endpoint_table(html: str) -> dict[str, str]:
    """Extract ``{model_id: endpoint}`` from the OpenCode docs table."""
    parser = _HtmlTableParser()
    parser.feed(html)

    endpoints: dict[str, str] = {}
    for table in parser.tables:
        if not table or table[0][:2] != ["Model", "Model ID"]:
            continue
        for row in table[1:]:
            if len(row) < 3:
                continue
            model_id, endpoint_url = row[1].strip(), row[2].strip()
            if not model_id or not endpoint_url:
                continue
            # https://opencode.ai/zen/go/v1/chat/completions -> chat/completions
            endpoint = re.sub(r"^.*/v1/", "", endpoint_url).strip("/")
            if endpoint in ENDPOINT_TO_PROTOCOL:
                endpoints[model_id] = endpoint
        if endpoints:
            break
    return endpoints


def fetch_doc_endpoints(timeout: float) -> dict[str, str]:
    """Scrape the live endpoint/protocol table from the OpenCode Go docs."""
    try:
        html = http_get_text(OPENCODE_DOCS_URL, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[warn] could not load docs endpoint table: {exc}", file=sys.stderr)
        return {}
    return parse_endpoint_table(html)


# --------------------------------------------------------------------------- #
# models.dev metadata
# --------------------------------------------------------------------------- #
def fetch_metadata(timeout: float) -> dict[str, dict[str, Any]]:
    try:
        data = http_get_json(MODELS_DEV_URL, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"[warn] could not load models.dev metadata: {exc}", file=sys.stderr)
        return {}
    provider = (data or {}).get(MODELS_DEV_PROVIDER) or {}
    models = provider.get("models") or {}
    return dict(models)


# --------------------------------------------------------------------------- #
# Live protocol probing
# --------------------------------------------------------------------------- #
def probe_endpoint(
    base_url: str, model_id: str, api_key: str, timeout: float
) -> str | None:
    """Send a 1-token request to each endpoint; return the first that accepts it."""
    base_url = base_url.rstrip("/")
    attempts: list[tuple[str, dict[str, str], dict[str, Any]]] = [
        (
            "chat/completions",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        ),
        (
            "responses",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {"model": model_id, "input": "hi", "max_output_tokens": 16},
        ),
        (
            "messages",
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            {"model": model_id, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        ),
    ]
    for endpoint, headers, body in attempts:
        request = urllib.request.Request(
            f"{base_url}/{endpoint}",
            data=json.dumps(body).encode("utf-8"),
            headers={**headers, "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return endpoint
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 405):
                continue
            # Any other status means the route exists but our probe was rejected.
            return endpoint
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
@dataclass
class Catalog:
    """The resolved model catalog plus diagnostics."""

    models: list[Model]
    unresolved: list[str] = field(default_factory=list)
    missing_metadata: list[str] = field(default_factory=list)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def protocol_counts(self) -> dict[Protocol, int]:
        counts: dict[Protocol, int] = {}
        for model in self.models:
            counts[model.protocol] = counts.get(model.protocol, 0) + 1
        return counts


def load_catalog(
    base_url: str,
    *,
    timeout: float = 30.0,
    probe: bool = False,
    api_key: str | None = None,
    model_ids: list[str] | None = None,
) -> Catalog:
    """Fetch model ids, metadata and protocols and return a :class:`Catalog`.

    Protocol resolution order:

    1. ``--probe`` live requests (when ``probe`` is true and a key is present)
    2. the endpoint table scraped from the OpenCode Go docs

    Models absent from every source are reported in ``unresolved`` and skipped.
    """
    base_url = base_url.rstrip("/")
    if model_ids is None:
        try:
            model_ids = fetch_model_ids(base_url, timeout)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"failed to fetch model list: {exc}") from exc

    metadata = fetch_metadata(timeout)

    endpoints: dict[str, str] = {}
    if probe:
        if not api_key:
            raise CatalogError("--probe needs a key: pass --api-key or set the env var")
        for model_id in model_ids:
            found = probe_endpoint(base_url, model_id, api_key, timeout)
            if found:
                endpoints[model_id] = found

    # Fill any gaps (or everything when not probing) from the docs table.
    doc_endpoints = fetch_doc_endpoints(timeout)
    if not doc_endpoints and not endpoints:
        raise CatalogError(
            "could not load the endpoint table from the OpenCode Go docs; "
            "aborting (use --probe to detect protocols live)"
        )
    for model_id in model_ids:
        if model_id not in endpoints and model_id in doc_endpoints:
            endpoints[model_id] = doc_endpoints[model_id]

    models: list[Model] = []
    unresolved: list[str] = []
    for model_id in model_ids:
        endpoint = endpoints.get(model_id)
        if endpoint is None:
            unresolved.append(model_id)
            continue
        protocol = ENDPOINT_TO_PROTOCOL[endpoint]
        models.append(Model.from_metadata(model_id, metadata.get(model_id), protocol))

    missing_metadata = [m.id for m in models if m.id not in metadata]
    return Catalog(
        models=models,
        unresolved=unresolved,
        missing_metadata=missing_metadata,
        metadata=metadata,
    )
