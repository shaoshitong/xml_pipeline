from pathlib import Path
import collections,hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';P=R/'clean/complexity_curation_20261102T054553Z_v1/published_v1/complex_conversion_targets.jsonl';sys.path.insert(0,str(R/'conversion/scripts'))
from matplotlib_plot_inputs_v1 import payload,audit,sha
SEED='HKUST-Matplotlib-complex-unseen-20261102-v1-public-seed-20261102'
EXCLUDED={'0057becd24a3714551ad9b40b5ed22a35b724022e0d531d0eea6a48b1da7c352','004cce7f61366bed1203555250b70bce358fefb9b3f04ef2dae3357ad12c3c06','00470c12cf48d87d7544160aa4adf794394bad4beb7f9366ec054527bcfd1d60','2f1586fb57bc6ecf8568d1a53cb2cad77a52b8cdc125b69a27fe4a5709734ecb'}
def stratum(r):
    f=r['features'];methods=set(f.get('direct_plot_methods',[]))
    if f.get('constant_subplot_axes_lower_bound',0)>=4:return 'multi_axes'
    if {'bar','plot'}<=methods:return 'mixed_bar_line'
    if f.get('direct_plot_call_sites',0)>=8:return 'many_series'
    return 'other_complex'
D.mkdir(exist_ok=True);rows=[];excluded_templates=set()
for r in map(json.loads,P.read_text().splitlines()):
    if r['source'] not in {'ChartMimic--ChartMimic','CSU-JPG--Chart2Code'}:continue
    try:a=audit(payload(r['payloads']['code']))
    except Exception as e:a={'safe_selfcontained_source':False,'security_issues':[type(e).__name__+':'+str(e)],'normalized_AST_template':None}
    if r['id'] in EXCLUDED:excluded_templates.add(a.get('normalized_AST_template'))
    rows.append(dict(r,static_audit=a,stratum=stratum(r),development_excluded=r['id'] in EXCLUDED))
assert len(rows)==3557
with (D/'inputs.jsonl').open('x') as f:
    for r in rows:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
groups=collections.defaultdict(list)
for r in rows:
    if r['static_audit']['safe_selfcontained_source'] and not r['development_excluded'] and r['static_audit']['normalized_AST_template'] not in excluded_templates:groups[(r['source'],r['stratum'])].append(r)
selected=[];seen_templates=set(excluded_templates)
for key,rs in sorted(groups.items()):
    count=0
    for r in sorted(rs,key=lambda r:sha((SEED+':'+r['id']).encode())):
        template=r['static_audit']['normalized_AST_template']
        if template in seen_templates:continue
        selected.append(r);seen_templates.add(template);count+=1
        if count==2:break
assert 10<=len(selected)<=20,len(selected)
with (D/'unseen_selected.jsonl').open('x') as f:
    for r in selected:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
summary={'schema':'matplotlib_plot_fixed_pool_v1','frozen_input_rows':len(rows),'by_source':dict(collections.Counter(r['source'] for r in rows)),'static_safe':sum(r['static_audit']['safe_selfcontained_source'] for r in rows),'static_skip_reasons':dict(collections.Counter(i for r in rows for i in r['static_audit']['security_issues'])),'development_ids_excluded':sorted(EXCLUDED),'development_AST_templates_excluded':sorted(t for t in excluded_templates if t),'public_seed':SEED,'unseen_rows':len(selected),'unseen_strata':dict(collections.Counter(r['source']+'|'+r['stratum'] for r in selected)),'unseen_ids':[r['id'] for r in selected],'all_unseen_templates_distinct':True,'inputs_sha256':sha((D/'inputs.jsonl').read_bytes()),'unseen_selected_sha256':sha((D/'unseen_selected.jsonl').read_bytes()),'source_images_read':0,'source_executions':0,'model_calls':0}
(D/'pool_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
