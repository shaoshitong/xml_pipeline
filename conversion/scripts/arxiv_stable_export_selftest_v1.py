"""Fresh gradient/math fixture: compare official random export with stable IDs."""
from pathlib import Path
import json,sys,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
from arxiv_math_uniform_viewport_renderer_v1 import MathSynced as Baseline
from arxiv_math_stable_export_renderer_v1 import MathSynced as Stable
D=R/'clean/arxiv_research_figures_v1/stable_export_protocol_selftest_v1';D.mkdir(exist_ok=True)
root=E.Element('mxGraphModel',dict(math='1',page='1'));cells=E.SubElement(root,'root');E.SubElement(cells,'mxCell',id='0');E.SubElement(cells,'mxCell',id='1',parent='0')
for i in range(4):
 c=E.SubElement(cells,'mxCell',id='v'+str(i),parent='1',vertex='1',value='$$x_'+str(i)+'^2+\\sum_{j=1}^{n}a_j$$',style='rounded=1;html=1;whiteSpace=wrap;fontSize=24;fillColor=#fff2cc;gradientColor=#ffd966;gradientDirection=south;');E.SubElement(c,'mxGeometry',x=str(100+i*310),y=str(100+(i%2)*120),width='240',height='100',**{'as':'geometry'})
 if i:
  c=E.SubElement(cells,'mxCell',id='e'+str(i),parent='1',edge='1',source='v'+str(i-1),target='v'+str(i));E.SubElement(c,'mxGeometry',relative='1',**{'as':'geometry'})
xml=E.tostring(root);results={}
for name,cls in [('random_export_ids',Baseline),('stable_export_ids',Stable)]:
 folder=D/name
 if (folder/'synced_replay_proof.json').exists():proof=json.loads((folder/'synced_replay_proof.json').read_text())
 else:
  renderer=cls()
  try:proof=renderer.replay(xml,folder)
  finally:renderer.close()
 results[name]={k:proof[k] for k in ['ok','normalized_model_exact_restore','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact','source_geometry_topology_style_inventory_sha256','restored_geometry_topology_style_inventory_sha256']}
assert not results['random_export_ids']['ok'] and results['random_export_ids']['restored_actual_RGBA_exact']
assert results['stable_export_ids']['ok']
(D/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
