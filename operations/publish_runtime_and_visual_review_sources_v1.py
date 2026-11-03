"""Back up bounded raster diagnostics, actual visual decisions and runtime receipts."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
W=Path(__file__).resolve().parents[2];repo=W/'work/xml_pipeline';O=W/'outputs';ops=repo/'operations'
names=['diagnose_datikz_pdf_svg_raster_v1.py','diagnose_datikz_pdf_svg_raster_v2.py','probe_datikz_source_stroke_adjust_v1.py']
code="from pathlib import Path\nimport json,hashlib\nS=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')\nresult=[]\nfor name in "+repr(names)+":\n p=S/name;b=p.read_bytes();result.append(dict(file='conversion/scripts/'+name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns))\nprint(json.dumps(result))"
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,check=True,timeout=30);remote=json.loads(r.stdout)
for entry,name in zip(remote,names):
 p=W/'work/catalog_refresh'/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];target=repo/entry['file']
 if target.exists():assert target.read_bytes()==p.read_bytes()
 else:shutil.copyfile(p,target)
files=['datikz-raster-diagnostic-import-failure-v1.json','datikz-pdf-svg-raster-diagnosis-v2.json','datikz-source-stroke-adjust-probe-v1.json','resolved-geometry-mass-value-review4.json','resolved-geometry-mass-decisions4.json','resolved-geometry-mass-publication4.json','curated-complex-research-delivery-v2.json','current-batch-runtime-progress1.json','current-batch-runtime-progress2.json','CURATED_RESEARCH_DELIVERY.md']
for name in files:
 assert (O/name).stat().st_size>0;shutil.copyfile(O/name,ops/name)
for name in ['snapshot_current_batch_runtime_v1.py',Path(__file__).name]:shutil.copyfile(W/'work/takeover'/name,ops/name)
def load(name):return json.loads((O/name).read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat();publication=load('resolved-geometry-mass-publication4.json');progress=load('current-batch-runtime-progress2.json');delivery=load('curated-complex-research-delivery-v2.json')
diagnostic=dict(saved_source_only=True,new_normal_calls=0,new_QA_calls=0,canonical_reference_unchanged=True,baseline_SSIM=0.8893715647115513,required_SSIM=.9,nontext_MSE_fraction=.6222141952768993,crispEdges_probe_SSIM=.8792336784363254,probe_not_adopted=True,remaining='Source PDF/SVG raster mismatch; diagnostic CSS crispEdges worsens fidelity. Preserve unqualified source and native candidate; defer further experiments while fixed bulk runs finish.',cached_candidate_comparison=dict(status='not_compared',reason='unregistered_reference_canvas_difference',no_crop_or_fit_applied=True))
for name in ['CURRENT_HANDOFF.json','CURRENT_RELEASE.json']:
 p=ops/name;x=json.loads(p.read_text());x.update(at_utc=now,strict_main_rows=publication['publication']['main']['rows'],authoritative_main=publication['publication']['main'],curated_delivery=delivery,latest_actual_PNG_publication=publication,latest_runtime_progress=progress,review_registry=progress['review_registry'],pending_reviews=progress['review_registry'].get('pending',0),datikz_saved_source_raster_diagnostic=diagnostic,goal_complete=False)
 x['next_step']='Prioritize completion and actual-result publication of the existing v11 mass, approved disjoint v24 mass and automatic parent v12 catchup. Do not expand diagnostics, rerun normals, restart active programs, alter QA thresholds or network routing. Review only new qualified PNG increments, refresh graded delivery and final whole-goal audit after all applicable cases are terminal. Current curated snapshot includes 1034 strict diagram/poster pairs, 92 complex charts and 262 arXiv pairs with separate reference grades.'
 p.write_text(json.dumps(x,indent=2)+'\n')
for name in ['SOURCE_MANIFEST.json','REMOTE_SOURCE_MANIFEST.json']:
 p=repo/name;m=json.loads(p.read_text());entries={r['file']:r for r in m['files']};entries.update({r['file']:r for r in remote})
 if name=='SOURCE_MANIFEST.json':
  for f in ops.rglob('*'):
   if f.is_file():b=f.read_bytes();entries[str(f.relative_to(repo))]=dict(file=str(f.relative_to(repo)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=f.stat().st_mtime_ns)
 m.update(at_utc=now,files=list(entries.values()));p.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(remote_source_files_verified=len(remote),strict_main=publication['publication']['main']['rows'],curated_delivery=delivery['unique_code_RGBA_pairs'],goal_complete=False)))
