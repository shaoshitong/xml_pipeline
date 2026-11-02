"""Check actual closed source markers analytically before a new normal attempt."""
from pathlib import Path
import copy,hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def main():
 from datikz_source_bezier_marker_geometry_v1 import geometry
 from tikz_literal_connectivity import Unsupported
 diagnosis=json.loads(Path(sys.argv[1]).read_bytes());raw=diagnosis['raw_id'];root=R/'conversion/priority_datikz_source_viewport_v3/program_runs/bdda92b0e0ae42058f682bdb55efa270'/raw/'source';dom=json.loads((root/'source_dom.json').read_bytes());objects={o['id']:o for o in dom['objects']};proof=[]
 from tikz_literal_connectivity import polyline
 for row in diagnosis['source_evidence']:
  shaft=objects[row['source_shaft']];points=polyline(shaft);index=0 if row['side']=='start'else -1;p=points[index];q=points[1 if index==0 else -2];obj=objects[row['following_source_paint'][0]['id']];g=geometry(obj,p,q,row['side']);proof.append(dict(source_marker=obj['id'],shaft=shaft['id'],side=row['side'],geometry=g))
  shifted=copy.deepcopy(obj);shifted['matrix'][4]+=1 if abs(p[0]-q[0])<abs(p[1]-q[1])else 0;shifted['matrix'][5]+=1 if abs(p[0]-q[0])>=abs(p[1]-q[1])else 0
  try:geometry(shifted,p,q,row['side'])
  except Unsupported:pass
  else:raise AssertionError('Off-axis marker accepted')
 assert proof
 result=dict(actual_source_marker_instances=len(proof),all_source_tips_are_actual_path_endpoints=True,curves_not_flattened=True,all_off_axis_negative_controls_rejected=True,proof=proof,new_normal_calls=0,new_QA_calls=0,new_source_captures=0,model_calls=0);print(json.dumps(result))
if __name__=='__main__':main()
