"""Small parser for the text KV3 emitted by SteamTracking's Deadlock extractor.

This deliberately fails closed on syntax it does not understand. A failed parse must
never become an empty snapshot or a mass-removal report.
"""

from __future__ import annotations

import json
import re


TOKEN = re.compile(
    r'''\s+|<!--.*?-->|//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]=,]|[^\s{}\[\]=,"/]+|/''',
    re.DOTALL,
)


class KV3Error(ValueError):
    pass


def tokenize(source: str) -> list[str]:
    tokens = []
    position = 0
    while position < len(source):
        match = TOKEN.match(source, position)
        if not match:
            raise KV3Error(f"Unsupported syntax at offset {position}")
        token = match.group()
        position = match.end()
        if not token.isspace() and not token.startswith(("<!--", "//", "/*")):
            tokens.append(token)
    return tokens


class Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def take(self) -> str:
        if self.index >= len(self.tokens):
            raise KV3Error("Unexpected end of file")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def value(self):
        token = self.take()
        if token == "{":
            result = {}
            while self.peek() != "}":
                if self.peek() is None:
                    raise KV3Error("Unclosed object")
                if self.peek() == ",":
                    self.take()
                    continue
                key = self.take()
                if key.startswith('"'):
                    key = json.loads(key)
                if self.take() != "=":
                    raise KV3Error(f"Expected '=' after {key!r}")
                if key in result:
                    raise KV3Error(f"Duplicate key {key!r}")
                result[key] = self.value()
            self.take()
            return result
        if token == "[":
            result = []
            while self.peek() != "]":
                if self.peek() is None:
                    raise KV3Error("Unclosed array")
                if self.peek() == ",":
                    self.take()
                    continue
                result.append(self.value())
            self.take()
            return result
        if token.startswith('"'):
            return json.loads(token)
        if token.endswith(":"):
            # KV3 typed literals, such as resource_name:"path", retain the value.
            return self.value()
        if token == "true":
            return True
        if token == "false":
            return False
        if token == "null":
            return None
        if re.fullmatch(r"[-+]?(?:0x[0-9a-fA-F]+|\d+)", token):
            return int(token, 0) if "0x" in token.lower() else int(token)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+|\d+(?:\.\d*)?[eE][-+]?\d+)", token):
            return float(token)
        if token in ("}", "]", "=", ","):
            raise KV3Error(f"Unexpected token {token!r}")
        return token


def loads(source: str):
    parser = Parser(tokenize(source))
    value = parser.value()
    if parser.peek() is not None:
        raise KV3Error(f"Trailing token {parser.peek()!r}")
    if not isinstance(value, dict) or not value:
        raise KV3Error("Expected a nonempty KV3 root object")
    return value
