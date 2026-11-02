import concurrent.futures,hashlib,json,sqlite3,sys
from native_worker import R,W,now
import tectonic_compile
from tex_missing_v2 import missing_files
tectonic_compile.missing_files=missing_files
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
IDS=['0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0029bf2032e526aa6fd09bbe5d8a324af2e677ae2652bef99909ee1b251330d7','040857fcfce2cae2347e1ab36d89c67e2b57a67f7f31a25067f956c72b2b559c','03a2e6ec94e66da721a1d3188e284fd2f40a35ddaa84bf6ff762d191c654623c']
def smoke(id):
    db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
    state,raw,inp,old_error=db.execute('select state,input_record,input_manifest,error from jobs where id=?',(id,)).fetchone();db.close()
    src=json.loads(raw);inp=json.loads(inp);data=(R/inp['source_code']).read_bytes();assert hashlib.sha256(data).hexdigest()==src['code_sha256'];assert not inp.get('panel_assets')
    folder=W/'tex_missing_v2_smoke'/id;folder.mkdir(parents=True,exist_ok=True);(folder/'source.tex').write_bytes(data)
    result={'id':id,'state_before':state,'source_code_sha256':src['code_sha256'],'old_error':old_error,'directory':str(folder.relative_to(R))}
    try:
        r,attempts=tectonic_compile.compile_case(folder);result.update(returncode=r.returncode,attempts=attempts,stderr_tail=r.stderr[-2200:]);assert r.returncode==0,r.stderr[-2200:]
        with pymupdf.open(folder/'source.pdf') as doc:
            result['pages']=[{'index':i,'text_chars':len(p.get_text()),'paths':len(p.get_drawings()),'images':len(p.get_images())} for i,p in enumerate(doc)]
            assert len(doc)>0 and all(p['text_chars'] or p['paths'] or p['images'] for p in result['pages'])
        result['pdf_sha256']=hashlib.sha256((folder/'source.pdf').read_bytes()).hexdigest();result['ok']=True
    except Exception as e:result.update(ok=False,error=str(e))
    result['source_unchanged']=hashlib.sha256((folder/'source.tex').read_bytes()).hexdigest()==src['code_sha256'];assert result['source_unchanged']
    (folder/'proof.json').write_text(json.dumps(result,indent=2)+'\n');return result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(smoke,IDS))
out={'at':now(),'results':results,'all_passed':all(r['ok'] for r in results),'database_mutated':False}
(W/'tex_missing_v2_smoke.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
