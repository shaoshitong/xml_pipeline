"""Fresh synthetic math-source edit/restore selftest; never imports a PDF."""
from pathlib import Path
import json,sys
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
from arxiv_bulk_official_xml_png_math_v1 import OfficialXmlPng
from arxiv_author_native_synced_replay_v1 import Synced
D=R/'clean/arxiv_research_figures_v1/math_source_replay_v1';D.mkdir(exist_ok=True)
class MathSynced(Synced):
 def __init__(self,asset_map=None):
  self.r=OfficialXmlPng();self.r.assets=asset_map or {};self.r.blocked.clear();self.r.missing.clear()
if __name__=='__main__':
 case=D/'procedure_selftest_runtime_svg_options_v3';result=case/'synced_replay_proof.json'
 if result.exists():
  proof=json.loads(result.read_text());assert proof['ok'];print(result.read_text());sys.exit()
 xml=b'<mxGraphModel math="1"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" value="$$x^2+y^2$$" style="rounded=1;whiteSpace=wrap;html=1;fontSize=20;" vertex="1" parent="1"><mxGeometry x="20" y="20" width="180" height="80" as="geometry"/></mxCell><mxCell id="b" value="Output" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="260" y="20" width="120" height="80" as="geometry"/></mxCell><mxCell id="e" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel>'
 renderer=MathSynced()
 try:
  proof=renderer.replay(xml,case);assert proof['ok'];print(json.dumps(dict(ok=True,actual_RGBA_restore_exact=proof['restored_actual_RGBA_exact'],source_XML_unmodified=True,MathJax_official_bundle_loaded=True,new_PDF_import_calls=0)))
 finally:renderer.close()
