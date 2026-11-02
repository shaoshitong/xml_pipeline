"""Finite two-candidate native render/ROI/editing smoke, never canonical writes."""
import sys,json,collections,sqlite3,datetime,copy,hashlib,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';P=W/'prototype/svg_source_profile_scope_v1/triangle_marker_bound_family_cohort_v1';sys.path[:0]=[str(W/'prototype'),str(W/'scripts')]
import svg_native_triangle_marker_v1 as rule
import svg_native_marker_edit_probe_v1 as editing
import auto_quality_source_vector_v2 as prior
from svg_source_scene_dom_v1 import close_worker_runtime
from native_worker import native
from tikz_execution_binding_v2 import marker_metrics
from auto_quality_common_v4 import registration_record,image_quality,resource_checks,require_rendered_text
from strict_canvas_gate import require_declared_page
sha=lambda b:hashlib.sha256(b).hexdigest();D=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);report=json.loads((P/'triangle_rule_report.json').read_text());selected=[r for r in report['records'] if r.get('ok')][:3];results=[]
def font_stats(info):
 counts=collections.Counter()
 for row in info.get('actual_platform_font_usage',[]):
  for f in row.get('fonts',[]):counts[(row.get('cell'),f.get('postScriptName'),f.get('isCustomFont'),f.get('familyName'))]+=f.get('glyphCount',0)
 return sorted((str(k),v) for k,v in counts.items())
try:
 for row in selected:
  id=row['id'];case=P/id;out={'id':id,'published':False,'accepted':False,'implementation_sha256':sha(Path(rule.__file__).read_bytes()),'editing_implementation_sha256':sha(Path(editing.__file__).read_bytes())}
  try:
   state,worker,raw=D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone();record=json.loads(raw);assert worker is None and record['code_sha256']==row['input_code_sha256'] and record['image_sha256']==row['input_image_sha256'],'current revision changed';before=prior._read_clean(record['code_file'],record['code_sha256']).decode();proposal=json.loads((case/'triangle_rule_proposal.json').read_text());candidate=proposal['candidate_xml'];reference=prior._read_clean(record['original_reference'],record['source_image_sha256']);verified,contract=registration_record(record,reference,before);offset=contract['original_page_offset'] if contract else [0,0];fresh,dom=rule.propose(record,before);assert fresh['candidate_xml']==candidate,'Fresh source proposal changed';out['replay']=rule.verify_candidate_from_scene(dom,before,candidate,proposal,offset);out['editing']=editing.audit(candidate,proposal['markers']);resource_checks(R,record,candidate,reference);model=E.fromstring(candidate).find('.//mxGraphModel');width,height=(int(round(float(model.get(k)))) for k in ('pageWidth','pageHeight'));renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';old=native.native_job(before,width,height,180,renderer,8192,runtime);new=native.native_job(candidate,width,height,180,renderer,8192,runtime)
   out['render']={'before':{k:v for k,v in old.items() if k not in ('png','native_render')},'after':{k:v for k,v in new.items() if k not in ('png','native_render')}};assert old['ok'] and new['ok'],'strict native render refused before or after';require_declared_page(old['native_render'],width,height);require_declared_page(new['native_render'],width,height);(case/'triangle_before_native.png').write_bytes(old['png']);(case/'triangle_candidate_native.png').write_bytes(new['png']);(case/'triangle_candidate_native_info.json').write_text(json.dumps(new['native_render'],ensure_ascii=False,indent=2)+'\n');shifted=copy.deepcopy(dom)
   for obj in shifted['objects']:
    obj['bbox']['x']+=offset[0];obj['bbox']['y']+=offset[1];obj['matrix'][4]+=offset[0];obj['matrix'][5]+=offset[1]
    if obj.get('sampledPoints'):obj['sampledPoints']=[[x+offset[0],y+offset[1]] for x,y in obj['sampledPoints']]
   binding={'native_arrowheads':[{'source_object':m['source_head_object'],'edge':m['edge'],'side':m['side'],'marker':m['native_marker'],'native_marker_stroke':'transparent'} for m in proposal['markers']]};out['marker_ROI']=marker_metrics(old['png'],new['png'],candidate,shifted,binding);out['source_font_glyph_inventory_unchanged']=font_stats(old['native_render'])==font_stats(new['native_render']);out['text_paint']=require_rendered_text(candidate,new['native_render']);out['all_current_fonts_custom']=all(f.get('isCustomFont') for row in new['native_render'].get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0));out['complete_marker_coverage']=proposal['complete_source_marker_coverage'];out['before_native_png_sha256']=sha(old['png']);out['after_native_png_sha256']=sha(new['png']);out['input_code_sha256']=record['code_sha256'];out['input_image_sha256']=record['image_sha256'];out['candidate_code_sha256']=sha(candidate.encode());out['source_code_sha256']=record['source_code_sha256'];out['source_image_sha256']=record['source_image_sha256'];out['same_renderer_sha256']=sha(renderer.read_bytes());out['reference_offset']=offset
   for name,png,info in [('before',old['png'],old['native_render']),('after',new['png'],new['native_render'])]:
    try:out[name+'_original_image_quality']=image_quality(reference,png,verified,info.get('actual_text_positions'))
    except Exception as error:out[name+'_original_image_quality_error']=repr(error)
   after=D.execute('select worker_pid,output_record from jobs where id=?',(id,)).fetchone();assert after[0] is None and json.loads(after[1])['code_sha256']==record['code_sha256'] and json.loads(after[1])['image_sha256']==record['image_sha256'],'revision changed during smoke';out['current_revision_rechecked_after_smoke']=True
  except Exception as error:out['error']=repr(error)
  (case/'triangle_native_smoke.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');results.append(out)
finally:close_worker_runtime()
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':rule.POLICY,'results':results,'scope':'Fresh source+strict native render+actual native endpoint/direction edit and restored paint. Candidate prototypes only; no source profile waiver, accepted outcome, job/queue/canonical mutation or API call.'};(P/'triangle_native_smoke_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(P/'triangle_native_smoke_report.json'),'cases':[{k:r.get(k) for k in ('id','error','complete_marker_coverage','source_font_glyph_inventory_unchanged','all_current_fonts_custom','current_revision_rechecked_after_smoke')}|{'editing_ok':r.get('editing',{}).get('ok'),'marker_roi_ok':r.get('marker_ROI',{}).get('ok'),'outside_roi_changed':r.get('marker_ROI',{}).get('changed_pixels_outside_marker_rois'),'before_original_ok':r.get('before_original_image_quality',{}).get('ok'),'after_original_ok':r.get('after_original_image_quality',{}).get('ok'),'after_original_error':r.get('after_original_image_quality_error')} for r in results]},ensure_ascii=False),flush=True)
