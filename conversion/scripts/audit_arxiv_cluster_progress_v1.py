"""Small real-state evidence snapshots; no imports, requests, retries or conversions."""
from pathlib import Path
import datetime,hashlib,json,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'cluster_direct_v1'
def birth(pid):
    try:
        x=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return x[19] if x[0]!='Z' else None
    except FileNotFoundError:return None
progress=json.loads((D/'progress.json').read_text())
launch=json.loads((D/'broker_launch.json').read_text());assert birth(launch['pid'])==launch['birth_ticks']
with sqlite3.connect((D/'queue.sqlite').as_uri()+'?mode=ro',uri=True) as c:
    jobs=[dict(node=n,status=s,count=k) for n,s,k in c.execute('select node,status,count(*) from jobs group by node,status')]
    errors=[dict(node=n,reason=e,count=k) for n,e,k in c.execute("select node,error,count(*) from jobs where error is not null group by node,error")]
    claims=[r[0] for r in c.execute('select id from pdf_claims')]
with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as c:
    statuses={};technical=[];records=[]
    for ident in claims:
        row=c.execute('select status,record from pdfs where id=?',(ident,)).fetchone();assert row
        statuses[row[0]]=statuses.get(row[0],0)+1
        if row[0]=='technical_failure_review':technical.append(json.loads(row[1]))
        if row[0]=='qualified_native_xml_png_pair':records.append(json.loads(row[1]))
    papers=dict(c.execute("select status,count(*) from papers where json_extract(record,'$.metadata.discovery')='official_OAI_PMH_arXivRaw' group by status"))
current=json.loads((P/'goal500_progress_v1/current.json').read_text())
row=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),progress=progress,authoritative_jobs=jobs,network_pending_errors=errors,cluster_new_PDF_states=statuses,cluster_technical_failures=technical,cluster_preliminary_native_pairs=records,official_OAI_paper_states=papers,accepted_new_complex=current['accepted_new_pairs']['rows'],unified_rows=current['unified_pairs']['rows'],metadata_status=json.loads((P/'oai_direct_pipeline_v1/status.json').read_text()),broker_alive_verified=True)
out=D/'observations.jsonl'
with out.open('a') as f:f.write(json.dumps(row,ensure_ascii=True)+'\n')
print(json.dumps(row,ensure_ascii=True))
