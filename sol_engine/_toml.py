"""Small TOML loading compatibility layer for the dependency-light control plane.

Python 3.11+ uses ``tomllib`` and installed Python 3.9/3.10 environments use
``tomli``. The final fallback intentionally implements only the TOML subset
used by Sol-Engine catalog, recipe, profile, and launch metadata: tables,
arrays-of-tables, primitive values/arrays, inline tables, and multiline strings.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _native_module():
    try:
        import tomllib

        return tomllib
    except ModuleNotFoundError:
        try:
            import tomli

            return tomli
        except ModuleNotFoundError:
            return None


def load(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    native = _native_module()
    if native is not None:
        with source.open("rb") as handle:
            return native.load(handle)
    return loads(source.read_text())


def _strip_comment(line: str) -> str:
    quote = ""
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {'"', "'"}:
            if not quote:
                quote = char
            elif quote == char:
                quote = ""
            continue
        if char == "#" and not quote:
            return line[:index]
    return line


def _split_top_level(value: str, separator: str) -> list[str]:
    """Split a TOML collection without splitting nested collections or strings."""

    parts: list[str] = []
    start = 0
    square_depth = 0
    brace_depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == separator and square_depth == 0 and brace_depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return parts


def _balanced(value: str) -> bool:
    square_depth = 0
    brace_depth = 0
    quote = ""
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        if square_depth < 0 or brace_depth < 0:
            return False
    return square_depth == 0 and brace_depth == 0 and not quote


def _parse_key(raw: str) -> str:
    key = raw.strip()
    if key.startswith(('"', "'")):
        parsed = ast.literal_eval(key)
        if not isinstance(parsed, str):
            raise ValueError(f"invalid TOML key {raw!r}")
        return parsed
    if not key:
        raise ValueError("empty TOML key")
    return key


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith(('"""', "'''")):
        delimiter = value[:3]
        if not value.endswith(delimiter) or len(value) < 6:
            raise ValueError("unterminated TOML multiline string")
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, str):
            raise ValueError(f"invalid TOML multiline string {value!r}")
        return parsed
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith(('"', "'")):
        return ast.literal_eval(value)
    if value.startswith("["):
        if not value.endswith("]"):
            raise ValueError(f"unterminated TOML array {value!r}")
        items = _split_top_level(value[1:-1], ",")
        return [_parse_value(item) for item in items if item]
    if value.startswith("{"):
        if not value.endswith("}"):
            raise ValueError(f"unterminated TOML inline table {value!r}")
        result: dict[str, Any] = {}
        for item in _split_top_level(value[1:-1], ","):
            if not item:
                continue
            assignment = _split_top_level(item, "=")
            if len(assignment) != 2:
                raise ValueError(f"invalid TOML inline-table item {item!r}")
            key = _parse_key(assignment[0])
            if key in result:
                raise ValueError(f"duplicate TOML inline-table key {key!r}")
            result[key] = _parse_value(assignment[1])
        return result
    try:
        return int(value, 10)
    except ValueError:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"unsupported TOML value {value!r}") from exc


def _descend(root: dict[str, Any], parts: list[str], *, array: bool) -> dict[str, Any]:
    node: dict[str, Any] = root
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        existing = node.get(part)
        if last and array:
            if existing is None:
                existing = []
                node[part] = existing
            if not isinstance(existing, list):
                raise ValueError(f"TOML path {'.'.join(parts)!r} changes table kind")
            child: dict[str, Any] = {}
            existing.append(child)
            node = child
            continue
        if isinstance(existing, list):
            if not existing or not isinstance(existing[-1], dict):
                raise ValueError(f"TOML array table {part!r} has no current item")
            node = existing[-1]
            continue
        if existing is None:
            existing = {}
            node[part] = existing
        if not isinstance(existing, dict):
            raise ValueError(f"TOML path {'.'.join(parts)!r} is not a table")
        node = existing
    return node


def loads(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current = root
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = _strip_comment(lines[index]).strip()
        index += 1
        if not line:
            continue
        if line.startswith("[["):
            if line[-2:] != "]" * 2:
                raise ValueError(f"malformed TOML array table: {line!r}")
            parts = [part.strip() for part in line[2:-2].split(".")]
            current = _descend(root, parts, array=True)
            continue
        if line.startswith("[") and line.endswith("]"):
            parts = [part.strip() for part in line[1:-1].split(".")]
            current = _descend(root, parts, array=False)
            continue
        if "=" not in line:
            raise ValueError(f"unsupported TOML line: {line!r}")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        if raw_value.startswith(('"""', "'''")):
            delimiter = raw_value[:3]
            while not raw_value.endswith(delimiter) and index < len(lines):
                raw_value += "\n" + lines[index]
                index += 1
        else:
            while not _balanced(raw_value) and index < len(lines):
                raw_value += "\n" + _strip_comment(lines[index]).strip()
                index += 1
        parsed_key = _parse_key(key)
        if parsed_key in current:
            raise ValueError(f"duplicate TOML key {parsed_key!r}")
        current[parsed_key] = _parse_value(raw_value)
    return root
