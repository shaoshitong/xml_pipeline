"""Structural frame diagnosis from saved immutable source captures only."""
from pathlib import Path
import json,re,sys,uuid,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def main():
 from datikz_coordinate_routes_v1 import controls
 from priority_datikz_execution_binding_v2 import graph_from_events,coordinate_mapping
 from tikz_execution_graph import parse_events
 rows=[]
 for raw in ['4972350fae3aa6b6abe3d600011fa3c1e8bef241d4c05d9480e7f2be22fc0d74','d33bf4c3f050929ae2907cf8c94f46be081fbe626e11d747d933c2e938982c5b']:
  root=R/'conversion/priority_datikz_source_viewport_v3/program_runs/bdda92b0e0ae42058f682bdb55efa270'/raw/'source';dom=json.loads((root/'source_dom.json').read_bytes());events=parse_events((root/'execution/instrumented/source.iic').read_text());graph=graph_from_events(events)
  frames=[e for e in ET.fromstring((root/'source.svg').read_bytes()).iter()if e.get('data-tikz-physical-pdf-frame')=='1'];assert len(frames)==1;match=re.fullmatch(r'scale\(([0-9.]+)\)',frames[0].get('transform'));assert match;scale=float(match[1])
  row=dict(raw_id=raw,proofs=graph['executed_coordinate_route_proofs'],source_graph_ok=graph['ok'])
  try:row.update(frame_ok=True,frame=coordinate_mapping(dom,graph,[scale,0,0,scale,0,0]))
  except Exception as e:row.update(frame_ok=False,reason=str(e))
  rows.append(row)
 out=R/'conversion/datikz_coordinate_route_development_v1'/uuid.uuid4().hex;out.mkdir(parents=True);result=dict(root=str(out),controls=controls(),results=rows,new_normal_calls=0,new_QA_calls=0,source_recaptures=0,model_calls=0,qualification_claimed=False);(out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
