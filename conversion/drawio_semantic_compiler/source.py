"""Stage 1: unpack draw.io containers and lex XML into located elements.

Expat supplies the tokens and their byte, line and column positions. This
module adds the draw.io container grammar: a bare ``mxGraphModel``, an
``mxfile`` of ``diagram`` pages, and pages stored as deflated or escaped text.
"""

import base64
from dataclasses import dataclass, field
import re
import urllib.parse
from xml.parsers import expat
import zlib

LIMIT = 256 * 1024 ** 2


@dataclass(frozen=True)
class Loc:
    """Start of an element. ``decoded`` positions index the unpacked page text."""
    line: int
    column: int
    byte: int
    page: int | None = None
    decoded: bool = False

    def to_json(self):
        result = {"line": self.line, "column": self.column, "byte": self.byte}
        if self.page is not None:
            result["page"] = self.page
        if self.decoded:
            result["in_decoded_page"] = True
        return result


@dataclass(frozen=True)
class Diagnostic:
    severity: str  # "error" stops compilation; "warning" and "info" are recorded
    code: str
    message: str
    loc: Loc | None = None
    cell_id: str | None = None
    attribute: str | None = None

    def to_json(self):
        result = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.loc is not None:
            result["location"] = self.loc.to_json()
        if self.cell_id is not None:
            result["cell_id"] = self.cell_id
        if self.attribute is not None:
            result["attribute"] = self.attribute
        return result

    def __str__(self):
        where = ""
        if self.loc is not None:
            page = "" if self.loc.page is None else f"page {self.loc.page} "
            where = f" at {page}line {self.loc.line} column {self.loc.column}"
        cell = "" if self.cell_id is None else f" (cell {self.cell_id!r})"
        return f"{self.severity}[{self.code}]{where}{cell}: {self.message}"


class CompileError(Exception):
    def __init__(self, diagnostics):
        self.diagnostics = [diagnostics] if isinstance(diagnostics, Diagnostic) else list(diagnostics)
        super().__init__("; ".join(str(d) for d in self.diagnostics if d.severity == "error"))


def fail(code, message, loc=None, cell_id=None, attribute=None):
    raise CompileError(Diagnostic("error", code, message, loc, cell_id, attribute))


def xml_attributes(pairs):
    def escape(value):
        return (value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
                .replace("\t", "&#9;").replace("\n", "&#10;").replace("\r", "&#13;"))

    return "".join(f' {key}="{escape(value)}"' for key, value in pairs)


class RuleLog:
    def __init__(self):
        self.entries = {}

    def add(self, rule, page, detail=None):
        entry = self.entries.setdefault((rule, page), {"rule": rule, "page": page, "count": 0, "examples": []})
        entry["count"] += 1
        if detail is not None and len(entry["examples"]) < 8:
            entry["examples"].append(detail)


@dataclass(slots=True, eq=False)
class Element:
    tag: str
    attrs: dict
    loc: Loc
    children: list = field(default_factory=list, init=False)

    def get(self, key, default=None):
        return self.attrs.get(key, default)

    def elements(self, tag=None):
        return [c for c in self.children if isinstance(c, Element) and (tag is None or c.tag == tag)]

    def text(self):
        return "".join(c for c in self.children if isinstance(c, str))


def lex(data, page=None, decoded=False):
    """Parse one XML document into located elements."""
    if len(data) > LIMIT:
        fail("input_too_large", f"XML exceeds {LIMIT} bytes")
    parser = expat.ParserCreate()
    parser.ordered_attributes = True
    parser.buffer_text = True
    stack, roots = [], []

    def here():
        return Loc(parser.CurrentLineNumber, parser.CurrentColumnNumber + 1,
                   parser.CurrentByteIndex, page, decoded)

    def start(tag, attributes):
        element = Element(tag, dict(zip(attributes[::2], attributes[1::2])), here())
        (stack[-1].children if stack else roots).append(element)
        stack.append(element)

    def end(tag):
        stack.pop()

    def text(data):
        if stack:
            stack[-1].children.append(data)

    def doctype(*args):
        fail("doctype_not_supported", "document type declarations and entities are not accepted", here())

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = doctype
    try:
        parser.Parse(data, True)
    except expat.ExpatError as error:
        loc = Loc(error.lineno, error.offset + 1, parser.ErrorByteIndex, page, decoded)
        fail("xml_syntax", expat.ErrorString(error.code), loc)
    return roots[0]


def attribute_loc(data, element, name):
    """Locate one attribute inside the start tag at ``element.loc``."""
    start = element.loc.byte
    stop = data.find(b">", start)
    tag = data[start:stop if stop >= 0 else len(data)]
    match = re.search(rb"[\s]" + re.escape(name.encode()) + rb"\s*=", tag)
    if match is None:
        return element.loc
    prefix = tag[:match.start() + 1]
    lines = prefix.count(b"\n")
    column = (len(prefix) - prefix.rfind(b"\n") if lines
              else element.loc.column + len(prefix.decode("utf-8", "replace")))
    return Loc(element.loc.line + lines, column, start + len(prefix), element.loc.page, element.loc.decoded)


@dataclass
class SourcePage:
    index: int                 # 1-based
    encoding: str              # bare | plain | compressed | escaped
    model: Element
    data: bytes                # the bytes that ``model`` locations index
    diagram: Element | None    # the enclosing <diagram>, located in the file
    extras: list = field(default_factory=list)


@dataclass
class SourceFile:
    data: bytes
    container: Element | None  # the <mxfile>, when present
    pages: list
    extras: list               # non-diagram children of <mxfile>
    diagnostics: list


def inflate(text, loc):
    try:
        raw = base64.b64decode("".join(text.split()), validate=True)
        decoder = zlib.decompressobj(-15)
        body = decoder.decompress(raw, LIMIT + 1)
        if len(body) > LIMIT or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError("deflate stream is truncated, oversized or has trailing data")
        return urllib.parse.unquote(body.decode("utf-8"), errors="strict").encode("utf-8")
    except (zlib.error, ValueError) as error:
        fail("compressed_page", f"cannot decode compressed page: {error}", loc)


def unpack(data):
    """Return the page models of a draw.io file with their source positions."""
    diagnostics = []
    root = lex(data)
    if root.tag == "mxGraphModel":
        _relocate(root, 1)
        return SourceFile(data, None, [SourcePage(1, "bare", root, data, None)], [], diagnostics)
    if root.tag != "mxfile":
        fail("not_drawio", f"expected <mxfile> or <mxGraphModel>, found <{root.tag}>", root.loc)
    pages, extras = [], []
    for child in root.children:
        if isinstance(child, str):
            if child.strip():
                diagnostics.append(Diagnostic("warning", "stray_text", "text directly inside <mxfile> has no "
                                              "draw.io meaning and is dropped", root.loc))
            continue
        if child.tag != "diagram":
            extras.append(child)
            continue
        index = len(pages) + 1
        models = child.elements("mxGraphModel")
        others = [c for c in child.elements() if c.tag != "mxGraphModel"]
        body = child.text().strip()
        if models:
            if len(models) > 1 or body:
                fail("ambiguous_page", "a page holds more than one model or mixes a model with text", child.loc)
            _relocate(models[0], index)
            pages.append(SourcePage(index, "plain", models[0], data, child, others))
        elif body:
            encoding = "escaped" if body.startswith("<") else "compressed"
            page_data = body.encode("utf-8") if encoding == "escaped" else inflate(body, child.loc)
            model = lex(page_data, index, True)
            if model.tag != "mxGraphModel":
                fail("not_drawio", f"page {index} decodes to <{model.tag}>, not <mxGraphModel>", child.loc)
            pages.append(SourcePage(index, encoding, model, page_data, child, others))
        else:
            fail("empty_page", f"page {index} has no graph model", child.loc)
    if not pages:
        fail("no_pages", "<mxfile> has no <diagram> pages", root.loc)
    return SourceFile(data, root, pages, extras, diagnostics)


def _relocate(element, page):
    element.loc = Loc(element.loc.line, element.loc.column, element.loc.byte, page, False)
    for child in element.children:
        if isinstance(child, Element):
            _relocate(child, page)
