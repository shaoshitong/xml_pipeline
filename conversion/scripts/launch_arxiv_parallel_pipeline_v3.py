"""Idempotent task launcher, pinned code, existing once ledgers, no AI watchdog."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/transport_performance_v3';S=R/'conversion/scripts'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def birth(pid):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return None
 s=p.read_text().split(') ',1)[1].split();return s[19] if s[0]!='Z' else None
D.mkdir(exist_ok=True);receipt=D/'launch.json'
if receipt.exists():
 old=json.loads(receipt.read_text())
 if birth(old['pid'])==old['birth_ticks']:print(json.dumps({'already_running':True,**old}));sys.exit(0)
benchmark=json.loads((R/'conversion/arxiv_performance_audit_20261102_v1/direct_VPS_HKUST3_thread_scaling_benchmark.json').read_text())
assert len(benchmark)==3 and all(x['all_hashes_match'] for x in benchmark)
assert benchmark[-1]['aggregate_MiB_s']>=1,'Actual4lane relay not verified fast'
test=json.loads((R/'clean/arxiv_research_figures_v1/new_bulk_200_v1/procedure_selftest/success.json').read_text());assert test['success']
paths=[S/'arxiv_parallel_pipeline_v3.py',S/'arxiv_sourceonly_bulk_200_v1_1.py',S/'arxiv_bulk_official_xml_png_v1.py',
 S/'arxiv_sourceonly_expansion_v2.py',S/'arxiv_source_pilot.py',
 R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/official_pdf_functions.js',
 R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/pako.min.js',
 R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/node_adapter.cjs']
pins={str(p.relative_to(R)):sha(p) for p in paths};pinfile=D/'procedure_pins.json'
if pinfile.exists():assert json.loads(pinfile.read_text())==pins,'frozen program changed'
else:
 with pinfile.open('x') as f:json.dump(pins,f,indent=2)
cfg={'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,'download_workers':4,'native_import_workers':4,
 'fulltext_request_starts_per_second_max':3,'legacy_metadata_API_minimum_interval_seconds':3.2,
 'all_old_PDF_once_claims_preserved':True,'source_partial_range_overlap_bytes':65536,
 'performance_reports':['initial_200.performance.json','recent_AI.performance.json'],
 'external_models':0,'whole_figure_embedding':False,'program_pins_sha256':sha(pinfile)}
if not (D/'configuration.json').exists():
 with (D/'configuration.json').open('x') as f:json.dump(cfg,f,indent=2)
command=['/home/shaoshitong/anaconda3/bin/python','-u',str(S/'arxiv_parallel_pipeline_v3.py')]
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env'))
with (D/'program.log').open('ab') as log:
 p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
out={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':p.pid,'birth_ticks':birth(p.pid),
 'command':command,'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,'download_workers':4,'native_import_workers':4,
 'configuration':str(D/'configuration.json'),'pins_sha256':sha(pinfile),'program_log':str(D/'program.log'),
 'resume_command':['/home/shaoshitong/anaconda3/bin/python',str(S/'launch_arxiv_parallel_pipeline_v3.py')],'external_model_calls':0}
with (D/'launches.jsonl').open('a') as f:f.write(json.dumps(out)+'\n')
q=D/'launch.tmp.json';q.write_text(json.dumps(out,indent=2));os.replace(q,receipt);print(json.dumps(out))
