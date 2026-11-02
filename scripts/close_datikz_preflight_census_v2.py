"""Publish verified source-readiness evidence; never label it native QA success."""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,os,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p),bytes=p.stat().st_size)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run.resolve();assert run.is_relative_to(R/'conversion')
 summary=json.loads((run/'summary.json').read_bytes());assert summary['finished']and summary['combined_total']==39
 targets=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/priority_datikz_targets39_v1.json';originals={r['id']:r for r in json.loads(targets.read_bytes())};rows=list(map(json.loads,(run/'combined_results.jsonl').read_text().splitlines()));assert len(rows)==39 and{r['id']for r in rows}==set(originals)
 reviewed=[];states=collections.Counter();baseline_count=0
 for row in rows:
  ref=row['execution_report'];p=R/ref['file'];assert sha(p)==ref['sha256'];execution=json.loads(p.read_bytes());directory=p.parent;source=directory/'baseline/original_source.tex';assert sha(source)==originals[row['id']]['code_sha256_manifest']==row['original_code_sha256']
  for name,digest in execution['configuration']['pins'].items():assert sha(Path(name))==digest
  runs=execution.get('runs',{});baseline=runs.get('baseline',{}).get('returncode')==0;baseline_count+=baseline
  state=row['status'];proof={}
  if state=='preflight_error'and execution.get('error')=='source_requires_single_unrotated_page':
   state='source_single_page_profile_unsupported';proof=dict(engine_error=execution['error'],baseline_PDF=asset(directory/'baseline/source.pdf'),instrumented_PDF=asset(directory/'instrumented/source.pdf'))
  if state=='source_compilation_failed':state='instrumentation_hook_compilation_failed'if baseline else'source_baseline_compilation_failed'
  elif state=='preflight_error'and execution.get('error')=='instrumentation_changed_actual_Poppler_PDF_pixels':
   from PIL import Image,ImageChops
   a=directory/'baseline/actual_Poppler100dpi/source.png';b=directory/'instrumented/actual_Poppler100dpi/source.png';left=Image.open(a).convert('RGB');right=Image.open(b).convert('RGB');assert left.size!=right.size or ImageChops.difference(left,right).getbbox()is not None
   state='instrumentation_changed_source_pixels';proof=dict(baseline_PNG=asset(a),instrumented_PNG=asset(b),baseline_canvas=list(left.size),instrumented_canvas=list(right.size),pixel_identical=False)
  states[state]+=1
  reviewed.append({**row,'readiness_status':state,'baseline_original_source_compiled':baseline,'source_bytes_hash_verified':True,'original_source_selection':originals[row['id']],'instrumentation_pixel_difference_proof':proof,'native_pair_qualified':False})
 pilot=R/'conversion/priority_datikz_native_pilot_v1/bdda92b0e0ae42058f682bdb55efa270/summary.json';native=json.loads(pilot.read_bytes());assert native['finished']and native['normal_calls']==3
 for row in native['results']:
  claim=R/row['claim']['file'];assert sha(claim)==row['claim']['sha256'];assert row['normal_calls']==1 and row['canonical_unchanged']
 root=R/'clean/priority_datikz_source_readiness_v1';root.mkdir(exist_ok=True);out=root/uuid.uuid4().hex;out.mkdir();pairs=out/'source_readiness.jsonl';pairs.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in reviewed))
 result=dict(schema='DaTikZ_complex_39_source_readiness_not_native_qualification_v1',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(out),targets=asset(targets),input_summary=asset(run/'summary.json'),source_readiness=asset(pairs),producer=asset(Path(__file__)),selected_sources=39,original_source_hashes_verified=39,baseline_original_sources_compiled=baseline_count,readiness_counts=dict(states),native_development=asset(pilot),native_normal_calls=3,native_qualified=sum(bool(r.get('quality_ok'))for r in native['results']),native_failures=[dict(raw_id=r['raw_id'],reason=r.get('reason'),detail=r.get('detail'))for r in native['results']if not r.get('quality_ok')],provider_original_PNG_fidelity_claimed=False,no_whole_image_wrappers=True,model_calls=0,goal_complete=False)
 (out/'summary.json').write_text(json.dumps(result,indent=2));pointer=dict(summary=asset(out/'summary.json'),source_readiness=asset(pairs),native_pairs_qualified=result['native_qualified'],goal_complete=False);tmp=root/'current.tmp';tmp.write_text(json.dumps(pointer,indent=2));os.replace(tmp,root/'current.json')
 for p in out.iterdir():p.chmod(0o444)
 print(json.dumps(result),flush=True)
if __name__=='__main__':main()
