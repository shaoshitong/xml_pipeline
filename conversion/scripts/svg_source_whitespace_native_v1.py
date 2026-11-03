"""Preserve literal source-run boundary spaces without changing any characters.

The independent source/native font, grapheme geometry and raster gates remain
mandatory: SVG whitespace that was itself collapsed is not assumed supported.
"""
import html


def preserve(cells, positions):
    for identifier, row in positions.items():
        text = row['text']
        if text != text.strip():
            cells[identifier].set('value',
                '<span data-compiler-source-whitespace-scene-v5="true" '
                'style="white-space:pre">' + html.escape(text) + '</span>')


def wrap(text, identifier, offset):
    from compiler_scene_text_v2 import wrap as original_wrap
    value = original_wrap(text, identifier, offset)
    if text != text.strip():
        value = value.replace('style="', 'style="white-space:pre;', 1)
    return value
