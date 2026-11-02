#!/usr/bin/env python3
"""Verify every canonical locator against its stored image/code content hashes."""
import argparse, collections, hashlib, importlib.util, json, time
from pathlib import Path
import pyarrow.parquet as pq

def sha(data):return hashlib.sha256(data).hexdigest()
def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def main(root):
    spec=importlib.util.spec_from_file_location('pair_curator',root/'scripts/curate_pairs.py')
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    result={'started_at':now(),'checks':'All canonical image/code bytes match declared SHA256 at their locators. No arbitrary dataset code executed.',
        'groups':{},'sources':{},'errors':0,'checked_pairs':0,'input_manifest_sha256':{}}
    error_path=root/'reports/content_audit_errors.jsonl';grouped=collections.defaultdict(list);standalone=[]
    for kind in ('clean','derived'):
        path=root/kind/'manifest.jsonl';data=path.read_bytes();result['input_manifest_sha256'][kind]=sha(data)
        result['groups'][kind]={'checked':0,'errors':0}
        for line in data.splitlines():
            if not line.strip():continue
            record=json.loads(line);record['_audit_kind']=kind
            if record.get('clean_file'):grouped[record['clean_file']].append(record)
            else:standalone.append(record)
    with error_path.open('w') as errors:
        def check(record,data,code,error=None):
            kind=record['_audit_kind'];source=record['source']
            try:
                if error:raise ValueError(error)
                if not data or sha(data)!=record['image_sha256']:raise ValueError('image bytes/hash mismatch')
                if code is None or sha(code.encode())!=record['code_sha256']:raise ValueError('code bytes/hash mismatch')
            except Exception as exc:
                result['errors']+=1;result['groups'][kind]['errors']+=1
                errors.write(json.dumps({'source':source,'kind':kind,'clean_file':record.get('clean_file'),
                    'clean_row':record.get('clean_row'),'source_manifest':record.get('source_manifest'),
                    'source_manifest_line':record.get('source_manifest_line'),'error':str(exc)[:300]})+'\n')
            result['checked_pairs']+=1;result['groups'][kind]['checked']+=1
            result['sources'].setdefault(source,{'checked':0})['checked']+=1
        for relative,records in sorted(grouped.items()):
            rows=collections.defaultdict(list)
            for record in records:rows[record['clean_row']].append(record)
            columns=sorted({r[k] for r in records for k in ('image_key','code_key')})
            offset=0
            try:
                pf=pq.ParquetFile(root/relative)
                for batch in pf.iter_batches(batch_size=64,columns=columns):
                    for i,row in enumerate(batch.to_pylist()):
                        for record in rows.pop(offset+i,[]):
                            try:
                                image=core.image_bytes(row[record['image_key']],root/'raw'/record['source'])
                                code=(core.code_value(row)[0] if record['code_key'] in ('messages','conversations','conversation')
                                    else core.text_content(row[record['code_key']]))
                                if record.get('profile'):code=core.unwrap_code(code)
                                check(record,image,code)
                            except Exception as exc:check(record,None,None,type(exc).__name__+': '+str(exc))
                    offset+=batch.num_rows
                for missing in rows.values():
                    for record in missing:check(record,None,None,'locator row missing')
            except Exception as exc:
                for remaining in rows.values():
                    for record in remaining:check(record,None,None,type(exc).__name__+': '+str(exc))
            print(json.dumps({'event':'content_file_checked','file':relative,'checked_pairs':result['checked_pairs'],'errors':result['errors']}),flush=True)
        for record in standalone:
            try:
                data=(root/(record.get('reference_image') or record['image_file'])).read_bytes()
                code=(root/record['code_file']).read_text();check(record,data,code)
            except Exception as exc:check(record,None,None,type(exc).__name__+': '+str(exc))
    for kind,digest in result['input_manifest_sha256'].items():
        if sha((root/kind/'manifest.jsonl').read_bytes())!=digest:
            result['errors']+=1;result.setdefault('manifest_changes_during_audit',[]).append(kind)
    result['finished_at']=now();result['ok']=result['errors']==0
    result['limitations']='Hash integrity and correct row association only; not exhaustive semantic or rendering equivalence.'
    target=root/'reports/content_audit.json';temporary=target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2));temporary.replace(target)
    print(json.dumps(result,ensure_ascii=False),flush=True);return int(not result['ok'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();raise SystemExit(main(a.root.resolve()))
