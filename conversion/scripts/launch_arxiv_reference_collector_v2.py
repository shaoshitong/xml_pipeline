from pathlib import Path
import datetime,hashlib,json,os,sqlite3,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';D=R/'clean/arxiv_research_figures_v1/original_PDF_reference_audit_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def birth(pid):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return None
 a=p.read_text().split(') ',1)[1].split();return a[19] if a[0]!='Z' else None
receipt=D/'collector_launch.json'
if receipt.exists():
 old=json.loads(receipt.read_text())
 if birth(old['pid'])==old['birth_ticks']:print(json.dumps({'already_running':True,**old}));sys.exit(0)
control=json.loads((D/'controls_latest.json').read_text());proof=json.loads((R/control['proof']).read_text())
assert sha(R/control['proof'])==control['proof_sha256'] and proof['positive_passed']==3 and proof['actual_negative_rejected']==3 and proof['false_accepts']==0
for path,digest in proof['pins'].items():assert sha(R/path)==digest,'Validated audit code changed'
files=[S/'arxiv_reference_case_v2.py',S/'arxiv_reference_collector_v2.py',S/'arxiv_native_reference_audit_v1.py',
 S/'arxiv_native_reference_audit_v2.py',S/'arxiv_bulk_official_xml_png_v1.py',S/'auto_quality_common.py',
 S/'arxiv_sourceonly_bulk_200_v1_1.py',R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war']
cfg={'schema':'author_native_original_PDF_fidelity_filter_v2','pins':{str(p.relative_to(R)):sha(p) for p in files},
 'validated_controls':control,'registration':'Unique original asset pixels/opaque vector-fill identity plus independent geometry; no pixel-score fitting.',
 'raster_thresholds':{'global_SSIM':.90,'foreground_tile_p10':.72,'foreground_precision_recall':.90,'local_text_line':.55},
 'case_timeout_seconds':180,'discovery_interval_seconds':60,'source_native_authority_binding_required':True,
 'normal_generations':0,'official_PDF_import_calls':0,'external_models':0,'strict_provider_reference_full8_profile':False}
policy=D/'collector_policy.json'
if policy.exists():assert json.loads(policy.read_text())==cfg
else:
 with policy.open('x') as f:json.dump(cfg,f,ensure_ascii=True,indent=2)
# A single online status index avoids repeatedly reading every large source record.
for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
 with sqlite3.connect(R/'clean/arxiv_research_figures_v1'/name/'once.sqlite',timeout=30) as db:
  db.execute('create index if not exists native_pdf_status_idx on pdfs(status)');db.commit()
command=['/home/shaoshitong/anaconda3/bin/python','-u',str(S/'arxiv_reference_collector_v2.py')]
with (D/'collector.log').open('ab') as log:
 p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
   env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env')),start_new_session=True)
row={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':p.pid,'birth_ticks':birth(p.pid),
 'command':command,'policy_sha256':sha(policy),'controls':control,'summary':str(D/'collector_summary.json'),
 'manifest':str(D/'paired_registered_original_PDF.jsonl'),'case_timeout_seconds':180,'external_models':0,'normal_generations':0}
q=receipt.with_name('collector_launch.tmp.json');q.write_text(json.dumps(row,indent=2)+'\n');os.replace(q,receipt);print(json.dumps(row))
