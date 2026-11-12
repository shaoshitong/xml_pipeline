"""Stage 2: the draw.io notations carried inside XML attribute values.

These follow how the editor's codec reads them: numbers through JavaScript
``parseFloat``, cell flags through ``!= 0``, and style strings through
``mxStylesheet.getCellStyle``.
"""

from decimal import Decimal, InvalidOperation
import re

_FLOAT = re.compile(r"[ \t\n\r\f\v]*([+-]?(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?))")
_HEX = re.compile(r"\s*[+-]?0[xX]")


def parse_float(text):
    """JavaScript ``parseFloat``: the longest numeric prefix, or None for NaN/Infinity."""
    match = _FLOAT.match(text)
    if match is None:
        return None
    try:
        value = Decimal(match.group(1))
    except InvalidOperation:
        return None
    try:
        as_float = float(value)
    except OverflowError:
        return None
    if as_float in (float("inf"), float("-inf")):
        return None
    return value


def is_numeric(text):
    """``mxUtils.isNumeric`` for a string attribute value."""
    if parse_float(text) is None or _HEX.match(text):
        return False
    try:  # JavaScript isFinite(Number(text))
        return abs(float(text.strip() or "0")) != float("inf")
    except ValueError:
        return False


def number(text):
    """A geometry coordinate as the codec stores it. Returns (Decimal, exact)."""
    value = parse_float(text)
    if value is None:
        return Decimal(0), False  # the codec replaces NaN and infinities by 0
    return value, _FLOAT.match(text).end() == len(text) and text[:1] not in " \t\n\r\f\v+"


def flag(text, default):
    """A cell flag as ``mxCell`` evaluates it. Returns (bool, canonical)."""
    if text is None:
        return default, True
    if text in ("0", "1"):
        return text == "1", True
    if is_numeric(text):
        return parse_float(text) != 0, False
    return bool(text.strip()), False  # a non-numeric string compares unequal to 0


def format_number(value):
    """Shortest decimal that ``parseFloat`` reads back as the same double."""
    as_float = float(value)
    if as_float == int(as_float) and abs(as_float) < 1e16:
        return str(int(as_float))
    return repr(as_float)


def parse_style(text):
    """Split a style into ordered tokens: (key, value) or (None, stylename)."""
    # mxStylesheet reads a leading semicolon as an instruction to start with
    # an empty style instead of inheriting the editor's default style.
    tokens = [(None, "")] if text.startswith(";") else []
    for token in text.split(";"):
        if not token:
            continue
        position = token.find("=")
        tokens.append((None, token) if position < 0 else (token[:position], token[position + 1:]))
    return tuple(tokens)


def canonical_style(tokens):
    """Remove overwritten keys and order keys between stylenames.

    ``getCellStyle`` applies tokens left to right. A ``key=value`` is dead once
    the same key is written again. A stylename may write any key, so keys never
    move across one. Returns (tokens, dropped duplicate count).
    """
    last = {}
    for index, (key, _) in enumerate(tokens):
        if key is not None:
            last[key] = index
    kept = [token for index, token in enumerate(tokens) if token[0] is None or last[token[0]] == index]
    result, run = [], []
    for token in kept:
        if token[0] is None:
            result.extend(sorted(run))
            result.append(token)
            run = []
        else:
            run.append(token)
    result.extend(sorted(run))
    return tuple(result), len(tokens) - len(kept)


def format_style(tokens):
    if tokens == ((None, ""),):
        return ";"
    return ";".join(value if key is None else f"{key}={value}" for key, value in tokens)


def id_seeds_sketch(tokens):
    """Whether the editor paints the cell with a rough canvas seeded by the cell ID.

    ``mxShape.createHandJiggle`` takes the rough canvas when ``sketch`` is not
    0 and ``sketchStyle`` is not ``comic``; ``RoughCanvas.getStyle`` hashes the
    cell ID into the seed of every stroke and fill. Only explicit keys are
    read here; the native acceptance checks the editor's resolved style.
    """
    style = style_map(tokens or ())
    sketch = style.get("sketch")
    if sketch is None or sketch == "none" or (is_numeric(sketch) and parse_float(sketch) == 0):
        return False
    return style.get("sketchStyle") != "comic"


def style_map(tokens):
    """Explicit keys of a style in effect after all tokens are applied."""
    return {key: value for key, value in tokens if key is not None}


_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")
_COLOR_FUNCTION = re.compile(r"(?:rgba?|hsla?|light-dark|var)\(.*\)\Z", re.S)
_NAMED = re.compile(r"[a-zA-Z]+\Z")
COLOR_KEYS = frozenset({
    "fillColor", "strokeColor", "fontColor", "gradientColor", "labelBackgroundColor",
    "labelBorderColor", "swimlaneFillColor", "imageBackground", "imageBorder", "shadowColor",
    "separatorColor", "laneColor",
})


def valid_color(value):
    """Whether a style colour has a form the editor passes to the canvas."""
    return bool(_COLOR.match(value) or _COLOR_FUNCTION.match(value) or _NAMED.match(value))
