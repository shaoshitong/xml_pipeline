"""Independent fresh SOURCE HTML -> native full quality, with actual ink proof."""
import hashlib,io,json,sqlite3,uuid,re
from pathlib import Path
import xml.etree.ElementTree as E
from html.parser import HTMLParser
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='independent_fresh_HTML_source_slots_decorated_exact_ink_native_quality_v8'
sha=lambda b:hashlib.sha256(b).hexdigest()

def require(ok,reason):
 if not ok:raise ValueError(reason)

class LabelGrammar(HTMLParser):
 def handle_starttag(self,tag,attrs):
  require(tag=='span','html_source_nontext_label_overlay')
  for k,v in attrs:
   require(k in ['style','data-img2code-source-clip','data-img2code-source-glyph','data-img2code-source-whitespace'],'html_source_unknown_label_attribute')
   if k=='style':
    for item in v.split(';'):
     if not item:continue
     name,value=item.split(':',1);require(name.strip() in ['clip-path','position','left','top','white-space','line-height'],'html_source_unproved_label_style')
     if name.strip()=='line-height':require(re.fullmatch(r'normal|[0-9]+(?:\.[0-9]+)?px',value.strip())is not None,'html_source_unproved_literal_line_height')
     if name.strip()=='white-space':require(value.strip()=='pre','html_source_unproved_literal_whitespace')
     if name.strip()=='position':require(value.strip()=='relative','html_source_unproved_label_positioning')
 def handle_endtag(self,tag):require(tag=='span','html_source_nontext_label_overlay')
 def handle_startendtag(self,tag,attrs):raise ValueError('html_source_nontext_label_overlay')

def pins():
 import auto_quality_batch_v4b as legacy
 out={str((Path(k) if Path(k).is_absolute() else Path(legacy.__file__).parent/k).resolve()):v for k,v in legacy.IMPLEMENTATION.items()}
 for n in ['html_source_frontend_v8.py','html_source_clip_v8.py','html_source_range_contract_v1.py','compiler_html_source_quality_ro_v8.py','html_native_editing_v5.py','native_html_font_compiler_v3.py','native_font_order_probe_v3.py','native_html_font_quality_v3.py','html_actual_text_alignment.py','html_source_whitespace_capture_v8.py','html_source_whitespace_ir_v8.js','html_batch_v3.py','html_range_extractor_v2.py','html_dom_clip.js']:
  p=W/'scripts'/n;out[str(p)]=sha(p.read_bytes())
 for p in [W/'rendering_clipbox_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']:out[str(p)]=sha(p.read_bytes())
 return out

def verify(identifier,record_file,data_root,plugin_file,work,database=W/'jobs.sqlite'):
 from fixed_batch_case_v1 import save,raw
 from auto_quality_common import checked,structure_checks,resource_checks,require_rendered_text,image_quality
 from strict_canvas_gate import require_declared_page
 from html_source_whitespace_capture_v8 import capture_source
 from html_actual_text_alignment import analyze,_plain
 from html_actual_text_clip_alignment_v4 import native_rectangle
 from html_source_clip_v8 import source_hidden_capture,ink_metrics
 from html_source_range_contract_v1 import from_analysis
 from native_html_font_quality_v3 import verify as font_verify
 from html_native_editing_v5 import audit as editing_audit
 from native_worker import native
 import auto_quality_source_vector_v2 as source_profile
 from PIL import Image
 record_file=Path(record_file).resolve(strict=True);work=Path(work).resolve();require(Path(data_root).resolve()==R.resolve(),'html_source_wrong_root');require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve()) and not work.exists(),'html_source_unowned_quality_work');work.mkdir(parents=True)
 blob=record_file.read_bytes();record=json.loads(blob);implementation=pins();policy=VERSION+':'+sha(raw(implementation))[:20]
 report=dict(id=identifier,version=VERSION,quality_policy=policy,checks={},failures=[],ok=False,accepted=False,canonical_mutations=0,model_calls=0,implementation_pins=implementation,input_record_sha256=sha(blob))
 try:
  require(Path(plugin_file).resolve()==W/'scripts/html_source_frontend_v8.py','html_source_wrong_plugin')
  require(all(sha(Path(p).read_bytes())==h for p,h in implementation.items()),'infrastructure_html_source_pins_changed')
  with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30) as d:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
  require(job is not None and job[12] is None,'html_source_job_missing_or_owned');original=json.loads(job[4])
  require((record['id'],record['source_pair_sha256'],record['source_format'],record['category'],record['source'],record['source_code_sha256'],record['source_image_sha256'])==(identifier,identifier,'html','poster',original['source'],original['code_sha256'],original['image_sha256']),'html_source_original_identity_changed')
  xml=checked(R,record['code_file'],record['code_sha256']).decode();reference=checked(R,record['original_reference'],record['source_image_sha256']);source=checked(R,record['original_source_code'],record['source_code_sha256']);stored_png=checked(R,record['image_file'],record['image_sha256'])
  source_profile._identity(record,xml)
  manifest=json.loads(job[11]);require((R/manifest['source_code']).read_bytes()==source and (R/manifest['reference_image']).read_bytes()==reference,'html_source_payload_not_exact_original_manifest')
  model=E.fromstring(xml).find('.//mxGraphModel');require(model is not None,'html_source_missing_model');size=[int(round(float(model.get(k)))) for k in ['pageWidth','pageHeight']];viewport=list(Image.open(io.BytesIO(reference)).size);offset=[32,32]
  require(size==[n+64 for n in viewport],'html_source_unproved_page_registration')
  structure=structure_checks(xml);require(structure['edges']==0,'html_poster_connector_semantics_unsupported');report['checks']['structure']=structure;report['checks']['resources']=resource_checks(R,record,xml,reference)
  # Validate the exact frozen font revision and its current native payload;
  # SOURCE correctness is checked separately below, never inferred from this.
  fp=record.get('round2_font_repair') or {};audit=(R/fp.get('audit','')).resolve(strict=True);owner=W/'auto_quality_font_repair_v1/round2_v1'/identifier
  require(audit.name=='report.json' and audit.is_relative_to(owner.resolve()),'html_source_missing_owned_font_revision')
  frozen=json.loads((audit.parent/'candidate_record.json').read_bytes());require(frozen['code_sha256']==record['code_sha256'] and frozen['image_sha256']==record['image_sha256'] and frozen.get('round2_font_repair')==fp,'html_source_font_revision_not_current')
  font=font_verify(frozen,work/'font_source');require(font.get('ok') is True,'html_source_independent_font_proof_failed:'+str(font.get('reason')))
  strict=native.native_job(xml,*size,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(strict.get('ok') is True,'html_source_actual_strict_native_render_failed');require_declared_page(strict['native_render'],*size)
  fresh=native.native_job(xml,*size,180,W/'rendering_clipbox_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(fresh.get('ok') is True,'html_source_actual_native_render_failed');info=fresh['native_render'];require(fresh['png']==strict['png']==stored_png,'html_source_png_not_exact_fresh_native')
  save(work/'fresh.png',fresh['png'])
  report['checks']['render']=dict(code_sha256=record['code_sha256'],image_sha256=sha(fresh['png']),canvas=size,strict_outside_page_pixels=0,renderer_sha256=sha((W/'rendering_paintbounds_strict/remote_render.py').read_bytes()),clip_box_renderer_sha256=sha((W/'rendering_clipbox_strict/remote_render.py').read_bytes()),actual_upstream_drawio=True)
  report['checks']['text_paint']=require_rendered_text(xml,info);usage=[f for row in info['actual_platform_font_usage'] for f in row['fonts'] if f.get('glyphCount',0)];require(usage and all(f.get('isCustomFont') for f in usage),'html_source_unembedded_actual_font')
  report['checks']['fonts']=dict(all_rendered_fonts_embedded=True,actual_custom_font_glyphs=sum(f['glyphCount'] for f in usage),independent_font_revision_report=dict(file=font['report_file'],sha256=font['report_sha256']))
  dom,served,source_png,capture=capture_source(record,work/'fresh_source');require(capture['viewport']==viewport,'html_source_viewport_changed');require(not [i for i in dom.get('unsupported',[]) if i.get('reason')!='css_stacking_order'],'html_source_unsupported_source_features')
  coverage=source_profile._html_coverage(dom,xml,served);paint=source_profile._html_paint_order(dom,xml);require(coverage['ok'] and paint['ok'],'html_source_complete_object_or_paint_coverage_failed:'+str(coverage.get('errors'))+str(paint.get('errors')))
  translation=coverage['native_source_paint']['source_layout_translation'];require([translation[k] for k in ['dx','dy']]==offset,'html_source_registration_not_source_geometry_translation')
  objects={str(o['id']+1):o for o in dom['objects'] if o['type']=='text'};cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};glyphs={r['cell']:r for r in analyze(dom,info,xml,offset)['objects']};clips={r['cell']:r['clips'] for r in info['actual_clip_boxes']};details=[]
  for key,o in objects.items():
   c=cells[key];LabelGrammar(convert_charrefs=True).feed(c.get('value',''));require('data-img2code-source-whitespace="v8"'in c.get('value','')and 'nl2Br=0'in c.get('style',''),'html_source_literal_whitespace_lowering_missing');g=glyphs[key]
   require('line-height:'+o['actualSourceCss']['lineHeight']+';'in c.get('value',''),'html_source_line_height_not_exact_SOURCE_css')
   require(g.get('source_font_basis')=='actual_text_node' and set(g.get('native_faces') or ())<=set(g.get('source_faces') or ()) and g.get('native_faces'),'html_source_physical_glyph_font_not_in_original_source')
   alignment=from_analysis(g);require(alignment['ok']and alignment['aligned'],'html_source_actual_graphemes_not_source_aligned')
   clip=o.get('sourceClip',{});require(not clip.get('unmodeled'),'html_source_unmodeled_clip');chain=clip.get('chain',[])
   require(all(all(float(str(r).removesuffix('px'))==0 for r in a['radius']) for a in chain),'html_source_rounded_clip_pending')
   bounds=[max([0]+[a['left'] for a in chain if a['clipX']])+32,max([0]+[a['top'] for a in chain if a['clipY']])+32,min([viewport[0]]+[a['right'] for a in chain if a['clipX']])+32,min([viewport[1]]+[a['bottom'] for a in chain if a['clipY']])+32]
   require(all(abs(x-round(x))<1e-8 for x in bounds),'html_source_fractional_clip_pending');actual=clips.get(key,[]);require(len(actual)==1 and len(actual[0]['fragments'])==1,'html_source_missing_or_duplicate_actual_native_clip')
   live=native_rectangle(actual[0]);require(all(abs(a-b)<=.03 for a,b in zip(live,bounds)),'html_source_actual_clip_not_source_css_intersection');details.append(dict(cell=key,source_clip=bounds,native_clip=live,maximum_original_range_slot_residual=g['maximum_absolute_position_error'],independent_range_slot_contract=alignment))
  background=E.fromstring(xml)
  for c in background.iter('mxCell'):
   if c.get('id') in objects:c.set('value','')
  bgxml=E.tostring(background,encoding='unicode');bg=native.native_job(bgxml,*size,180,W/'rendering_clipbox_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(bg.get('ok') is True,'html_source_native_background_failed')
  hidden,hiddenproof=source_hidden_capture(record,dom,set(objects),source_png,work/'fresh_source_hidden');ink=ink_metrics(source_png,hidden,fresh['png'],bg['png'],offset);require(ink['exact_same_domain_source_native_ink'] is True,'html_source_actual_text_ink_not_exact_source:'+json.dumps(ink));save(work/'native.background.png',bg['png'])
  report['checks']['source']=dict(ok=True,supported=True,profile=VERSION,evidence=dict(complete_source_coverage=True,all_source_objects_and_original_assets=coverage,actual_css_paint_order=paint,source_layout_translation=offset,actual_source_glyph_and_clip_checks=details,all_fresh_HTML_native_text_ink=ink,source_raster_code_and_image_hashes=[record['source_code_sha256'],record['source_image_sha256']],no_target_image_fitting=True))
  visual=image_quality(reference,fresh['png'],{'native_canvas_contract':{'offset':offset}},info['actual_text_positions']);report['checks']['visual']=visual;require(visual['ok'],'raster_anomaly:'+','.join(visual['failures']))
  report['checks']['native_editing']=editing_audit(xml,work/'native_editing');report['checks']['native_editing']['source_profile_proves_no_semantic_edges']=True
  require(all(sha(Path(p).read_bytes())==h for p,h in implementation.items()),'infrastructure_html_source_pins_changed');require(record_file.read_bytes()==blob,'html_source_record_changed_during_QA')
  with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30) as d:require(d.execute('select * from jobs where id=?',(identifier,)).fetchone()==job,'html_source_original_job_changed')
  report['ok']=True;save(work/'fresh.png',fresh['png'])
 except Exception as exc:report['failures'].append(dict(type=type(exc).__name__,reason=str(exc)[:7000]))
 report['evidence_file']=str(work/'report.json');save(work/'report.json',raw(report));return report
