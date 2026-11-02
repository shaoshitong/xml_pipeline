"""Read only release-exact plot inputs; static audit before sandbox execution."""
from pathlib import Path
import ast,collections,hashlib,json
import pyarrow.parquet as pq
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_development_20261102_v1'
P=R/'clean/complexity_curation_20261102T054553Z_v1/published_v1/complex_conversion_targets.jsonl'
IDS={'0057becd24a3714551ad9b40b5ed22a35b724022e0d531d0eea6a48b1da7c352':'multiplot','004cce7f61366bed1203555250b70bce358fefb9b3f04ef2dae3357ad12c3c06':'mixed_bar_line','00470c12cf48d87d7544160aa4adf794394bad4beb7f9366ec054527bcfd1d60':'dense_lines_and_bands'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def payload(desc):
    p=(R/desc['file']).resolve(strict=True);assert p.is_relative_to(R/'clean')
    if desc['kind']=='clean_file':data=p.read_bytes()
    else:
        pf=pq.ParquetFile(p);row=int(desc['row']);start=0
        for i in range(pf.num_row_groups):
            n=pf.metadata.row_group(i).num_rows
            if start<=row<start+n:v=pf.read_row_group(i,columns=[desc['column']],use_threads=False)[desc['column']][row-start].as_py();break
            start+=n
        if isinstance(v,dict):v=v.get('bytes')
        data=v.encode() if isinstance(v,str) else bytes(v)
    assert sha(data)==desc['expected_sha256'],'release_exact_hash_mismatch';return data
allowed={'numpy','matplotlib','seaborn','pandas','scipy','math','random','statistics','datetime','collections','itertools','PIL'}
bad_calls={'exec','eval','compile','__import__','getattr','setattr','delattr','globals','locals','vars','open','input','system','popen','spawn','fork','load_library','urlopen','urlretrieve','read_html'}
file_calls={'load','loadtxt','genfromtxt','read_csv','read_excel','read_json','imread','open'}
D.mkdir(exist_ok=True);rows=[]
for raw in P.open():
    r=json.loads(raw)
    if r['id'] not in IDS:continue
    case=D/'cases'/r['id'];case.mkdir(parents=True,exist_ok=True);code=payload(r['payloads']['code']);image=payload(r['payloads']['image']);tree=ast.parse(code);imports=[];calls=collections.Counter();assets=[];issues=[];seeds=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
        elif isinstance(n,ast.ImportFrom):imports.append(n.module or '')
        if isinstance(n,ast.Attribute) and (n.attr.startswith('__') or n.attr in {'os','sys','ctypes','subprocess','builtins'}):issues.append('unsafe_attribute:'+n.attr)
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else '<dynamic>'
            calls[name]+=1
            if name in bad_calls or name=='<dynamic>':issues.append('unsafe_call:'+name)
            if name in file_calls:assets.append({'call':name,'line':n.lineno,'argument':n.args[0].value if n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) else '<dynamic>'})
            if name in {'seed','default_rng','RandomState'}:seeds.append({'name':name,'line':n.lineno,'constant_seed':n.args[0].value if n.args and isinstance(n.args[0],ast.Constant) else None})
    for name in imports:
        if name.split('.')[0] not in allowed:issues.append('unapproved_import:'+name)
    if assets:issues.append('file_asset_requires_explicit_verified_closure')
    (case/'source.py').write_bytes(code);(case/'original_reference.png').write_bytes(image)
    report={'id':r['id'],'development_stratum':IDS[r['id']],'source':r['source'],'source_bytes':len(code),'source_code_sha256':sha(code),'source_image_sha256':sha(image),'payloads':r['payloads'],'imports':sorted(set(imports)),'call_counts':dict(calls),'file_asset_reads':assets,'explicit_seed_calls':seeds,'security_issues':sorted(set(issues)),'safe_selfcontained_source':not issues,'source_features':r['features'],'no_source_execution_yet':True}
    (case/'input_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');rows.append(report)
(D/'development_inputs.json').write_text(json.dumps({'schema':'matplotlib_plot_development_inputs_v1','input_manifest_sha256':sha(P.read_bytes()),'cases':rows,'models':0,'source_exported_to_local':False},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'root':str(D),'cases':[{k:r[k] for k in ['id','development_stratum','imports','source_bytes','file_asset_reads','explicit_seed_calls','security_issues','safe_selfcontained_source']} for r in rows]},ensure_ascii=False))
