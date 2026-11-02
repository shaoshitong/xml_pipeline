from pathlib import Path
import ast,hashlib,json
import pyarrow.parquet as pq
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_development_20261102_v1';P=R/'clean/complexity_curation_20261102T054553Z_v1/published_v1/complex_conversion_targets.jsonl'
sha=lambda b:hashlib.sha256(b).hexdigest()
rows=[r for r in map(json.loads,P.read_text().splitlines()) if r['source'] in {'ChartMimic--ChartMimic','CSU-JPG--Chart2Code'} and r['features'].get('direct_plot_call_sites',0)>=8 and set(r['features'].get('direct_plot_methods',[]))<={'plot','fill_between','fill_betweenx'}];cache={};candidates=[]
def data(desc):
    path=R/desc['file']
    if desc['kind']=='clean_file':blob=path.read_bytes()
    else:
        key=(desc['file'],desc['column'])
        if key not in cache:cache[key]=pq.read_table(path,columns=[desc['column']])[desc['column']]
        value=cache[key][int(desc['row'])].as_py();blob=value.encode() if isinstance(value,str) else value.get('bytes') if isinstance(value,dict) else bytes(value)
    assert sha(blob)==desc['expected_sha256'];return blob
for r in sorted(rows,key=lambda r:r['id']):
    code=data(r['payloads']['code']);tree=ast.parse(code);imports=[];sizes=[];issues=[];assets=[];seed=False;random=False
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
        if isinstance(n,ast.ImportFrom):imports.append(n.module or '')
        if isinstance(n,ast.Attribute) and n.attr.startswith('__'):issues.append('dunder')
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else '<dynamic>'
            if name in {'exec','eval','compile','getattr','setattr','open','system','popen','__import__','<dynamic>'}:issues.append(name)
            if name in {'read_csv','read_excel','load','loadtxt','genfromtxt','imread'}:assets.append(name)
            if name in {'seed','default_rng','RandomState'}:seed=True
            if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Attribute) and n.func.value.attr=='random':random=True
            if name in {'linspace','logspace'}:
                v=n.args[2] if len(n.args)>=3 else next((k.value for k in n.keywords if k.arg=='num'),None)
                if isinstance(v,ast.Constant) and isinstance(v.value,int):sizes.append(v.value)
    if set(i.split('.')[0] for i in imports)-{'matplotlib','numpy','math','scipy'} or issues or assets or (random and not seed):continue
    if sizes and 200<=max(sizes)<=2000:candidates.append((r,code,max(sizes),seed,imports))
    if len(candidates)>=3:break
assert candidates,'no_safe_real_dense_plot_found'
r,code,n,seed,imports=candidates[0];case=D/'cases'/r['id'];case.mkdir(parents=True,exist_ok=True);image=data(r['payloads']['image']);(case/'source.py').write_bytes(code);(case/'original_reference.png').write_bytes(image)
audit={'id':r['id'],'development_stratum':'actual_dense_curves','source':r['source'],'source_code_sha256':sha(code),'source_image_sha256':sha(image),'payloads':r['payloads'],'imports':imports,'safe_selfcontained_source':True,'security_issues':[],'estimated_per_series_point_count':n,'explicit_seed_present':seed,'source_features':r['features'],'no_source_execution_yet':True}
(case/'input_audit.json').write_text(json.dumps(audit,indent=2)+'\n');(D/'dense_development_input.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
