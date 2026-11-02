import json,sqlite3,hashlib
from native_worker import R,W,now
from durable_sqlite import begin,commit
sha=lambda b:hashlib.sha256(b).hexdigest();D=sqlite3.connect(W/'jobs.sqlite',timeout=2);rows=D.execute("select id,state,output_record from jobs where json_type(output_record,'$.native_embedded_fonts')='object' and json_extract(output_record,'$.conversion_method') like 'mermaid_10_9_1_source_global_reference_fit%' ").fetchall();reports=[]
for id,state,raw in rows:
 assert state in ['accepted','needs_quality_repair','harness_review_pending'],(id,state)
 r=json.loads(raw);fonts=r['native_embedded_fonts'];assert fonts and all(k==v['family'] for k,v in fonts.items())
 for f in fonts.values():
  for k,hk in [('file','sha256'),('original_file','original_sha256')]:
   p=R/f[k];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==f[hk]
 for k,hk in [('code_file','code_sha256'),('image_file','image_sha256')]:assert sha((R/r[k]).read_bytes())==r[hk]
 b=W/'font_registry_schema_repairs'/id/sha(raw.encode());b.mkdir(parents=True,exist_ok=True);(b/'before_record.json').write_text(raw);r['native_embedded_fonts']=list(fonts.values());r['font_registry_schema_repair']={'at':now(),'audit':str(b.relative_to(R)),'change':'Normalize verified font-family map to the canonical list schema; XML, PNG and font bytes unchanged'}
 if id=='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce':
  r['root_review']={'decision':'requires_repair','at':now(),'reason':'Global source scale and fonts improved, but other native edges can paint over edge-owned label background shapes. Native labelBackgroundColor prototype also failed to resolve the paint-order conflict. Not accepted for final release.'};r.setdefault('validation_pending',[]).append('Resolve cross-edge label background paint order while retaining label/edge editability and original layout')
 begin(D);assert D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==(state,raw)
 path=(R/r['code_file']).parent/'conversion.json';tmp=path.with_suffix('.fontschema.tmp');tmp.write_text(json.dumps(r,indent=2));tmp.replace(path);D.execute('update jobs set output_record=?,updated_at=? where id=?',(json.dumps(r),now(),id));commit(D);reports.append({'id':id,'state':state,'font_files':len(fonts),'xml_png_unchanged':True})
 result={'at':now(),'repairs':reports,'ok':True};(W/'reference_fit_font_schema_repair.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'repairs':reports,'ok':True}))
