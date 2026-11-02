"""Finite continuous-boundary diagnostic for the two already-seen PlantUML cases.

Uses historical hash-checked original-source observations and fresh actual
native marker SVG paths. It changes no quality policy and accepts no sample.
"""
import hashlib,json,math,re,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'));sys.path.append(str(W/'prototype'))

def distance(point,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0
 return math.dist(point,(a[0]+t*dx,a[1]+t*dy))

def directed(source,target):
 lower=0;upper=0
 # A point-to-set distance is 1-Lipschitz. Uniform segment samples therefore
 # give an explicit continuous interval, not just vertex-to-vertex distance.
 for a,b in zip(source,source[1:]+source[:1]):
  count=max(1,math.ceil(math.dist(a,b)/.01));sample=[min(distance((a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count),x,y) for x,y in zip(target,target[1:]+target[:1])) for i in range(count+1)];lower=max(lower,max(sample));upper=max(upper,max(sample)+math.dist(a,b)/count/2)
 return {'lower_bound_px':lower,'upper_bound_px':upper,'sampling_step_px':.01,'certified_by_one_lipschitz_distance':True}

def main():
 import compiler_plantuml_natural_candidate_v5 as compiler
 import svg_source_scene_dom_v1 as scene
 from compiler_svg_scene_backend_v5 import _parts
 from native_marker_geometry_exact_v1 import OBSERVE_SCRIPT
 from native_worker import native
 from svg_convert_v3 import unpack
 source=W/'compiler_plantuml_natural_candidate_v5/development/a157cf5d479746618edcd1df4b562ab8';results=[];out=W/'plantuml_marker_vector_diagnostic_v1'/uuid.uuid4().hex;out.mkdir(parents=True)
 for summary in sorted(source.glob('*/summary.json')):
  row=json.loads(summary.read_text());record=json.loads(Path(row['candidate_record']).read_text());xml=(R/record['code_file']).read_text();profile=json.loads((summary.parent/'candidate_source_check.json').read_text());proof=profile['evidence']['fresh_source_proof'];data=compiler._source_data(proof);match=compiler._match_candidate(data['dom'],data['metadata'],xml)
  runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js';browser=scene._browser();page=browser.new_page()
  try:page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(runtime));observed=page.evaluate(OBSERVE_SCRIPT,{'xml':xml})
  finally:page.close();scene.close_worker_runtime()
  objects=data['dom']['objects'];paths=[o for o in objects if o.get('edge') and o['tag']=='path'];markers=[]
  for arrow in [o for o in objects if o.get('edge') and o['tag']=='polygon']:
   path=next(o for o in paths if o['edge']['id']==arrow['edge']['id']);center=[arrow['bbox']['x']+arrow['bbox']['w']/2,arrow['bbox']['y']+arrow['bbox']['h']/2];side='start' if math.dist(center,path['sampledPoints'][0])<math.dist(center,path['sampledPoints'][-1]) else 'end';edge=match['edge_map'][path['id']];call=next(c for c in reversed(observed) if c['edge']==edge and c['side']==side);paint=next(p for p in call['paint'] if p.get('fill') not in (None,'none','transparent'));d=paint['d']
   if paint.get('transform') or re.search(r'[^MLZmlz\d.,\s+eE-]',d):raise ValueError('actual_native_polygon_unproven')
   values=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',d)));points=[(x+call['offset'],y+call['offset']) for x,y in zip(values[::2],values[1::2])]
   if len(points)>1 and math.dist(points[0],points[-1])<1e-9:points.pop()
   original=_parts(arrow)[0]['points'];forward=directed(original,points);backward=directed(points,original);lower=max(forward['lower_bound_px'],backward['lower_bound_px']);upper=max(forward['upper_bound_px'],backward['upper_bound_px']);markers.append({'source_arrow':arrow['id'],'native_edge':edge,'side':side,'source_polygon':original,'actual_native_polygon':points,'continuous_hausdorff_lower_px':lower,'continuous_hausdorff_upper_px':upper,'certified_at_most_1px':upper<=1,'source_to_native':forward,'native_to_source':backward,'source_paint':arrow['style'],'native_paint':paint,'actual_native_kind':call.get('type'),'pixel_rule_diagnostic':next(m for m in profile['evidence']['source_native_markers']['markers'] if m['source_arrow']==arrow['id'])})
  results.append({'id':record['id'],'markers':markers,'all_continuous_geometry_at_most_1px':all(m['certified_at_most_1px'] for m in markers),'all_quality_gates_unchanged':True,'new_heldout_consumed':0,'model_calls':0});print(json.dumps({'id':record['id'],'markers':[{k:v for k,v in m.items() if k in ('source_arrow','continuous_hausdorff_lower_px','continuous_hausdorff_upper_px','certified_at_most_1px')} for m in markers]}),flush=True)
 report={'schema':'plantuml_actual_continuous_marker_diagnostic_v1','results':results,'historical_hash_checked_original_source_observation':True,'fresh_actual_native_marker_paths':True,'quality_policy_changed':False,'samples_accepted':0,'new_heldout_consumed':0,'model_calls':0};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'report':str(out/'report.json')}),flush=True)

if __name__=='__main__':main()
