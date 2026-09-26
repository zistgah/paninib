from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .errors import ParseError


@dataclass
class IntentStmt:
    verb: str
    name: str
    bindings: Dict[str, str] = field(default_factory=dict)


@dataclass
class Program:
    organism: str
    intents: List[IntentStmt]
    constraints: List[str]
    verify: List[str]
    target_backend: Optional[str] = None
    assertions: List[IntentStmt] = field(default_factory=list)

    def source_summary(self) -> str:
        return (
            f"organism {self.organism} with {len(self.intents)} intent(s), "
            f"{len(self.constraints)} constraint(s), "
            f"{len(self.assertions)} assertion(s)"
        )


_TOKEN = re.compile(
    r"""
    \s+
    |\#[^\n]*
    |//[^\n]*
    |\{|\}|\(|\)|=|,
    |"[^"]*"
    |[A-Za-z_][A-Za-z0-9_.]*
    |[0-9]+(?:\.[0-9]+)?
    """,
    re.VERBOSE,
)


def tokenize(src: str) -> List[tuple[str, str, int]]:
    tokens: List[tuple[str, str, int]] = []
    line = 1
    i = 0
    while i < len(src):
        if src[i] == "\n":
            line += 1
            i += 1
            continue
        m = _TOKEN.match(src, i)
        if not m:
            raise ParseError(f"{line}:?", f"unexpected character {src[i]!r}")
        text = m.group(0)
        i = m.end()
        if text.startswith("#") or text.startswith("//") or text.isspace():
            line += text.count("\n")
            continue
        if text.startswith('"'):
            tokens.append(("string", text[1:-1], line))
        elif text in "{}()=," :
            tokens.append((text, text, line))
        elif text[:1].isdigit():
            tokens.append(("number", text, line))
        else:
            tokens.append(("ident", text, line))
    tokens.append(("eof", "", line))
    return tokens


class Parser:
    def __init__(self, src: str):
        self.tokens = tokenize(src)
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def bump(self):
        t = self.peek()
        if t[0] != "eof":
            self.i += 1
        return t

    def loc(self) -> str:
        return f"line {self.peek()[2]}"

    def expect_ident(self) -> str:
        kind, val, line = self.bump()
        if kind != "ident":
            raise ParseError(f"line {line}", f"expected identifier, got {kind} {val!r}")
        return val

    def expect(self, kind: str):
        got = self.bump()
        if got[0] != kind and got[1] != kind:
            raise ParseError(f"line {got[2]}", f"expected {kind}, got {got}")

    def parse(self) -> Program:
        if self.expect_ident() != "organism":
            raise ParseError(self.loc(), "program must start with `organism`")
        organism = self.expect_ident()
        backend = None
        if self.peek()[0] == "ident" and self.peek()[1] == "backend":
            self.bump()
            backend = self.expect_ident()
        self.expect("{")
        intents: List[IntentStmt] = []
        constraints: List[str] = []
        verify: List[str] = []
        assertions: List[IntentStmt] = []
        while self.peek()[1] not in ("}", "") and self.peek()[0] != "eof":
            section = self.expect_ident()
            self.expect("{")
            if section == "intent":
                while self.peek()[1] != "}":
                    intents.append(self.parse_intent())
            elif section == "constraints":
                constraints.extend(self.parse_names())
            elif section == "verify":
                verify.extend(self.parse_names())
            elif section in ("assertion", "assert", "assertions"):
                while self.peek()[1] != "}":
                    assertions.append(self.parse_intent())
            else:
                raise ParseError(self.loc(), f"unknown section `{section}`")
            self.expect("}")
        self.expect("}")
        return Program(organism, intents, constraints, verify, backend, assertions)

    def parse_intent(self) -> IntentStmt:
        verb = self.expect_ident()
        name = self.expect_ident()
        bindings: Dict[str, str] = {}
        if self.peek()[1] == "{":
            self.bump()
            while self.peek()[1] != "}":
                key = self.expect_ident()
                self.expect("=")
                kind, val, line = self.bump()
                if kind not in ("ident", "string", "number"):
                    raise ParseError(f"line {line}", "expected value")
                bindings[key] = val
                if self.peek()[1] == ",":
                    self.bump()
            self.expect("}")
        return IntentStmt(verb, name, bindings)

    def parse_names(self) -> List[str]:
        names = []
        while self.peek()[0] == "ident":
            names.append(self.bump()[1])
            if self.peek()[1] == ",":
                self.bump()
        return names


def parse_source(src: str) -> Program:
    return Parser(src).parse()
