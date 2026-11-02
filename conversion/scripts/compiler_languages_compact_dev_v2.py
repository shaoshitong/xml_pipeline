import pathlib,sys,sqlite3,json,uuid,io,argparse,copy,xml.etree.ElementTree as E
R=pathlib.Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
p=argparse.ArgumentParser();p.add_argument('--format',required=True,choices=['tikz','mermaid']);a=p.parse_args()
if a.format=='tikz':
 import compiler_tikz_free_paths_v1 as c
 ids=['0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0045d2aab53331e329c7b7109eaf64022c6937b99229e12c6c0a8967073dc246','0036b5425c60a565c4de754bd9940630f0cacb14f7813e9c83eda930de1d1a7e']
else:
 import compiler_languages_source_layout_v2 as c
 ids=['0005a67a974edb3bb5b4895389d0d314689bc67c773a13ddfbd64445d5f69c5f','00183704798da07e820aaa5a8cfe725ff7411328089b7287fa5b8509d0e1cf52','001f560436006922610ca3f7610b32258ba9ea2de3b64f06c7260e53ddf650e3']
base=W/c.VERSION/'development'/uuid.uuid4().hex;base.mkdir(parents=True);db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);cols=[x[1] for x in db.execute('pragma table_info(jobs)')];rows=[]
print(json.dumps({'development_directory':str(base),'format':a.format,'cases':len(ids),'unseen_consumed':0}),flush=True)
for ident in ids:
 before=db.execute('select * from jobs where id=?',(ident,)).fetchone();job=dict(zip(cols,before));old=json.loads(job['output_record']) if job['output_record'] else {};out=c.convert(old,job,base/ident);row={k:out.get(k) for k in ['ok','reason','detail','stage','diagnostic_stage','stats','record_file']};row['id']=ident;row['source_reproduction']=out.get('source_reproduction');row['canonical_unchanged']=before==db.execute('select * from jobs where id=?',(ident,)).fetchone()
 if out['ok']:
  try:
   r=out['record'];xml=(R/r['code_file']).read_text();profile=c.validate_source(r,xml);row['source_profile']=profile
   if profile['ok']:
    row['editing']=c.audit_editing(r,xml,profile,R);row['negatives']=[]
    mutations={'delete_arrow':lambda root:next(x for x in root.iter('mxCell') if x.get('edge')=='1').set('style','endArrow=none;startArrow=none;'), 'delete_text':lambda root:next(x for x in root.iter('mxCell') if x.get('value','').strip()).set('value','')}
    for name,change in mutations.items():
     root=E.fromstring(xml);change(root);bad=E.tostring(root,encoding='unicode');rr=copy.deepcopy(r);rr['code_sha256']=c.sha(bad.encode());rr[c.FIELD]['candidate_code_sha256']=rr['code_sha256'];q=c.validate_source(rr,bad);row['negatives'].append({'kind':name,'rehashed_submission':True,'rejected':not q['ok'],'failures':q['failures']})
   from native_worker import native
   from auto_quality_common_v4 import image_quality,resource_checks,require_rendered_text
   from PIL import Image
   ref=(R/r['original_reference']).read_bytes();w,h=Image.open(io.BytesIO(ref)).size;render=native.native_job(xml,w,h,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');row['strict_native_render_ok']=render['ok']
   if render['ok']:
    info=render['native_render'];row['resources']=resource_checks(R,r,xml,ref);row['actual_text']=require_rendered_text(xml,info);row['visual']=image_quality(ref,render['png'],r,info['actual_text_positions']);usage=[f for x in info['actual_platform_font_usage'] for f in x.get('fonts',[]) if f.get('glyphCount',0)>0];row['all_fonts_custom']=bool(usage) and all(x['isCustomFont'] for x in usage);row['full_QA_equivalent']=bool(profile['ok'] and row.get('editing',{}).get('ok') and row['visual']['ok'] and row['all_fonts_custom'] and all(x['rejected'] for x in row.get('negatives',[])))
  except Exception as e:row['QA_exception']=str(e)[:2000]
 rows.append(row);(base/'report.json').write_text(json.dumps({'format':a.format,'results':rows,'model_calls':0,'unseen_consumed':0},indent=2))
 brief={k:row.get(k) for k in ['id','ok','reason','detail','stats','QA_exception','full_QA_equivalent','record_file']};brief['profile_ok']=row.get('source_profile',{}).get('ok');brief['profile_failures']=row.get('source_profile',{}).get('failures');brief['source_ssim']=(row.get('source_reproduction') or {}).get('visual',{}).get('ssim_1024');brief['native_visual_failures']=row.get('visual',{}).get('failures');print(json.dumps(brief),flush=True)
print(json.dumps({'report':str(base/'report.json'),'converted':sum(bool(x['ok']) for x in rows),'full_QA_equivalent':sum(bool(x.get('full_QA_equivalent')) for x in rows),'canonical_mutations':sum(not x['canonical_unchanged'] for x in rows)}),flush=True)
