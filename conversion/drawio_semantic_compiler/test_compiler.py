"""Replayable tests of the compiler stages. Standard library only:

    python3 conversion/drawio_semantic_compiler/test_compiler.py
"""

import base64
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compiler import compile_bytes  # noqa: E402
import ir  # noqa: E402
from source import CompileError  # noqa: E402
import syntax  # noqa: E402

CLI = Path(__file__).resolve().parents[1] / "scripts" / "drawio-compile"
if not CLI.exists():
    # A lab deployment stages this package without the wrapper script.
    CLI = Path(__file__).with_name("cli.py")


def model(cells, attrs='grid="1" page="1"'):
    return f"<mxGraphModel {attrs}><root>{cells}</root></mxGraphModel>"


def mxfile(*pages, attrs=""):
    body = "".join(f'<diagram name="P{i}" id="d{i}">{p}</diagram>' for i, p in enumerate(pages, 1))
    return f"<mxfile{attrs}>{body}</mxfile>".encode()


def deflate(text):
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = packer.compress(urllib.parse.quote(text, safe="~()*!.'").encode()) + packer.flush()
    return base64.b64encode(raw).decode()


# (l << 5) - l + charCode, wrapped to int32 at every step, as RoughCanvas.getStyle computes it.
SEEDS = [1, 128, 81, -2009078292, 1065528]

BASE = ('<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="a" value="A" style="rounded=1;html=1;" vertex="1" parent="1">'
        '<mxGeometry x="10" y="20" width="80" height="40" as="geometry"/></mxCell>'
        '<mxCell id="b" value="B" style="ellipse;html=1;" vertex="1" parent="1">'
        '<mxGeometry x="200" y="20" width="80" height="40" as="geometry"/></mxCell>'
        '<mxCell id="e" style="edgeStyle=orthogonalEdgeStyle;exitX=1;exitY=0.5;entryX=0;entryY=0.5;html=1;" '
        'edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry">'
        '<Array as="points"><mxPoint x="150" y="5.5"/></Array></mxGeometry></mxCell>')


def xml(data):
    return compile_bytes(data).xml.decode()


def errors(data):
    try:
        compile_bytes(data)
    except CompileError as error:
        return [d for d in error.diagnostics if d.severity == "error"]
    return []


class Unpacking(unittest.TestCase):
    def test_compressed_escaped_and_plain_pages_converge(self):
        plain = mxfile(model(BASE))
        packed = f'<mxfile><diagram name="P1" id="zz">{deflate(model(BASE))}</diagram></mxfile>'.encode()
        escaped = ('<mxfile><diagram name="P1">' + model(BASE).replace("&", "&amp;").replace("<", "&lt;")
                   + "</diagram></mxfile>").encode()
        self.assertEqual(xml(plain), xml(packed))
        self.assertEqual(xml(plain), xml(escaped))
        report = compile_bytes(packed).report
        self.assertEqual(report["representation_changes"][0]["rule"], "drop_unreferenced_page_id")
        self.assertIn("unpack_compressed_page", [r["rule"] for r in report["representation_changes"]])

    def test_bare_model_is_wrapped(self):
        out = xml(model(BASE).encode())
        self.assertTrue(out.startswith("<mxfile><diagram><mxGraphModel "))
        self.assertEqual(out, xml(out.encode()))

    def test_multiple_pages_keep_order_and_separate_id_spaces(self):
        second = BASE.replace('value="A"', 'value="Other"')
        out = xml(mxfile(model(BASE), model(second)))
        self.assertEqual(out.count("<diagram"), 2)
        self.assertLess(out.index('name="P1"'), out.index('name="P2"'))
        self.assertEqual(out.count('<mxCell id="0"/>'), 2)
        self.assertIn('value="Other"', out.split("<diagram")[2])

    def test_locations_in_compressed_pages_index_the_decoded_page(self):
        broken = model(BASE + '\n<mxCell id="x" vertex="1" parent="nowhere"/>')
        data = f'<mxfile><diagram name="P1">{deflate(broken)}</diagram></mxfile>'.encode()
        (error,) = errors(data)
        self.assertEqual((error.code, error.cell_id, error.attribute), ("unresolved_parent", "x", "parent"))
        self.assertEqual((error.loc.page, error.loc.decoded, error.loc.line), (1, True, 2))
        self.assertEqual(broken.encode()[error.loc.byte:error.loc.byte + 6], b"parent")

    def test_rejects_doctype_and_foreign_roots(self):
        self.assertEqual(errors(b'<!DOCTYPE x [<!ENTITY a "b">]><mxfile/>')[0].code, "doctype_not_supported")
        self.assertEqual(errors(b"<svg/>")[0].code, "not_drawio")
        self.assertEqual(errors(b"<mxfile><diagram>")[0].code, "xml_syntax")
        self.assertEqual(errors(b'<mxfile><diagram name="x">!!!!</diagram></mxfile>')[0].code, "compressed_page")


class Syntax(unittest.TestCase):
    def test_numbers_follow_parse_float(self):
        self.assertEqual(syntax.format_number(syntax.number("80.0")[0]), "80")
        self.assertEqual(syntax.format_number(syntax.number("1e1")[0]), "10")
        self.assertEqual(syntax.format_number(syntax.number("-0")[0]), "0")
        self.assertEqual(syntax.format_number(syntax.number("1.4210854715202004e-14")[0]), "1.4210854715202004e-14")
        self.assertEqual(syntax.number("12px"), (12, False))
        self.assertEqual(syntax.number("NaN"), (0, False))
        self.assertEqual(syntax.number("Infinity"), (0, False))

    def test_flags_follow_the_codec(self):
        self.assertEqual(syntax.flag(None, True), (True, True))
        self.assertEqual(syntax.flag("0", True), (False, True))
        self.assertEqual(syntax.flag("2", False), (True, False))
        self.assertEqual(syntax.flag("false", False), (True, False))
        self.assertEqual(syntax.flag("", True), (False, False))

    def test_style_keys_commute_only_between_stylenames(self):
        tokens = syntax.parse_style("rounded=0;html=1;text;rounded=1;align=left;;fillColor=none")
        style, dropped = syntax.canonical_style(tokens)
        self.assertEqual(syntax.format_style(style), "html=1;text;align=left;fillColor=none;rounded=1")
        self.assertEqual(dropped, 1)
        other, _ = syntax.canonical_style(syntax.parse_style("html=1;text;fillColor=none;rounded=1;align=left;"))
        self.assertEqual(style, other)
        moved, _ = syntax.canonical_style(syntax.parse_style("text;html=1;fillColor=none;rounded=1;align=left"))
        self.assertNotEqual(style, moved)

    def test_style_values_keep_urls_unicode_and_spaces(self):
        text = "shape=image;image=data:image/png,iVBOR=;fontFamily=Noto Sans 中文;a = b"
        self.assertEqual(syntax.format_style(syntax.parse_style(text)), text)

    def test_style_leading_semicolon_keeps_the_default_style_reset(self):
        tokens, _ = syntax.canonical_style(syntax.parse_style(";;strokeColor=red;fillColor=blue;"))
        self.assertEqual(syntax.format_style(tokens), ";fillColor=blue;strokeColor=red")
        data = mxfile(model('<mxCell id="0" style=";"/><mxCell id="1" parent="0" style=";;"/>'))
        result = compile_bytes(data)
        self.assertEqual(result.xml.count(b'style=";"'), 2)
        self.assertTrue(result.report["checks"]["recompilation_byte_stable"])


class Semantics(unittest.TestCase):
    def test_invalid_references_are_located(self):
        data = mxfile(model(BASE + '\n  <mxCell id="x" vertex="1" parent="nowhere"/>'))
        (error,) = errors(data)
        self.assertEqual((error.code, error.cell_id, error.loc.line, error.loc.page), ("unresolved_parent", "x", 2, 1))
        self.assertEqual(data[error.loc.byte:error.loc.byte + 16], b'parent="nowhere"')
        self.assertEqual(errors(mxfile(model(BASE + '<mxCell id="a" parent="1"/>')))[0].code, "duplicate_id")
        loop = BASE + '<mxCell id="p" parent="q" vertex="1"/><mxCell id="q" parent="p" vertex="1"/>'
        self.assertEqual({e.code for e in errors(mxfile(model(loop)))}, {"parent_cycle"})
        self.assertEqual(errors(mxfile(model(BASE + '<mxCell id="r"/>')))[0].code, "model_root")
        self.assertEqual(errors(mxfile(model(BASE + '<mxCell id="v" vertex="1" edge="1" parent="1"/>')))[0].code,
                         "vertex_and_edge")

    def test_dangling_terminal_becomes_a_free_end_with_a_warning(self):
        data = mxfile(model(BASE.replace('target="b"', 'target="gone"')))
        result = compile_bytes(data)
        (warning,) = [d for d in result.report["diagnostics"] if d["code"] == "dangling_terminal"]
        self.assertEqual((warning["cell_id"], warning["attribute"]), ("e", "target"))
        self.assertNotIn("target=", result.xml.decode())

    def test_colour_and_geometry_errors_are_reported(self):
        cells = BASE.replace("rounded=1;", "rounded=1;fillColor=#12;strokeColor=#abcdef;fontColor=none;") \
                    .replace('x="10"', 'x="NaN"').replace('height="40" as', 'height="-4" as', 1)
        result = compile_bytes(mxfile(model(cells)))
        codes = sorted((d["code"], d.get("attribute")) for d in result.report["diagnostics"])
        self.assertEqual(codes, [("invalid_color", "style"), ("invalid_number", "x"), ("negative_size", None)])
        self.assertIn('<mxGeometry y="20" width="80" height="-4" as="geometry"/>', result.xml.decode())

    def test_ir_verifier_rejects_broken_graphs(self):
        document = compile_bytes(mxfile(model(BASE))).document
        page = document.pages[0]
        edge = next(c for c in page.cells.values() if c.kind == ir.EDGE)
        edge.source = 999
        with self.assertRaises(ir.IRError):
            ir.verify(document)
        edge.source = None
        page.cells[edge.parent].children.append(edge.uid)
        with self.assertRaises(ir.IRError):
            ir.verify(document)

    def test_ir_separates_local_and_page_coordinates(self):
        cells = BASE + ('<mxCell id="g" style="group" vertex="1" parent="1">'
                        '<mxGeometry x="100" y="200" width="50" height="50" as="geometry"/></mxCell>'
                        '<mxCell id="c" vertex="1" parent="g"><mxGeometry x="5" y="6" width="9" height="9" '
                        'as="geometry"/></mxCell>')
        result = compile_bytes(mxfile(model(cells)))
        child = next(c for c in result.source_map["pages"][0]["cells"] if c["original_id"] == "c")
        self.assertEqual(child["page_xy"], [105.0, 206.0])
        record = next(c for c in result.ir_json["pages"][0]["cells"] if c["id"] == child["id"])
        self.assertEqual(record["geometry"], {"x": "5", "y": "6", "width": "9", "height": "9"})


class Normalization(unittest.TestCase):
    def test_output_is_compact_and_omits_defaults(self):
        cells = BASE.replace('vertex="1" parent="1"', 'vertex="1" connectable="1" visible="1" collapsed="0" '
                             'edge="0" parent="1"', 1)
        result = compile_bytes(mxfile(model(cells, 'dx="3" dy="4" grid="1" page="1"'),
                                      attrs=' host="h" modified="m" agent="a" etag="e" version="1" type="t"'))
        self.assertEqual(result.xml.decode(), xml(mxfile(model(BASE))))
        self.assertEqual(
            result.xml.decode(),
            '<mxfile><diagram name="P1"><mxGraphModel grid="1" page="1"><root><mxCell id="0"/>'
            '<mxCell id="1" parent="0"/><mxCell id="2" value="A" style="html=1;rounded=1" vertex="1" parent="1">'
            '<mxGeometry x="10" y="20" width="80" height="40" as="geometry"/></mxCell>'
            '<mxCell id="3" value="B" style="ellipse;html=1" vertex="1" parent="1">'
            '<mxGeometry x="200" y="20" width="80" height="40" as="geometry"/></mxCell>'
            '<mxCell id="4" style="edgeStyle=orthogonalEdgeStyle;entryX=0;entryY=0.5;exitX=1;exitY=0.5;html=1" '
            'edge="1" parent="1" source="2" target="3"><mxGeometry relative="1" as="geometry">'
            '<Array as="points"><mxPoint x="150" y="5.5"/></Array></mxGeometry></mxCell>'
            "</root></mxGraphModel></diagram></mxfile>\n")
        rules = {r["rule"]: r["count"] for r in result.report["representation_changes"]}
        self.assertEqual(rules["omit_default_flag"], 4)
        self.assertEqual(rules["drop_file_metadata"], 1)
        self.assertTrue(all(result.report["checks"].values()))

    def test_ids_and_storage_order_do_not_matter(self):
        renamed = BASE
        for old, new in (('"a"', '"node-α"'), ('"b"', '"zz9"'), ('"e"', '"0x1"'), ('"1"', '"layer"')):
            renamed = renamed.replace(f"id={old}", f"id={new}").replace(f"parent={old}", f"parent={new}") \
                             .replace(f"source={old}", f"source={new}").replace(f"target={old}", f"target={new}")
        self.assertEqual(xml(mxfile(model(BASE))), xml(mxfile(model(renamed))))
        group = ('<mxCell id="g" style="group" vertex="1" parent="1"><mxGeometry width="9" height="9" as="geometry"/>'
                 '</mxCell>')
        kids = ['<mxCell id="k%d" value="%d" vertex="1" parent="g"><mxGeometry width="5" height="5" as="geometry"/>'
                '</mxCell>' % (i, i) for i in range(2)]
        ordered = BASE + group + kids[0] + kids[1]
        # Children of different parents interleave freely; siblings keep their order.
        interleaved = '<mxCell id="0"/>' + kids[0] + BASE.replace('<mxCell id="0"/>', "") + group + kids[1]
        self.assertEqual(xml(mxfile(model(ordered))), xml(mxfile(model(interleaved))))

    def test_draw_order_of_overlapping_siblings_is_semantic(self):
        first, second = BASE.split('<mxCell id="b"')[0], '<mxCell id="b"' + BASE.split('<mxCell id="b"')[1]
        head, a_cell = first.split('<mxCell id="a"')
        b_cell, edge = second.split('<mxCell id="e"')
        swapped = head + b_cell + '<mxCell id="a"' + a_cell + '<mxCell id="e"' + edge
        self.assertNotEqual(xml(mxfile(model(BASE))), xml(mxfile(model(swapped))))

    def test_bound_and_free_edge_ends_stay_distinct(self):
        free = BASE.replace(' source="a" target="b"', "").replace(
            '<Array as="points">', '<mxPoint x="90" y="40" as="sourcePoint"/><mxPoint x="200" y="40" '
            'as="targetPoint"/><Array as="points">')
        bound, loose = compile_bytes(mxfile(model(BASE))), compile_bytes(mxfile(model(free)))
        self.assertNotEqual(bound.xml, loose.xml)
        self.assertEqual(bound.report["reducibility_audit"]["retained"][0]["bound_edge_ends"], 2)
        self.assertEqual(loose.report["reducibility_audit"]["retained"][0]["free_edge_ends"], 2)
        self.assertIn('<mxPoint x="90" y="40" as="sourcePoint"/>', loose.xml.decode())

    def test_user_objects(self):
        trivial = BASE.replace('<mxCell id="a" value="A" ', '<object label="A" id="a"><mxCell ') \
                      .replace('</mxCell><mxCell id="b"', '</mxCell></object><mxCell id="b"')
        self.assertEqual(xml(mxfile(model(BASE))), xml(mxfile(model(trivial))))
        data = trivial.replace('<object label="A"', '<UserObject tooltip="t" link="https://x/?a=1&amp;b=2" '
                               'placeholders="1" label="%name%"').replace("</object>", "</UserObject>")
        out = xml(mxfile(model(data)))
        self.assertIn('<UserObject label="%name%" link="https://x/?a=1&amp;b=2" placeholders="1" tooltip="t" '
                      'id="2"><mxCell style="html=1;rounded=1" vertex="1" parent="1">', out)

    def test_ports_relative_children_tables_and_math_survive(self):
        cells = BASE + (
            '<mxCell id="t" value="" style="shape=table;startSize=0;container=1;collapsible=0;childLayout=tableLayout;" '
            'vertex="1" parent="1"><mxGeometry x="10" y="100" width="120" height="40" as="geometry"/></mxCell>'
            '<mxCell id="r" style="shape=tableRow;horizontal=0;" vertex="1" parent="t">'
            '<mxGeometry width="120" height="40" as="geometry"/></mxCell>'
            '<mxCell id="c1" value="$$x^2 &lt; y$$" style="shape=partialRectangle;html=1;" vertex="1" parent="r">'
            '<mxGeometry width="60" height="40" as="geometry"><mxRectangle width="60" height="40" as="alternateBounds"/>'
            '</mxGeometry></mxCell>'
            '<mxCell id="p" style="ellipse;" vertex="1" parent="a"><mxGeometry x="1" y="0.5" width="8" height="8" '
            'relative="1" as="geometry"><mxPoint x="-4" y="-4" as="offset"/></mxGeometry></mxCell>'
            '<mxCell id="lab" value="  two  spaces &#10; line" style="edgeLabel;html=1;" vertex="1" connectable="0" '
            'parent="e"><mxGeometry x="-0.2" relative="1" as="geometry"><mxPoint as="offset"/></mxGeometry></mxCell>')
        result = compile_bytes(mxfile(model(cells, 'math="1"')))
        out = result.xml.decode()
        for piece in ('style="childLayout=tableLayout;collapsible=0;container=1;shape=table;startSize=0"',
                      'value="$$x^2 &lt; y$$"', '<mxRectangle width="60" height="40" as="alternateBounds"/>',
                      '<mxGeometry x="1" y="0.5" width="8" height="8" relative="1" as="geometry">'
                      '<mxPoint x="-4" y="-4" as="offset"/></mxGeometry>',
                      'value="  two  spaces &#10; line" style="edgeLabel;html=1" vertex="1" parent="5" connectable="0">'
                      '<mxGeometry x="-0.2" relative="1" as="geometry"/>', 'math="1"',
                      "exitX=1;exitY=0.5"):
            self.assertIn(piece, out)
        kept = result.report["reducibility_audit"]["retained"][0]
        self.assertEqual((kept["vertex_containers"], kept["stylenames"]), (3, 3))

    def test_coordinate_frames_fold_and_real_groups_stay(self):
        def nest(kind):
            flags = 'style="group" vertex="1" connectable="0"' if kind == "group" else ""
            return (BASE.split('<mxCell id="a"')[0]
                    + f'<mxCell id="f1" {flags} parent="1"><mxGeometry x="7.3" y="-2" width="1" height="1" '
                      'as="geometry"/></mxCell>'
                    + f'<mxCell id="f2" {flags} parent="f1"><mxGeometry x="0.1" y="0.2" as="geometry"/></mxCell>'
                    + f'<mxCell id="f3" {flags} parent="f2"/>'
                    + '<mxCell id="a"' + BASE.split('<mxCell id="a"')[1]
                    .replace('parent="1"', 'parent="f3"')
                    .replace('x="10" y="20"', 'x="2.6" y="21.8"').replace('x="200" y="20"', 'x="192.6" y="21.8"')
                    .replace('x="150" y="5.5"', 'x="142.6" y="7.3"'))
        base = compile_bytes(mxfile(model(BASE)))
        framed = compile_bytes(mxfile(model(nest("frame"))))
        self.assertEqual(base.xml, framed.xml)
        self.assertEqual(base.ir_json, framed.ir_json)
        (rule,) = [r for r in framed.report["rules_applied"] if r["rule"] == "fold_transparent_frame"]
        self.assertEqual(rule["count"], 3)
        folded = [c for c in framed.source_map["pages"][0]["cells"] if "folded_into" in c]
        self.assertEqual([(c["original_id"], c["folded_into"]) for c in folded], [("f1", "1"), ("f2", "1"), ("f3", "1")])
        grouped = compile_bytes(mxfile(model(nest("group"))))
        self.assertNotEqual(base.xml, grouped.xml)
        self.assertEqual(grouped.report["reducibility_audit"]["retained"][0]["vertex_containers"], 3)

    def test_frames_with_meaning_are_kept(self):
        def frame(extra, child=""):
            return BASE + f'<mxCell id="f" {extra} parent="1"/>' + child
        for extra, reason in (('value="named"', "has_value"), ('style="locked=1"', "has_style"),
                              ('visible="0"', "hidden"), ('collapsed="1"', "collapsed"), ('data-x="1"', "has_extensions")):
            result = compile_bytes(mxfile(model(frame(extra))))
            self.assertEqual(result.report["reducibility_audit"]["retained"][0]["frames_kept_by_reason"], {reason: 1})
        relative = frame("", '<mxCell id="k" vertex="1" parent="f"><mxGeometry x="0.5" relative="1" as="geometry"/></mxCell>')
        kept = compile_bytes(mxfile(model(relative))).report["reducibility_audit"]["retained"][0]
        self.assertEqual(kept["frames_kept_by_reason"], {"relative_child": 1})
        terminal = frame("").replace('target="b"', 'target="f"')
        kept = compile_bytes(mxfile(model(terminal))).report["reducibility_audit"]["retained"][0]
        self.assertEqual(kept["frames_kept_by_reason"], {"is_edge_terminal": 1})

    def test_layers_are_kept(self):
        layered = BASE + '<mxCell id="L2" value="Notes" parent="0"/><mxCell id="L3" parent="0" visible="0"/>'
        out = xml(mxfile(model(layered)))
        self.assertIn('<mxCell id="5" value="Notes" parent="0"/><mxCell id="6" parent="0" visible="0"/>', out)

    def test_action_links_pin_cell_ids_and_page_links_pin_page_ids(self):
        link = "data:action/json,{&quot;actions&quot;:[{&quot;toggle&quot;:{&quot;cells&quot;:[&quot;b&quot;]}}]}"
        cells = BASE.replace('<mxCell id="a" value="A" ', f'<object label="A" link="{link}" id="a"><mxCell ') \
                    .replace('</mxCell><mxCell id="b"', '</mxCell></object><mxCell id="b"')
        result = compile_bytes(mxfile(model(cells)))
        self.assertIn('<mxCell id="b" value="B"', result.xml.decode())
        self.assertTrue(result.ir_json["pages"][0]["cell_ids_are_anchors"])
        paged = BASE.replace('<mxCell id="a" value="A" ', '<object label="A" link="data:page/id,d2" id="a"><mxCell ') \
                    .replace('</mxCell><mxCell id="b"', '</mxCell></object><mxCell id="b"')
        out = xml(mxfile(model(paged), model(BASE)))
        self.assertIn('<diagram id="d2" name="P2">', out)

    def test_observed_cell_ids_keep_their_names(self):
        # RoughCanvas.getStyle seeds every stroke from a hash of the cell ID.
        self.assertEqual([syntax.rough_seed(i) for i in ("", "a", "2", "VJmkmMmNDr8svSAsHePi-12", "节点")],
                         SEEDS)
        sketch = BASE.replace('style="rounded=1;html=1;"', 'style="rounded=1;sketch=1;html=1;"')
        result = compile_bytes(mxfile(model(sketch)))
        out = result.xml.decode()
        self.assertIn('<mxCell id="a" value="A" style="html=1;rounded=1;sketch=1" vertex="1" parent="1">', out)
        self.assertIn('<mxCell id="2" value="B"', out)
        self.assertIn('edge="1" parent="1" source="a" target="2">', out)
        cells = result.ir_json["pages"][0]["cells"]
        self.assertEqual([c.get("id_roles") for c in cells], [None, None, ["sketch_seed"], None, None])
        self.assertEqual(result.report["reducibility_audit"]["retained"][0]["observed_cell_ids"], {"sketch_seed": 1})
        self.assertIn("cell_id_is_observed", [d["code"] for d in result.report["diagnostics"]])
        self.assertEqual(result.source_map["pages"][0]["cells"][2]["id_roles"], ["sketch_seed"])
        self.assertEqual(xml(result.xml), out)

        def rename(cells, pairs):
            names = dict(pairs)
            return re.sub(r'\b(id|parent|source|target)="([^"]*)"',
                          lambda m: f'{m.group(1)}="{names.get(m.group(2), m.group(2))}"', cells)

        # Unobserved IDs are storage: any renaming of them converges.
        self.assertEqual(xml(mxfile(model(rename(sketch, (("b", "q-7"), ("e", "edge"), ("1", "L"), ("0", "root")))))), out)
        # The observed ID is content: renaming it is a different drawing.
        self.assertNotEqual(xml(mxfile(model(rename(sketch, (("a", "a2"),))))), out)
        # Counted names step over a kept name, in whatever position it sits.
        clash = xml(mxfile(model(rename(sketch, (("a", "1"), ("1", "L"))))))
        self.assertIn('<mxCell id="0"/><mxCell id="2" parent="0"/><mxCell id="1" value="A" ', clash)
        self.assertIn('<mxCell id="3" value="B"', clash)
        self.assertEqual(xml(clash.encode()), clash)
        self.assertEqual(xml(mxfile(model(rename(sketch, (("a", "1"), ("1", "zz"), ("b", "0x0"), ("0", "r")))))), clash)

        def roles(style):
            cells = compile_bytes(mxfile(model(BASE.replace('style="rounded=1;html=1;"', f'style="{style}"'))))
            return cells.ir_json["pages"][0]["cells"][2].get("id_roles")

        # createHandJiggle: sketch != 0 takes the rough canvas unless sketchStyle is comic.
        for style in ("sketch=1", "sketch=0;sketch=1", "sketch=true", "sketch=", "sketch=2;sketchStyle=rough",
                      "sketch=1;curveFitting=1;jiggle=2"):
            self.assertEqual(roles(style), ["sketch_seed"], style)
        for style in ("sketch=0", "sketch=1;sketch=0", "sketch=0.0", "sketch=none", "sketch=1;sketchStyle=comic",
                      "comic=1", "sketchStyle=rough"):
            self.assertIsNone(roles(style), style)

        # Graph.replacePlaceholders prints the cell ID for %id%.
        def placeholder(label, extra):
            cells = BASE.replace('<mxCell id="a" value="A" ', f'<object label="{label}" {extra} id="a"><mxCell ') \
                        .replace('</mxCell><mxCell id="b"', '</mxCell></object><mxCell id="b"')
            return compile_bytes(mxfile(model(cells)))

        printed = placeholder("Node %id%", 'placeholders="1"')
        self.assertIn('<object label="Node %id%" placeholders="1" id="a">', printed.xml.decode())
        self.assertEqual(printed.ir_json["pages"][0]["cells"][2]["id_roles"], ["placeholder"])
        self.assertIn(' id="a">', placeholder("Node", 'placeholders="1" tooltip="cell %id%"').xml.decode())
        for label, extra in (("Node %id%", 'placeholders="0"'), ("Node %id%", 'tag="x"'), ("Node %name%", 'placeholders="1"')):
            self.assertIn(' id="2">', placeholder(label, extra).xml.decode(), (label, extra))

        # An observed ID the file leaves to the editor's counter cannot be kept by name.
        implicit = compile_bytes(mxfile(model(sketch.replace('<mxCell id="a" ', "<mxCell "))))
        self.assertIn("implicit_semantic_id", [d["code"] for d in implicit.report["diagnostics"]])

    def test_extension_content_is_carried_through(self):
        cells = BASE.replace('<mxCell id="b" ', '<mxCell id="b" zeta="1" data-name="n&amp;m" ') \
                    .replace('<Array as="points">', '<mxPoint x="1" as="custom"/><Array as="points">')
        data = mxfile(model(cells, 'grid="1" page="1" extFonts="A^https://f/a.woff"'), attrs=' vars="{&quot;k&quot;:1}"')
        data = data.replace(b"</mxfile>", b"<voutline>\n  <x y='1'/>\n</voutline></mxfile>")
        out = xml(data)
        for piece in ('<mxfile vars="{&quot;k&quot;:1}">', 'data-name="n&amp;m" zeta="1"',
                      '<mxPoint as="custom" x="1"/>', 'extFonts="A^https://f/a.woff"',
                      '<voutline><x y="1"/></voutline></mxfile>'):
            self.assertIn(piece, out)

    def test_recompilation_is_byte_stable_across_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "in.drawio").write_bytes(mxfile(model(BASE)))
            for name, source in (("one", "in.drawio"), ("two", "one/canonical.drawio"), ("three", "in.drawio")):
                done = subprocess.run([sys.executable, str(CLI), str(folder / source), "--out", str(folder / name)],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
            outputs = {(folder / name / "canonical.drawio").read_bytes() for name in ("one", "two", "three")}
            self.assertEqual(len(outputs), 1)
            self.assertEqual((folder / "one/ir.json").read_bytes(), (folder / "two/ir.json").read_bytes())
            report = json.loads((folder / "one/report.json").read_text())
            self.assertEqual(report["checks"], {"ir_verified": True, "emitted_xml_rebuilds_ir": True,
                                                "recompilation_byte_stable": True, "emitted_xml_is_fixed_point": True})
            again = subprocess.run([sys.executable, str(CLI), str(folder / "in.drawio"), "--out", str(folder / "one")],
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 2)
            (folder / "bad.drawio").write_bytes(mxfile(model(BASE + '<mxCell id="x" parent="nope"/>')))
            bad = subprocess.run([sys.executable, str(CLI), str(folder / "bad.drawio"), "--out", str(folder / "bad")],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("error[unresolved_parent] at page 1 line 1 column", bad.stderr)
            self.assertFalse((folder / "bad").exists())


if __name__ == "__main__":
    unittest.main()
