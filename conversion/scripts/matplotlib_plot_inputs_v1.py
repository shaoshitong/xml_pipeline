"""Release-exact payload reads and conservative source-only security/domain audit."""
from pathlib import Path
import ast,collections,copy,hashlib,json
import pyarrow.parquet as pq
R=Path('/backup/shaoshitong/img2code_20261029')
sha=lambda b:hashlib.sha256(b).hexdigest()
def payload(desc):
    p=(R/desc['file']).resolve(strict=True)
    if not p.is_relative_to(R/'clean'):raise ValueError('input_outside_clean')
    if desc['kind']=='clean_file':blob=p.read_bytes()
    else:
        pf=pq.ParquetFile(p);row=int(desc['row']);offset=0
        for i in range(pf.num_row_groups):
            n=pf.metadata.row_group(i).num_rows
            if offset<=row<offset+n:value=pf.read_row_group(i,columns=[desc['column']],use_threads=False)[desc['column']][row-offset].as_py();break
            offset+=n
        else:raise ValueError('parquet_row_outside_file')
        blob=value.encode() if isinstance(value,str) else value.get('bytes') if isinstance(value,dict) else bytes(value)
    if sha(blob)!=desc['expected_sha256']:raise ValueError('release_expected_payload_hash_mismatch')
    return blob
ALLOWED={'numpy','matplotlib','seaborn','pandas','scipy','math','random','statistics','datetime','collections','itertools','PIL','warnings'}
DENIED={'exec','eval','compile','__import__','getattr','setattr','delattr','globals','locals','vars','open','input','system','popen','spawn','fork','load_library','urlopen','urlretrieve','read_html','memmap','fromfile','tofile'}
BAD_ATTRS={'os','sys','ctypes','subprocess','builtins','f_globals','f_builtins','gi_frame','tb_frame','func_globals','func_code','func_closure'}
FILE_CALLS={'load','loadtxt','genfromtxt','read_csv','read_excel','read_json','imread','load_dataset'}
class Constants(ast.NodeTransformer):
    def visit_Constant(self,node):return ast.copy_location(ast.Constant(value=type(node.value).__name__),node)
def audit(code):
    tree=ast.parse(code);issues=[];imports=[];calls=collections.Counter();assets=[];rng=[];seeds=[];unsupported_rng=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
        elif isinstance(n,ast.ImportFrom):imports.append(n.module or '')
        if isinstance(n,ast.ClassDef):issues.append('custom_class_requires_another_execution_profile')
        if isinstance(n,ast.Name) and (n.id in DENIED or n.id.startswith('__') and n.id not in {'__name__','__file__'}):issues.append('unsafe_name:'+n.id)
        if isinstance(n,ast.Attribute) and (n.attr.startswith('__') or n.attr in BAD_ATTRS):issues.append('unsafe_attribute:'+n.attr)
        if isinstance(n,ast.Call):
            name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else '<dynamic>'
            calls[name]+=1
            if name in DENIED or name=='<dynamic>':issues.append('unsafe_call:'+name)
            if name in FILE_CALLS:assets.append({'call':name,'line':n.lineno})
            full=ast.unparse(n.func)
            if 'random' in full or name in {'default_rng','RandomState','Generator','Random'}:rng.append({'call':full,'line':n.lineno})
            if name=='seed':seeds.append({'call':full,'constant_seed':n.args[0].value if n.args and isinstance(n.args[0],ast.Constant) else None})
            if name in {'RandomState','Generator','Random','PCG64','MT19937'}:unsupported_rng.append({'call':full,'line':n.lineno})
            if any(k.arg=='projection' and isinstance(k.value,ast.Constant) and k.value.value=='3d' for k in n.keywords):issues.append('3D_artist_requires_full_3D_data_contract')
        if isinstance(n,ast.Subscript) and isinstance(n.ctx,ast.Store) and isinstance(n.slice,ast.Constant) and n.slice.value=='text.usetex':issues.append('external_TeX_text_requires_another_execution_profile')
    for name in imports:
        if name.split('.')[0] not in ALLOWED:issues.append('unapproved_import:'+name)
    if assets:issues.append('file_asset_requires_explicit_verified_closure')
    if unsupported_rng:issues.append('independent_RNG_constructor_not_observed_by_current_capture')
    return {'safe_selfcontained_source':not issues,'security_issues':sorted(set(issues)),'imports':sorted(set(imports)),'call_counts':dict(calls),'file_asset_reads':assets,'RNG_source_calls':rng,'source_explicit_seed_calls':seeds,'normalized_AST_template':sha(ast.dump(Constants().visit(copy.deepcopy(tree)),include_attributes=False).encode()),'source_code_sha256':sha(code),'source_code_bytes':len(code)}
