"""Finite structural development on consumed failures; no normal/QA reruns."""
from pathlib import Path
import argparse,copy,hashlib,json,sqlite3,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S));sys.path.append(str(R/'conversion/prototype'))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--offset',type=int,default=3);parser.add_argument('--limit',type=int,default=16);args=parser.parse_args()
 from svg_source_stroke_support_v2 import supports,may_overlap
 def line(key,points):
  return dict(id=key,type='shape',tag='path',matrix=[1,0,0,1,0,0],bbox=dict(x=min(x for x,y in points),y=min(y for x,y in points),w=max(x for x,y in points)-min(x for x,y in points),h=max(y for x,y in points)-min(y for x,y in points)),style=dict(fill='none',stroke='black',strokeWidth=1,linejoin='round'),sceneGeometry=dict(topology=dict(subpaths=[dict(operations=[dict(operation='moveTo',points=[points[0]]),*[dict(operation='lineTo',points=[p])for p in points[1:]],dict(operation='endPath',points=[])])])))
 a=line('a',[(0,0),(100,100)]);b=line('b',[(0,50),(40,90)]);c=line('c',[(0,100),(100,0)])
 text=dict(id='text',type='text',bbox=dict(x=80,y=80,w=10,h=10),rotationHandled=True,originalBoundingBox=dict(x=0,y=0,w=15,h=100),style=dict(fill='black',stroke='none'))
 controls=dict(disjoint_broad_boxes=not may_overlap(a,b,{}),true_crossing_retained=may_overlap(a,c,{}),rotated_text_keeps_original_paint_support=may_overlap(text,a,{}))
 assert all(controls.values()),controls
 run=R/'release/compiler_iterations/runs/svg_complex_background_rotation_cached_unseen_20261102_v9_mass'
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:failed=[json.loads(x[0])for x in db.execute("select result from samples where status='abandoned' order by seq")]
 targets=[r for r in failed if r.get('reason')=='source_layer_interleaving_needs_compound_paint_representation'][args.offset:args.offset+args.limit];assert targets
 cached={r['id']:r for r in map(json.loads,(R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea/admitted.jsonl').read_text().splitlines())}
 backend=S/'compiler_svg_scene_backend_v13.py';original=backend.read_bytes();source=original.decode().replace('from svg_source_edge_layers_v9 import repair','from svg_source_edge_layers_v10 import repair');assert source!=original.decode()
 module=dict(__name__='background_stroke_support_structural_development',__file__=str(backend));exec(compile(source,str(backend),'exec'),module)
 output=R/'conversion/background_stroke_support_structural_development_v1'/uuid.uuid4().hex;output.mkdir(parents=True);results=[]
 for prior in targets:
  started=time.monotonic();cached_row=cached[prior['id']];ref=cached_row['cached_DOM'];path=R/ref['file'] if not Path(ref['file']).is_absolute()else Path(ref['file']);assert hashlib.sha256(path.read_bytes()).hexdigest()==ref['sha256'];dom=json.loads(path.read_bytes())
  from PIL import Image
  size=Image.open(Path(cached_row['source_observation_work'])/'browser_source.png').size
  row=dict(id=prior['id'],prior_reason=prior['reason'],source_DOM=ref)
  try:
   xml,stats=module['build'](copy.deepcopy(dom),size);p=output/(prior['id']+'.xml');p.write_text(xml);row.update(structural_order_passed=True,xml_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_edge_layers=stats['source_edge_layers'])
  except Exception as error:row.update(structural_order_passed=False,reason=str(error)[:1800])
  row['elapsed_seconds']=time.monotonic()-started;results.append(row)
 assert backend.read_bytes()==original
 summary=dict(root=str(output),controls=controls,results=results,normal_conversion_calls=0,QA_calls=0,browser_recaptures=0,model_calls=0,qualification_claimed=False,running_validation_unchanged=True)
 (output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
