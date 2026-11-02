"""Verify pinned code and queue an autonomous scan after the current 200 papers."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
D=R/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2'
OLD=R/'clean/arxiv_research_figures_v1/new_bulk_200_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
D.mkdir(parents=True,exist_ok=True)
receipt=D/'launch.json'
if receipt.exists():
    prior=json.loads(receipt.read_text());stat=Path('/proc',str(prior['pid']),'stat')
    parts=stat.read_text().split(') ',1)[1].split() if stat.exists() else []
    if parts and parts[0]!='Z' and parts[19]==prior['birth_ticks']:
        print(json.dumps({'already_running':True,'receipt':prior}));sys.exit(0)
pins={str(p.relative_to(R)):sha(p) for p in [S/'arxiv_sourceonly_expansion_v2.py',S/'arxiv_sourceonly_bulk_200_v1_1.py',
      S/'arxiv_bulk_official_xml_png_v1.py',S/'arxiv_source_pilot.py',
      S/'arxiv_sourceonly_expansion_launch_v2.py',OLD/'procedure_selftest/success.json',
      R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/official_pdf_functions.js',
      R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/pako.min.js',
      R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/node_adapter.cjs',
      R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war']}
freeze=D/'freeze.json'
if freeze.exists():
    cfg=json.loads(freeze.read_text());assert cfg['pins']==pins,'Expansion program changed; preserve all claims.'
else:
    cfg={'schema':'arxiv_AI_2023_present_native_source_scan_v2','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'until_date_UTC':datetime.datetime.now(datetime.timezone.utc).date().isoformat(),'since_year':2023,
         'categories':['cs.CV','cs.LG','cs.AI','cs.CL'],'artificial_paper_limit':None,'API_page_size':200,
         'minimum_request_interval_seconds':3.2,'new_source_download_budget_bytes':512*1024**3,
         'source_per_paper_limit_bytes':128*1024**2,'minimum_free_disk_bytes':250*1024**3,
         'old_200_once_ledger_preserved':True,'official_drawio_PDF_import_only':True,'custom_PDF_geometry_converter':False,
         'external_model_calls':0,'whole_paper_PDF_endpoint_requests':0,'all_data_on_HKUST':True,'pins':pins}
    with freeze.open('x') as f:json.dump(cfg,f,ensure_ascii=False,indent=2)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env'))
command=['/home/shaoshitong/anaconda3/bin/python',str(S/'arxiv_sourceonly_expansion_v2.py')]
tested=subprocess.run(command+['--selftest'],capture_output=True,text=True,env=env,timeout=60)
assert tested.returncode==0,tested.stderr[-3000:]
proof=json.loads(tested.stdout);assert proof['success']
if not (D/'selftest.json').exists():
    with (D/'selftest.json').open('x') as f:json.dump(proof,f,indent=2)
with (D/'program.log').open('ab') as log:
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
birth=Path('/proc',str(proc.pid),'stat').read_text().split(') ',1)[1].split()[19]
report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':proc.pid,'birth_ticks':birth,
        'command':command,'freeze_sha256':sha(freeze),'scope':'All paginated 2023-present AI date partitions; existing200 finish first',
        'phase':'autonomous_handoff_queued','summary':str(D/'summary.json'),'program_log':str(D/'program.log'),
        'selftest':proof,'resume_command':['/home/shaoshitong/anaconda3/bin/python',str(S/'arxiv_sourceonly_expansion_launch_v2.py')],
        'external_model_calls':0}
with (D/'launches.jsonl').open('a') as f:f.write(json.dumps(report)+'\n')
q=D/'launch.tmp.json';q.write_text(json.dumps(report,indent=2));os.replace(q,receipt)
print(json.dumps(report))
