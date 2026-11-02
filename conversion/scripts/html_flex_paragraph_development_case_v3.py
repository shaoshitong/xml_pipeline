"""One declared development generation per source core, never publication."""
from pathlib import Path
import argparse, datetime, hashlib, json, sqlite3, sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import html_source_flex_paragraph_frontend_v3 as frontend
import html_paragraph_source_contract_v9 as original
sha=lambda b:hashlib.sha256(b).hexdigest()
DEV_IDS={'b141e36589e819a6a1197679dc1f3970fcae91a3068fb5a80edfd998a85c11b7','1a43171dec56f6e9b5016b7f5d63ec320fd872f0b7096c6e5c45a61cde8474f9','92d8c4afd3a0edd7f166b0584448c0e8b42610fb7c49ff2d355ce8d42daa2a7f'}
DEV_IDS.add('002937254103449d702e89c8cf7f773e01110de0e74c96e66c6fab75ff18166a')  # Frozen prior-positive regression only.

DEV_IDS={'002937254103449d702e89c8cf7f773e01110de0e74c96e66c6fab75ff18166a','50a8c0d1677fe48820a5dfaad4ce86ad0f4e43fce7a83cfb13257103b7f7f408','bcb87b34f0057064b8c20f9dc50e87f05f90b9320462e29d691863c9948a5cc6'}
def run(ident):
    assert ident in DEV_IDS
    configuration=frontend.configuration();key=sha(json.dumps(configuration,sort_keys=True).encode())
    d=R/'clean/html_flex_paragraph_development_v3'/key/ident;d.mkdir(parents=True,exist_ok=True)
    claim=d/'normal_once_claim.json'
    with claim.open('x') as f:json.dump({'id':ident,'configuration':configuration,'core_key':key,'development_only':True,'claimed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'normal_generation_calls':1},f,sort_keys=True)
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30) as db:job=db.execute('select * from jobs where id=?',(ident,)).fetchone()
    seed,_=original.original(None,job)
    work=W/'html_source_flex_paragraph_frontend_v3/development'/key/ident
    result=frontend.convert(seed,job,work)
    assert frontend.configuration()==configuration,'prototype_core_changed_during_case'
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30) as db:assert db.execute('select * from jobs where id=?',(ident,)).fetchone()==job
    report={'id':ident,'core_key':key,'generation_ok':result.get('ok',False),'reason':result.get('reason'),'error_type':result.get('error_type'),'candidate_record_file':result.get('record_file'),'development_only':True,'qualification_claimed':False,'canonical_unchanged':True,'configuration_unchanged':True,'normal_generation_calls':1,'model_calls':0,'work':str(work),'performance':result.get('performance')}
    if result.get('ok'):
        row=result['record'];meta=row['html_source_paragraph_v9'];report.update(code_file=row['code_file'],image_file=row['image_file'],code_sha256=row['code_sha256'],image_sha256=row['image_sha256'],source_groups=meta['source_groups'],source_text_objects=meta['source_text_objects'],source_native_exact_ink=meta['all_SOURCE_native_text_ink'],font_proof=meta['font_proof'])
    with (d/'result.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ['font_proof','source_native_exact_ink']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('id');x=a.parse_args();run(x.id)
