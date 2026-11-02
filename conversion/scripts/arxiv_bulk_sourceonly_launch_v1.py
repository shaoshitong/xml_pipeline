"""Idempotent launch/resume of the frozen200-paper source-only procedure."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/new_bulk_200_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=D/'launch.json'
if receipt.exists():
    prior=json.loads(receipt.read_text());p=Path('/proc',str(prior['pid']));parts=p.joinpath('stat').read_text().split(') ',1)[1].split() if p.exists() else []
    if parts and parts[0]!='Z' and parts[19]==prior['birth_ticks']:
        print(json.dumps({'already_running':True,'receipt':prior}));sys.exit(0)
test=json.loads((D/'procedure_selftest/success.json').read_text());assert test['success'] and test['official_render_edit']['edit_probe']['restored_actual_PNG_exact']
paths=['conversion/scripts/arxiv_sourceonly_bulk_200_v1.py','conversion/scripts/arxiv_bulk_official_xml_png_v1.py','conversion/scripts/arxiv_bulk_procedure_selftest_v1.py','clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/official_pdf_functions.js','clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/pako.min.js','clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer/node_adapter.cjs','evaluation/assets/drawio-runtime-v32.6.1/draw.war']
pins={'schema':'frozen_sourceonly_bulk_procedure_pins_v1','files_sha256':{p:sha(R/p) for p in paths},'papers_sha256':sha(D/'papers.jsonl'),'selftest_success_sha256':sha(D/'procedure_selftest/success.json')}
pinfile=D/'procedure_pins.json'
if pinfile.exists():assert json.loads(pinfile.read_text())==pins,'Frozen procedure changed; do not reset source attempts.'
else:
    with pinfile.open('x') as f:json.dump(pins,f,indent=2);f.write('\n')
command=['/home/shaoshitong/anaconda3/bin/python','-u',str(R/'conversion/scripts/arxiv_sourceonly_bulk_200_v1.py')]
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
with (D/'program.log').open('ab') as log:process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
birth=Path('/proc',str(process.pid),'stat').read_text().split(') ',1)[1].split()[19]
r={'schema':'sourceonly_bulk_launch_v1','started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':process.pid,'birth_ticks':birth,'command':command,'pins_sha256':sha(pinfile),'frozen_papers':200,'scope':'Source packages only, no whole-paper PDF downloads; successful original author XML + actual official PNG pairs get their own manifest.','resume_command':['/home/shaoshitong/anaconda3/bin/python',str(R/'conversion/scripts/arxiv_bulk_sourceonly_launch_v1.py')],'summary_file':str(D/'summary.json'),'log_file':str(D/'program.log'),'events_file':str(D/'events.jsonl'),'once_ledger':str(D/'once.sqlite'),'model_calls':0,'custom_PDF_geometry_converter':False}
with (D/'launches.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
q=D/'launch.tmp.json';q.write_text(json.dumps(r,indent=2)+'\n');os.replace(q,receipt);print(json.dumps(r))
