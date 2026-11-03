"""Fresh synthetic wide/negative-coordinate math diagram, unchanged replay gates."""
from pathlib import Path
import json,sys,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
from arxiv_math_synced_renderer_v1 import MathSynced
D=R/'clean/arxiv_research_figures_v1/math_viewport_protocol_selftest_v1';D.mkdir(exist_ok=True)
class Uniform(MathSynced):
 def settled(self):
  self.r.page.evaluate("""()=>{const g=__bulkUi.editor.graph;g.view.setScale(1);g.view.setTranslate(0,0);g.container.scrollLeft=0;g.container.scrollTop=0;}""")
  return super().settled()
root=E.Element('mxGraphModel',dict(math='1',page='1',pageWidth='827',pageHeight='1169',pageScale='1'));cells=E.SubElement(root,'root');E.SubElement(cells,'mxCell',id='0');E.SubElement(cells,'mxCell',id='1',parent='0')
for i,(x,y) in enumerate([(-1800,-700),(-600,100),(800,1000),(2100,1800)]):
 c=E.SubElement(cells,'mxCell',id='v'+str(i),parent='1',vertex='1',value='$$x_'+str(i)+'^2+\\sum_{j=1}^{n}a_j$$',style='rounded=1;html=1;whiteSpace=wrap;fontSize=24;');E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width='500',height='260',**{'as':'geometry'})
 if i:
  e=E.SubElement(cells,'mxCell',id='e'+str(i),parent='1',edge='1',source='v'+str(i-1),target='v'+str(i));E.SubElement(e,'mxGeometry',relative='1',**{'as':'geometry'})
xml=E.tostring(root)
results={}
for name,renderer in [('baseline',MathSynced),('uniform_viewport',Uniform)]:
 case=D/name
 if (case/'synced_replay_proof.json').exists():proof=json.loads((case/'synced_replay_proof.json').read_text())
 else:
  r=renderer()
  try:proof=r.replay(xml,case)
  finally:r.close()
 results[name]={k:proof[k] for k in ['ok','normalized_model_exact_restore','restored_actual_RGBA_exact','restored_SVG_namespace_canonical_exact','source_geometry_topology_style_inventory_sha256','restored_geometry_topology_style_inventory_sha256']}
print(json.dumps(results))
(D/'results.json').write_text(json.dumps(results,indent=2)+'\n')
