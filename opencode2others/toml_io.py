"""A tiny, dependency-free TOML reader/writer.

Only the subset of TOML that appears in Codex ``config.toml`` files needs to
be supported, but the implementation aims to be correct for ordinary TOML 1.0:

* tables (``[a.b]``) and arrays of tables (``[[a]]``)
* dotted keys, bare keys and quoted keys
* basic/literal strings (single line and multi line)
* booleans, integers (dec/hex/oct/bin), floats
* arrays (possibly multi line) and inline tables

The writer always emits valid TOML and is used both for fresh configs and for
round-tripping a config that was read back with :func:`loads`.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import TomlError

__all__ = ["loads", "dumps", "TomlError"]

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
class _Reader:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0
        self.n = len(text)

    # -- low level helpers -------------------------------------------------- #
    def error(self, message: str) -> TomlError:
        line = self.s.count("\n", 0, self.i) + 1
        column = self.i - (self.s.rfind("\n", 0, self.i) + 1) + 1
        return TomlError(f"{message} at line {line}, column {column}")

    def peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def startswith(self, text: str) -> bool:
        return self.s.startswith(text, self.i)

    def eof(self) -> bool:
        return self.i >= self.n

    def skip_inline_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t":
            self.i += 1

    def skip_comment(self) -> None:
        if self.peek() == "#":
            while self.i < self.n and self.s[self.i] != "\n":
                self.i += 1

    def skip_ws_comments_newlines(self) -> None:
        while self.i < self.n:
            char = self.s[self.i]
            if char in " \t\r\n":
                self.i += 1
            elif char == "#":
                self.skip_comment()
            else:
                break

    def finish_statement(self) -> None:
        self.skip_inline_ws()
        self.skip_comment()
        if self.i < self.n and self.s[self.i] not in "\r\n":
            raise self.error("unexpected trailing characters")
        if self.i < self.n and self.s[self.i] == "\r":
            self.i += 1
        if self.i < self.n and self.s[self.i] == "\n":
            self.i += 1

    # -- strings ------------------------------------------------------------ #
    def parse_basic_string(self) -> str:
        if self.startswith('"""'):
            return self._parse_multiline_basic()
        self.i += 1  # opening quote
        out: list[str] = []
        while True:
            if self.eof():
                raise self.error("unterminated string")
            char = self.s[self.i]
            if char == '"':
                self.i += 1
                return "".join(out)
            if char == "\\":
                out.append(self._parse_escape())
            elif char in "\r\n":
                raise self.error("newline in single-line string")
            else:
                out.append(char)
                self.i += 1

    def _parse_multiline_basic(self) -> str:
        self.i += 3  # opening """
        if self.peek() == "\r":
            self.i += 1
        if self.peek() == "\n":
            self.i += 1
        out: list[str] = []
        while True:
            if self.eof():
                raise self.error("unterminated multi-line string")
            if self.startswith('"""'):
                self.i += 3
                return "".join(out)
            char = self.s[self.i]
            if char == "\\":
                # A backslash at end of line swallows the newline + following
                # whitespace (line continuation) in TOML.
                nxt = self.s[self.i + 1 : self.i + 2]
                if nxt in ("\r", "\n"):
                    self.i += 2
                    if self.s[self.i - 1] == "\r" and self.peek() == "\n":
                        self.i += 1
                    while self.i < self.n and self.s[self.i] in " \t\r\n":
                        self.i += 1
                    continue
                out.append(self._parse_escape())
            else:
                out.append(char)
                self.i += 1

    def _parse_escape(self) -> str:
        assert self.peek() == "\\"
        self.i += 1
        esc = self.peek()
        mapping = {
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "f": "\f",
            "r": "\r",
            '"': '"',
            "\\": "\\",
        }
        if esc in mapping:
            self.i += 1
            return mapping[esc]
        if esc in ("u", "U"):
            self.i += 1
            length = 4 if esc == "u" else 8
            digits = self.s[self.i : self.i + length]
            if len(digits) != length or not re.fullmatch(r"[0-9A-Fa-f]+", digits):
                raise self.error("invalid unicode escape")
            self.i += length
            return chr(int(digits, 16))
        raise self.error(f"invalid escape sequence \\{esc}")

    def parse_literal_string(self) -> str:
        if self.startswith("'''"):
            return self._parse_multiline_literal()
        self.i += 1
        end = self.s.find("'", self.i)
        if end < 0:
            raise self.error("unterminated literal string")
        value = self.s[self.i : end]
        if "\n" in value or "\r" in value:
            raise self.error("newline in single-line literal string")
        self.i = end + 1
        return value

    def _parse_multiline_literal(self) -> str:
        self.i += 3
        if self.peek() == "\r":
            self.i += 1
        if self.peek() == "\n":
            self.i += 1
        end = self.s.find("'''", self.i)
        if end < 0:
            raise self.error("unterminated multi-line literal string")
        value = self.s[self.i : end]
        self.i = end + 3
        return value

    # -- keys / values ------------------------------------------------------ #
    def parse_key_part(self) -> str:
        self.skip_inline_ws()
        char = self.peek()
        if char == '"':
            return self.parse_basic_string()
        if char == "'":
            return self.parse_literal_string()
        match = _BARE_KEY.match(self.s, self.i)
        if not match:
            raise self.error("invalid key")
        self.i = match.end()
        return match.group(0)

    def parse_key(self) -> list[str]:
        parts = [self.parse_key_part()]
        while True:
            self.skip_inline_ws()
            if self.peek() != ".":
                return parts
            self.i += 1
            parts.append(self.parse_key_part())

    def parse_value(self) -> Any:
        self.skip_inline_ws()
        char = self.peek()
        if char == '"':
            return self.parse_basic_string()
        if char == "'":
            return self.parse_literal_string()
        if char == "[":
            return self.parse_array()
        if char == "{":
            return self.parse_inline_table()
        return self.parse_bare_value()

    def parse_bare_value(self) -> Any:
        start = self.i
        while self.i < self.n and self.s[self.i] not in "\r\n,]}":
            self.i += 1
        raw = self.s[start : self.i].strip()
        if not raw:
            raise self.error("missing value")
        if raw == "true":
            return True
        if raw == "false":
            return False
        number = _parse_number(raw)
        if number is not None:
            return number
        # Dates/datetimes are kept as strings; they round-trip as strings.
        return raw

    def parse_array(self) -> list[Any]:
        self.i += 1  # [
        out: list[Any] = []
        while True:
            self.skip_ws_comments_newlines()
            if self.eof():
                raise self.error("unterminated array")
            if self.peek() == "]":
                self.i += 1
                return out
            out.append(self.parse_value())
            self.skip_ws_comments_newlines()
            char = self.peek()
            if char == ",":
                self.i += 1
                continue
            if char == "]":
                self.i += 1
                return out
            raise self.error("expected ',' or ']' in array")

    def parse_inline_table(self) -> dict[str, Any]:
        self.i += 1  # {
        out: dict[str, Any] = {}
        while True:
            self.skip_ws_comments_newlines()
            if self.eof():
                raise self.error("unterminated inline table")
            if self.peek() == "}":
                self.i += 1
                return out
            key = self.parse_key()
            self.skip_inline_ws()
            if self.peek() != "=":
                raise self.error("expected '=' in inline table")
            self.i += 1
            value = self.parse_value()
            _set_path(out, key, value)
            self.skip_ws_comments_newlines()
            char = self.peek()
            if char == ",":
                self.i += 1
                continue
            if char == "}":
                self.i += 1
                return out
            raise self.error("expected ',' or '}' in inline table")

    # -- document ----------------------------------------------------------- #
    def parse(self) -> dict[str, Any]:
        root: dict[str, Any] = {}
        current: dict[str, Any] = root
        while True:
            self.skip_ws_comments_newlines()
            if self.eof():
                return root
            if self.peek() == "[":
                if self.startswith("[["):
                    self.i += 2
                    key = self.parse_key()
                    self.skip_inline_ws()
                    if not self.startswith("]]"):
                        raise self.error("expected ']]'")
                    self.i += 2
                    current = _append_array_table(root, key)
                else:
                    self.i += 1
                    key = self.parse_key()
                    self.skip_inline_ws()
                    if self.peek() != "]":
                        raise self.error("expected ']'")
                    self.i += 1
                    current = _ensure_table(root, key)
                self.finish_statement()
                continue
            key = self.parse_key()
            self.skip_inline_ws()
            if self.peek() != "=":
                raise self.error("expected '='")
            self.i += 1
            value = self.parse_value()
            _set_path(current, key, value)
            self.finish_statement()


def _parse_number(raw: str) -> int | float | None:
    cleaned = raw.replace("_", "")
    if re.fullmatch(r"[+-]?0[xX][0-9A-Fa-f]+", raw):
        return int(cleaned, 16)
    if re.fullmatch(r"[+-]?0[oO][0-7]+", raw):
        return int(cleaned, 8)
    if re.fullmatch(r"[+-]?0[bB][01]+", raw):
        return int(cleaned, 2)
    if re.fullmatch(r"[+-]?\d+", cleaned):
        return int(cleaned)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", cleaned):
        if "." in cleaned or "e" in cleaned or "E" in cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _ensure_table(root: dict[str, Any], key: list[str]) -> dict[str, Any]:
    node = root
    for part in key:
        nxt = node.get(part)
        if nxt is None:
            nxt = {}
            node[part] = nxt
        elif not isinstance(nxt, dict):
            raise TomlError(f"key {part!r} is already defined and is not a table")
        node = nxt
    return node


def _append_array_table(root: dict[str, Any], key: list[str]) -> dict[str, Any]:
    parent = _ensure_table(root, key[:-1])
    name = key[-1]
    arr = parent.get(name)
    if arr is None:
        arr = []
        parent[name] = arr
    if not isinstance(arr, list):
        raise TomlError(f"key {name!r} is not an array of tables")
    item: dict[str, Any] = {}
    arr.append(item)
    return item


def _set_path(table: dict[str, Any], key: list[str], value: Any) -> None:
    node = table
    for part in key[:-1]:
        nxt = node.get(part)
        if nxt is None:
            nxt = {}
            node[part] = nxt
        elif not isinstance(nxt, dict):
            raise TomlError(f"key {part!r} is already defined")
        node = nxt
    node[key[-1]] = value


def loads(text: str) -> dict[str, Any]:
    """Parse a TOML document into a plain ``dict``."""
    return _Reader(text).parse()


# --------------------------------------------------------------------------- #
# Serialising
# --------------------------------------------------------------------------- #
def _format_key(parts: list[str]) -> str:
    return ".".join(_format_key_part(part) for part in parts)


def _format_key_part(key: str) -> str:
    if _BARE_KEY.fullmatch(key):
        return key
    if "'" not in key:
        return f"'{key}'"  # literal string, no escaping needed
    return _format_basic_string(key)


def _format_basic_string(value: str) -> str:
    out = ['"']
    for char in value:
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\b":
            out.append("\\b")
        elif char == "\t":
            out.append("\\t")
        elif char == "\n":
            out.append("\\n")
        elif char == "\f":
            out.append("\\f")
        elif char == "\r":
            out.append("\\r")
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _format_basic_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(
            f"{_format_key([key])} = {_format_value(item)}"
            for key, item in value.items()
        )
        return "{ " + inner + " }"
    raise TomlError(f"cannot serialise value of type {type(value).__name__}")


def _is_array_of_tables(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
    )


def _write_table(
    table: dict[str, Any],
    path: list[str],
    lines: list[str],
    *,
    header: bool,
) -> None:
    scalars: list[tuple[str, Any]] = []
    sub_tables: list[tuple[str, dict[str, Any]]] = []
    array_tables: list[tuple[str, list[dict[str, Any]]]] = []
    for key, value in table.items():
        if isinstance(value, dict):
            sub_tables.append((key, value))
        elif _is_array_of_tables(value):
            array_tables.append((key, value))
        else:
            scalars.append((key, value))

    if header:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"[{_format_key(path)}]")

    for key, value in scalars:
        lines.append(f"{_format_key([key])} = {_format_value(value)}")

    for key, value in sub_tables:
        _write_table(value, path + [key], lines, header=True)

    for key, items in array_tables:
        for item in items:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"[[{_format_key(path + [key])}]]")
            _write_table(item, path + [key], lines, header=False)


def dumps(data: dict[str, Any]) -> str:
    """Serialise a ``dict`` to TOML text (with a trailing newline)."""
    if not isinstance(data, dict):
        raise TomlError("top-level TOML value must be a table")
    lines: list[str] = []
    _write_table(data, [], lines, header=False)
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text
