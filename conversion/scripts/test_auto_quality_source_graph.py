"""Synthetic revision/semantic negatives; no dataset payloads or remote calls."""
import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as E
from pathlib import Path
from unittest.mock import patch

import auto_quality_source_graph as gate

sha = lambda data: hashlib.sha256(data).hexdigest()


class SourceGraphGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patch = patch.object(gate, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def record(self, fmt, source, xml):
        folder = self.root / "clean/fixture"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "source.txt").write_text(source)
        return {"id": "synthetic", "source_format": fmt,
                "code_sha256": sha(xml.encode()), "source_code_sha256": sha(source.encode()),
                "source_image_sha256": "imagehash", "original_source_code": "clean/fixture/source.txt"}

    def mermaid(self):
        ast = {"type": "flowchart-v2", "vertices": [["a", {"text": "First"}], ["b", {"text": "Second"}]],
               "edges": [{"start": "a", "end": "b", "text": "Data", "type": "arrow_point"}], "groups": []}
        xml = '<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" vertex="1" parent="1" value="First" mermaidId="n:a"/><mxCell id="b" vertex="1" parent="1" value="Second" mermaidId="n:b"/><mxCell id="e" edge="1" parent="1" source="a" target="b" value="Data" style="startArrow=none;endArrow=block;"/></root></mxGraphModel></diagram></mxfile>'
        return ast, xml

    def run_mermaid(self, record, xml, ast):
        # Keep the real v4 checker; replace only its side-effect-heavy transport
        # dependency and the browser AST parser with a synthetic source fixture.
        dependency = types.ModuleType("mermaid_semantic_audit")
        dependency.PARSE = gate._PARSE
        dependency.text = gate._text
        with patch.dict(sys.modules, {"mermaid_semantic_audit": dependency}), patch.object(gate, "_mermaid_source_ast", return_value=(ast, {"version": "synthetic", "bundle_sha256": "fixture"})):
            return gate.check_graph_profile(record, xml)

    def test_mermaid_positive_and_semantic_negatives(self):
        ast, xml = self.mermaid()
        record = self.record("mermaid", "flowchart LR\na[First] -->|Data| b[Second]", xml)
        good = self.run_mermaid(record, xml, ast)
        self.assertTrue(good["ok"], good)
        for name, bad in {
            "wrong_terminal": xml.replace('target="b"', 'target="a"'),
            "wrong_node_text": xml.replace('value="Second"', 'value="Wrong"'),
            "missing_arrow": xml.replace("endArrow=block", "endArrow=none"),
            "wrong_arrow_side": xml.replace("startArrow=none;endArrow=block", "startArrow=block;endArrow=none"),
            "extra_visible_text": xml.replace('</root>', '<mxCell id="extra" vertex="1" parent="1" value="Unrequested"/></root>'),
            "extra_node_child_text": xml.replace('</root>', '<mxCell id="extra" vertex="1" parent="a" value="Unrequested"/></root>'),
            "extra_edge_child_text": xml.replace('</root>', '<mxCell id="extra" vertex="1" parent="e" value="Unrequested"/></root>'),
            "hidden_node": xml.replace('id="a" vertex="1"', 'id="a" style="opacity=0;" vertex="1"'),
            "hidden_edge_label": xml.replace('startArrow=none;', 'textOpacity=0;startArrow=none;'),
        }.items():
            with self.subTest(name=name):
                changed = {**record, "code_sha256": sha(bad.encode()), "metrics": {"original_reference_ssim_512": 1}, "critic": {"score": 100, "pass": True}}
                result = self.run_mermaid(changed, bad, ast)
                self.assertTrue(result["supported"], result)
                self.assertFalse(result["ok"], result)
        self.assertEqual(good['evidence']['required_source_text_cells'],['a','b','e'])

    def test_mermaid_group_membership_and_unsupported_arrow(self):
        ast, xml = self.mermaid()
        ast["groups"] = [{"id": "group", "title": "Group", "nodes": ["a", "b"]}]
        xml = xml.replace('<mxCell id="a"', '<mxCell id="group" vertex="1" parent="1" value="Group" mermaidId="n:group"/><mxCell id="a"').replace('id="a" vertex="1" parent="1"', 'id="a" vertex="1" parent="group"')
        record = self.record("mermaid", "synthetic source", xml)
        result = self.run_mermaid(record, xml, ast)
        self.assertFalse(result["ok"], result)  # b is outside its required group
        ast["groups"] = []
        ast["edges"][0]["type"] = "arrow_circle"
        self.assertFalse(self.run_mermaid(record, xml, ast)["supported"])

    def test_revision_and_source_hashes_are_required(self):
        ast, xml = self.mermaid()
        record = self.record("mermaid", "source", xml)
        self.assertFalse(self.run_mermaid(record, xml.replace("Data", "Other"), ast)["ok"])
        (self.root / record["original_source_code"]).write_text("modified source")
        result = self.run_mermaid(record, xml, ast)
        self.assertFalse(result["ok"])
        self.assertIn("hash mismatch", result["failures"][0]["error"])

    def tikz(self):
        from PIL import Image
        from svg_convert_v2 import stencil
        from tikz_literal_connectivity import bind
        source = r"\begin{tikzpicture}\node[draw,fill=white] (a) {First};\node[draw,fill=white] (b) {Second};\draw (a) -- node[fill=white] {Data} (b);\end{tikzpicture}"
        style = {"fill": "white", "stroke": "black", "strokeWidth": 1, "fillOpacity": 1, "strokeOpacity": 1, "opacity": 1, "linecap": "butt", "linejoin": "miter", "dash": "none"}
        def shape(cid, x, y, w, h):
            return {"id": cid, "sourceId": cid, "type": "shape", "tag": "rect", "attrs": {"x": x, "y": y, "width": w, "height": h, "rx": 0, "ry": 0}, "style": dict(style), "matrix": [1, 0, 0, 1, 0, 0], "bbox": {"x": x, "y": y, "w": w, "h": h}, "sampledPoints": [[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]}
        def text(cid, label, x, y, w=25):
            return {"id": cid, "sourceId": cid, "type": "text", "text": label, "bbox": {"x": x, "y": y, "w": w, "h": 10}}
        path = {"id": "path", "sourceId": "path", "type": "shape", "tag": "line", "attrs": {"x1": 40, "y1": 10, "x2": 100, "y2": 10}, "style": {**style, "fill": "none"}, "matrix": [1,0,0,1,0,0], "bbox": {"x": 40, "y": 10, "w": 60, "h": .01}}
        dom = {"objects": [shape("a",0,0,40,20), text("ta","First",5,5), shape("b",100,0,40,20), text("tb","Second",105,5), path, shape("bg",58,1,24,14), text("label","Data",60,3,20)], "issues": [], "nodes": {}}
        root = E.fromstring('<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>')
        cr = root.find('.//root')
        for obj in dom["objects"]:
            if obj["type"] == "shape":
                native_shape, bounds = stencil(obj)
                attrs = {"style": "shape="+native_shape+";strokeColor=black;strokeWidth=1;", "value": ""}
            else:
                b = obj["bbox"]
                bounds = (b["x"], b["y"], b["w"], b["h"])
                attrs = {"style": "shape=text;", "value": obj["text"]}
            cell = E.SubElement(cr,"mxCell", {"id":obj["id"],"parent":"1","vertex":"1",**attrs})
            E.SubElement(cell,"mxGeometry",{k:str(v) for k,v in zip(("x","y","width","height"),bounds)})
        baseline = E.tostring(root,encoding="unicode")
        xml, proof = bind(baseline,dom,source)
        self.assertTrue(proof["complete"], proof)
        record = self.record("tikz", source, xml)
        folder = self.root / "clean/fixture"
        Image.new("RGB",(160,40),"white").save(folder/"image.png")
        record.update(original_reference="clean/fixture/image.png", source_image_sha256=sha((folder/"image.png").read_bytes()), source_render_svg="clean/fixture/source.svg", source_render_svg_sha256=sha(b"<svg/>"), previous_candidate_archive="conversion/harness_sessions/fixture/baseline")
        (folder/"source.svg").write_bytes(b"<svg/>")
        archive = self.root / record["previous_candidate_archive"]
        archive.mkdir(parents=True)
        (archive/"diagram.drawio").write_text(baseline)
        (archive/"conversion.json").write_text(json.dumps({**record,"code_sha256":sha(baseline.encode())}))
        return record, xml, dom

    def test_tikz_fresh_binding_rejects_changed_current_graph_and_stale_proof(self):
        record, xml, dom = self.tikz()
        with patch.object(gate, "_source_dom", return_value=(dom,{"dom_extractor_sha256":"fixture"})):
            result = gate.check_graph_profile(record,xml)
            self.assertTrue(result["ok"],result)
            for name,bad in {
                "wrong_terminal":xml.replace('target="b"','target="a"'),
                "wrong_label":xml.replace('value="Data"','value="Wrong"'),
                "detached_label":xml.replace('parent="tikz_label_path"','parent="1"'),
                "deleted_background":xml.replace('id="bg"','id="other"'),
            }.items():
                with self.subTest(name=name):
                    candidate={**record,"code_sha256":sha(bad.encode()),"connectivity":{"complete":True},"native_binding_validation":{"ok":True,"output_code_sha256":sha(bad.encode())}}
                    result=gate.check_graph_profile(candidate,bad)
                    self.assertTrue(result["supported"],result)
                    self.assertFalse(result["ok"],result)
            archive=self.root/record["previous_candidate_archive"]/"diagram.drawio"
            archive.write_text(archive.read_text()+" ")
            result=gate.check_graph_profile(record,xml)
            self.assertFalse(result["ok"],result)
            self.assertIn("hash mismatch",result["failures"][0]["error"])

    def test_tikz_unextracted_visible_features_never_claim_complete_coverage(self):
        record, xml, dom = self.tikz()
        for reason in ("textPath", "unsupported_visible_element", "marker_expansion_failed", "filter", "clipPath", "maskImage", "fill_paint_server", "evenodd_requires_review"):
            with self.subTest(reason=reason):
                incomplete=copy.deepcopy(dom)
                incomplete['issues']=[{'id':'uncovered','reason':reason}]
                with patch.object(gate,"_source_dom",return_value=(incomplete,{})):
                    result=gate.check_graph_profile(record,xml)
                self.assertFalse(result['supported'],result)
                self.assertFalse(result['ok'],result)
                self.assertIn('unmapped visible features',result['failures'][0]['error'])


if __name__ == "__main__":
    unittest.main()
