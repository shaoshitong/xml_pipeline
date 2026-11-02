from pathlib import Path
import argparse,json,sqlite3,sys,time,traceback
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
 p=argparse.ArgumentParser();p.add_argument('--id',required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);out=dict(id=a.id,normal_calls=0,QA_calls=0);t=time.monotonic()
 try:
  import compiler_svg_scene_frontend_v14 as f
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as d:d.row_factory=sqlite3.Row;job=dict(d.execute('select*from jobs where id=?',(a.id,)).fetchone())
  result=f.prepare_source(job);dom=result['capture']['dom'];contexts=dom['sceneMetadata']['useContexts'];proofs={k:v.get('actual_source_use_replacement_proof')for k,v in contexts.items()if v.get('actual_source_use_replacement_proof')};out.update(ok=result['ok']and any(v.get('ok')for v in proofs.values()),source_work=str(result['work']),source_pixel_preserved=result['sourceproof']['source_dom_extraction_preserved_all_pixels'],use_contexts=len(contexts),fresh_actual_UA_proofs=proofs,objects=len(dom['objects']))
 except Exception as e:out.update(ok=False,error=str(e),traceback=traceback.format_exc())
 out['elapsed_seconds']=time.monotonic()-t;(a.work/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items()if k!='fresh_actual_UA_proofs'}),flush=True)
if __name__=='__main__':main()
