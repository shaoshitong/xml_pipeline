import hashlib,json,sqlite3
from native_worker import R,W,now
from tex_xcolor_compile import compile_source,pymupdf,tectonic_compile
from tex_xcolor_forwarding import plan
IDS=['03299a3c21789a81926f027324ec2c78cc9134ff3fc0e46e271f1699b3202c19','03ed1e3ef92b003d0ec6b59a7743a990630e7b4cc90b0b4814340ebe8fe1e05c','0441977260ede10df236c30cf94fb466264ac6871bbccc9cdf88cd93cdabe473']
base=W/'xcolor_smoke';base.mkdir(exist_ok=True);d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);results=[]
for id in IDS:
    raw,inp=d.execute('select input_record,input_manifest from jobs where id=?',(id,)).fetchone();src=json.loads(raw);inp=json.loads(inp);data=(R/inp['source_code']).read_bytes();assert hashlib.sha256(data).hexdigest()==src['code_sha256'];assert not inp.get('panel_assets')
    try:
        proof=compile_source(base/id,data);result={'id':id,'ok':True,'proof':proof}
        # Compare against the same original with only the identical option command prepended.
        # This verifies that the wrapper does not change jobname, paths, text or rendered pixels.
        golden=base/id/'prefix_equivalence';golden.mkdir(exist_ok=True);prefix=proof['wrapper'].split('\\input')[0]
        (golden/'source.tex').write_bytes(prefix.encode()+data);r,_=tectonic_compile.compile_case(golden);assert r.returncode==0,r.stderr[-1500:]
        with pymupdf.open(base/id/'source.pdf') as a,pymupdf.open(golden/'source.pdf') as b:
            assert len(a)==len(b)
            for x,y in zip(a,b):
                assert x.rect==y.rect and x.get_text()==y.get_text()
                assert x.get_pixmap().samples==y.get_pixmap().samples
        result['wrapper_vs_prefix_all_pages_pixel_identical']=True
    except Exception as e:result={'id':id,'ok':False,'error':str(e)}
    results.append(result);print(json.dumps({'case':id,'ok':result['ok']}),flush=True)
out={'at':now(),'cases':results,'all_passed':all(x['ok'] for x in results),'production_database_mutated':False};(W/'xcolor_smoke_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
