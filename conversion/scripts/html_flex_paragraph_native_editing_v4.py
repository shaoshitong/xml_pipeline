"""Actual owner pixel interventions with live glyph-paint ROIs and safe batches.

Disjoint batches share screenshots, never owner evidence: every owner must
change pixels inside its own before/after support; no pixel outside the union
may change. Every batch restores the whole model, native DOM and full RGBA
exactly. All nonempty paragraph Text nodes are actually edited.
"""
from pathlib import Path
import base64,hashlib,io,json,math,time,uuid,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js')
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
def pixels(blob):
 with Image.open(io.BytesIO(blob))as im:return np.asarray(im.convert('RGBA')).copy()
def save(path,blob):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb')as f:f.write(blob)
 return dict(file=str(path),sha256=sha(blob),bytes=len(blob))
def encoded(x):return(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def union(*rects):
 rects=[r for r in rects if r and r['w']>0 and r['h']>0];require(rects,'native_owner_has_no_actual_paint_or_model_support');x=min(r['x']for r in rects);y=min(r['y']for r in rects);return dict(x=x,y=y,w=max(r['x']+r['w']for r in rects)-x,h=max(r['y']+r['h']for r in rects)-y)
def roi(rect,size):
 left=max(0,math.floor(rect['x'])-4);top=max(0,math.floor(rect['y'])-4);right=min(size[0],math.ceil(rect['x']+rect['w'])+4);bottom=min(size[1],math.ceil(rect['y']+rect['h'])+4);require(right>left and bottom>top,'native_owner_actual_support_outside_complete_viewport');return dict(x=left,y=top,width=right-left,height=bottom-top)
def overlaps(a,b):return min(a['x']+a['width'],b['x']+b['width'])>max(a['x'],b['x'])and min(a['y']+a['height'],b['y']+b['height'])>max(a['y'],b['y'])
def batches(rows):
 result=[]
 for row in sorted(rows,key=lambda r:(-r['roi']['width']*r['roi']['height'],r['cell'])):
  for group in result:
   if all(not overlaps(row['roi'],other['roi'])and row['cell']not in other.get('ancestor_ids',[])and other['cell']not in row.get('ancestor_ids',[])for other in group):group.append(row);break
  else:result.append([row])
 return result
def crop(array,r):return array[r['y']:r['y']+r['height'],r['x']:r['x']+r['width']]
def audit(xml,work,*,record=None,source_expected=None):
 from playwright.sync_api import sync_playwright
 from native_worker import native
 started=time.perf_counter();requested=Path(work).resolve();require(requested.is_relative_to(R),'native_edit_evidence_outside_registered_remote_root');requested.mkdir(parents=True,exist_ok=False)
 artifact=requested if requested.is_relative_to(R/'clean')else R/'clean/html_flex_paragraph_native_editing_v4'/uuid.uuid4().hex
 if artifact!=requested:artifact.mkdir(parents=True,exist_ok=False)
 tree=E.fromstring(xml);models=list(tree.iter('mxGraphModel'));require(len(models)==1,'native_editing_requires_one_model');size=[int(models[0].get(k))for k in('pageWidth','pageHeight')];require(0<max(size)<=8192 and size[0]*size[1]<=64_000_000,'native_editing_resource_bound')
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';expected=json.loads(manifest.read_bytes())['viewer_bundle_sha256'];require(sha(viewer.read_bytes())==expected,'native_editing_official_runtime_pin_changed')
 from html_source_owner_zero_paint_v1 import audit as source_zero_paint
 import html_source_owner_zero_paint_v1 as source_zero_module
 pins={str(p):sha(p.read_bytes())for p in(Path(__file__),JS,viewer,manifest,Path(source_zero_module.__file__))};script=JS.read_text();report=dict(ok=False,policy='actual_HTML_native_owner_disjoint_paint_support_source_zero_paint_visibility_witness_v4',candidate_code_sha256=sha(xml.encode()),artifact_root=str(artifact),requested_work=str(requested),pins=pins,moves=[],text_edits=[],batches=[],visibility_witnesses=[],actual_native_object_moves=0,actual_native_text_edits=0,normal_conversions=0,model_calls=0,canonical_mutations=0,original_reference_pixels_read=False,RGBA_restore_tolerance=0,screenshot_calls=0,planning_is_not_pixel_proof=True)
 screenshot_seconds=0.;image_seconds=0.;phase='initialize';browser=None
 try:
  with sync_playwright()as pw:
   browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
   try:
    page=browser.new_page(viewport=dict(zip(('width','height'),size)),device_scale_factor=1);blocked=[];page.route('**/*',lambda r:(blocked.append(r.request.url),r.abort())[1]);page.set_content('<html><body></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer))
    phase='resource_ready_baseline';setup=page.evaluate(script,dict(action='init',xml=xml,width=size[0],height=size[1]));require(setup['fonts_ready'],'native_editing_fonts_not_ready');report['resource_readiness']={k:setup[k]for k in('actual_native_image_resources_decoded','fonts_ready')};objects=setup['objects'];require(objects,'native_editing_has_no_vertices')
    cdp=page.context.new_cdp_session(page)
    def screenshot(path):
     nonlocal screenshot_seconds,image_seconds
     t=time.perf_counter();blob=base64.b64decode(cdp.send('Page.captureScreenshot',dict(format='png',fromSurface=True,captureBeyondViewport=False,optimizeForSpeed=True))['data']);screenshot_seconds+=time.perf_counter()-t;report['screenshot_calls']+=1;t=time.perf_counter();array=pixels(blob);image_seconds+=time.perf_counter()-t;return array,save(path,blob)
    baseline,baseline_asset=screenshot(artifact/'before.png');report['baseline_png']=baseline_asset;report['baseline_RGBA_sha256']=sha(baseline.tobytes());normal_blob=page.screenshot(type='png');require(np.array_equal(pixels(normal_blob),baseline),'native_optimized_capture_not_exact_official_viewport_RGBA');report['normal_capture_control']=dict(PNG=save(artifact/'normal_capture_control.png',normal_blob),whole_RGBA_equal_optimized=True,RGBA_error_tolerance=0)
    phase='actual_live_glyph_support_planning';planning=time.perf_counter();text_plans=page.evaluate(script,dict(action='plan_text'));after_plan,plan_asset=screenshot(artifact/'after_support_planning.png');require(np.array_equal(after_plan,baseline),'native_support_planning_did_not_restore_complete_original_RGBA');report['support_planning_seconds']=time.perf_counter()-planning
    move_rows=[]
    for obj in objects:
     b=obj['support']['bbox'];require(b is not None,'native_owner_has_no_actual_support');moved={**b,'x':b['x']+17,'y':b['y']+11};move_rows.append({**obj,'roi':roi(union(b,moved),size),'before_actual_paint_support':obj['support']})
    text_rows=[{**r,'roi':roi(union(r['before']['bbox'],r['after']['bbox']),size)}for r in text_plans]
    require(len(text_rows)==sum(o['paragraph']for o in objects),'native_text_owner_scope_changed_during_support_planning')
    groups={kind:batches(rows)for kind,rows in [('move',move_rows),('text',text_rows)]};report['batch_count_by_kind']={k:len(v)for k,v in groups.items()};report['vertex_count']=len(objects);report['paragraph_count']=len(text_rows)
    for kind in('move','text'):
     for index,group in enumerate(groups[kind]):
      phase=kind+':batch:'+str(index);require(all(not overlaps(a['roi'],b['roi'])for i,a in enumerate(group)for b in group[i+1:]),'native_batch_support_not_disjoint');ids=[r['cell']for r in group];changed=page.evaluate(script,dict(action='apply',kind=kind,ids=ids));edited,edited_asset=screenshot(artifact/(kind+'_'+str(index)+'_edited.png'));delta=np.any(edited!=baseline,axis=2);mask=np.zeros(delta.shape,dtype=bool)
      for row in group:
       r=row['roi'];mask[r['y']:r['y']+r['height'],r['x']:r['x']+r['width']]=True
      outside=int(np.count_nonzero(delta&~mask));require(outside==0,'native_batch_changed_pixels_outside_union_of_actual_owner_supports')
      byid={r['cell']:r for r in changed};owner_proofs=[]
      for row in group:
       r=row['roi'];before=crop(baseline,r);after=crop(edited,r);count=int(np.count_nonzero(np.any(before!=after,axis=2)))
       actual=byid[row['cell']]['after_support']['bbox'];require(actual is not None,'native_mutated_owner_has_no_actual_support');clipped=dict(x=max(0,actual['x']),y=max(0,actual['y']),right=min(size[0],actual['x']+actual['w']),bottom=min(size[1],actual['y']+actual['h']));require(clipped['x']>=r['x']and clipped['y']>=r['y']and clipped['right']<=r['x']+r['width']and clipped['bottom']<=r['y']+r['height'],'native_actual_mutated_support_escaped_its_own_planned_ROI')
       owner_proofs.append(dict(cell=row['cell'],actual_changed_pixels=count,original_pixels_sha256=sha(before.tobytes()),edited_pixels_sha256=sha(after.tobytes()),actual_pixel_roi=r,hash_domain='actual_full_frame_RGBA_owner_crop',actual_glyph_and_model_paint_support=row.get('before_actual_paint_support',row.get('before')),actual_mutated_support=byid[row['cell']]['after_support'],actual_mutated_support_contained_in_own_ROI=True,**{k:v for k,v in byid[row['cell']].items()if k not in('after_support','cell')}))
      restored=page.evaluate(script,dict(action='restore',kind=kind));final,final_asset=screenshot(artifact/(kind+'_'+str(index)+'_restored.png'));require(np.array_equal(final,baseline),'native_batch_full_RGBA_not_exactly_restored');restored_by_id={r['cell']:r for r in restored}
      for row in owner_proofs:
       row.update(restored_by_id[row['cell']]);row.update(restored_pixels_sha256=sha(crop(final,row['actual_pixel_roi']).tobytes()),whole_actual_native_pixels_restored_exactly=True,actual_paint_DOM_restored=True)
       (report['moves']if kind=='move'else report['text_edits']).append(row)
      report['batches'].append(dict(kind=kind,index=index,owner_ids=ids,owners=len(group),supports_pairwise_disjoint=True,owner_regions=[r['roi']for r in group],outside_union_RGBA_changed_pixels=outside,whole_frame_RGBA_restored_exactly=True,edited_png=edited_asset,restored_png=final_asset))
    unresolved={r['cell']for r in report['moves']+report['text_edits']if r['actual_changed_pixels']==0}
    if unresolved:
     phase='fresh_original_SOURCE_zero_paint_binding';require(record is not None,'visibility_witness_requires_original_SOURCE_record_and_hash_binding');require(record['code_sha256']==sha(xml.encode()),'visibility_witness_other_candidate');source_proof=source_zero_paint(record,xml,unresolved,artifact/'SOURCE_zero_visible_paint',source_expected,browser=browser);report['source_zero_paint_equivalence']=source_proof;bound={r['cell']:r for r in source_proof['rows']};require(set(bound)==unresolved,'visibility_witness_SOURCE_owner_scope_changed')
     for cell in sorted(unresolved):
      phase='visibility_witness:'+cell;folder=artifact/('visibility_'+cell);folder.mkdir();hide_state=page.evaluate(script,dict(action='hide_original',id=cell));hidden,hidden_asset=screenshot(folder/'original_native_hidden.png');require(int(np.count_nonzero(np.any(hidden!=baseline,axis=2)))==0,'SOURCE_zero_but_original_native_owner_has_extra_visible_paint:'+cell);hide_restore=page.evaluate(script,dict(action='restore_hidden'));unhidden,unhidden_asset=screenshot(folder/'original_native_restored.png');require(np.array_equal(unhidden,baseline),'native_original_visibility_control_not_whole_RGBA_restored');witness=page.evaluate(script,dict(action='visibility_start',id=cell));visible,visible_asset=screenshot(folder/'visible_witness.png');visible_count=int(np.count_nonzero(np.any(visible!=baseline,axis=2)));require(visible_count>0,'original_zero_paint_owner_not_actually_visible_under_witness:'+cell)
      def local_delta(a,b,rect):
       selected=roi(rect,size);mask=np.zeros(a.shape[:2],dtype=bool);mask[selected['y']:selected['y']+selected['height'],selected['x']:selected['x']+selected['width']]=True;delta=np.any(a!=b,axis=2);require(np.count_nonzero(delta&~mask)==0,'visibility_witness_changed_pixels_outside_actual_owner_support');return int(np.count_nonzero(delta)),selected
      _,visible_roi=local_delta(baseline,visible,witness['actual_support']['bbox']);movement=page.evaluate(script,dict(action='visibility_move'));moved,moved_asset=screenshot(folder/'visible_witness_moved.png');move_count,move_roi=local_delta(visible,moved,union(witness['actual_support']['bbox'],movement['actual_support']['bbox']));require(move_count>0,'visible_witness_geometry_move_did_not_change_actual_pixels:'+cell);pose_restore=page.evaluate(script,dict(action='visibility_move_restore'));pose,pose_asset=screenshot(folder/'visible_witness_pose_restored.png');require(np.array_equal(pose,visible),'visibility_witness_geometry_pose_not_whole_RGBA_restored');text_proof=None
      if cell.startswith('source_paragraph_owner_'):
       text_edit=page.evaluate(script,dict(action='visibility_text'));altered,altered_asset=screenshot(folder/'visible_witness_text_edited.png');text_count,text_roi=local_delta(visible,altered,union(witness['actual_support']['bbox'],text_edit['actual_support']['bbox']));require(text_count>0,'visible_witness_Text_edit_did_not_change_actual_pixels:'+cell);text_proof=dict(**text_edit,actual_changed_pixels=text_count,actual_pixel_roi=text_roi,actual_PNG=altered_asset)
      restore=page.evaluate(script,dict(action='visibility_restore'));restored,restored_asset=screenshot(folder/'whole_original_restored.png');require(np.array_equal(restored,baseline),'visibility_witness_complete_original_RGBA_not_exactly_restored');report['visibility_witnesses'].append(dict(cell=cell,source_original_visible_paint_changed_pixels=0,original_native_visible_paint_changed_pixels=0,source_nonpainted_layout_only=True,effective_complexity_excluded=True,source_binding=bound[cell],original_native_hidden=hidden_asset,original_native_hide_state=hide_state,original_native_restore=unhidden_asset,original_native_hide_restore=hide_restore,visible_witness=witness,visible_witness_actual_changed_pixels=visible_count,visible_witness_ROI=visible_roi,visible_witness_PNG=visible_asset,actual_geometry_move=dict(**movement,actual_changed_pixels=move_count,actual_pixel_roi=move_roi,actual_PNG=moved_asset),witness_pose_restore=pose_restore,witness_pose_restored_PNG=pose_asset,actual_Text_edit=text_proof,complete_original_restore=restore,complete_original_restored_PNG=restored_asset,whole_model_states_DOM_order_and_RGBA_restored_exactly=True,RGBA_restore_tolerance=0))
    phase='all_owner_actual_visible_edit_proof';witness_by_id={r['cell']:r for r in report['visibility_witnesses']};require(all(r['actual_changed_pixels']>0 or r['cell']in witness_by_id for r in report['moves']),'native_owner_has_no_actual_visible_geometry_edit_proof');require(all(r['actual_changed_pixels']>0 or witness_by_id.get(r['cell'],{}).get('actual_Text_edit',{}).get('actual_changed_pixels',0)>0 for r in report['text_edits']),'native_paragraph_has_no_actual_Text_and_pixel_edit_proof');report['every_native_owner_actual_pixels_edited_and_restored']=True;report['geometry_move_is_not_claimed_to_change_pixels_when_count_is_zero']=True;report['source_nonpainted_layout_owner_ids_excluded_from_effective_complexity']=sorted(witness_by_id);report['source_original_paint_classification_scope']='Only intervention-triggered owners measured; no original-paint claim is inferred for the remaining owners.';report['effective_complexity_excluded_original_Unicode_characters']=sum(r['original_source_owner_binding']['original_Unicode_characters']for r in report.get('source_zero_paint_equivalence',{}).get('rows',[]));report['original_source_XML_and_metadata_preserved']=True
    phase='final_complete_model_and_paint';snapshot=page.evaluate(script,dict(action='snapshot'));require(snapshot['whole_model_restored']and snapshot['whole_actual_paint_DOM_restored'],'native_edit_complete_model_or_DOM_not_restored');final,final_asset=screenshot(artifact/'restored.png');require(np.array_equal(final,baseline),'native_edit_final_whole_RGBA_not_exact');page.evaluate(script,dict(action='dispose'));require(not blocked,'native_editing_external_resource_request_blocked')
    report.update(ok=True,endpoint_moves=0,actual_native_object_moves=len(report['moves']),actual_native_text_edits=len(report['text_edits']),every_native_vertex_actually_moved_and_restored=len(report['moves'])==len(objects),every_native_paragraph_actual_text_and_pixels_edited_and_restored=len(report['text_edits'])==len(text_rows),whole_encoded_model_restored=True,whole_actual_native_pixels_restored_exactly=True,official_view_restore=dict(whole_model_restored=True,whole_actual_paint_DOM_restored=True,official_graph_refresh_and_validate=True),restored_png=final_asset,all_nonempty_original_paragraph_Text_nodes_edited=True)
   finally:browser.close();browser=None
  require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'native_editing_implementation_changed');report['implementation_unchanged']=True
 except Exception as e:report.update(ok=False,typed_failure=dict(phase=phase,error_type=type(e).__name__,reason=str(e)))
 report['performance']=dict(total_monotonic_seconds=time.perf_counter()-started,screenshot_seconds=screenshot_seconds,PNG_decode_seconds=image_seconds,screenshot_calls=report['screenshot_calls'],old_sequential_text_ROI_screenshot_lower_bound=3*report.get('paragraph_count',0)+5)
 save(artifact/'report.json',encoded(report))
 if artifact!=requested:save(requested/'report.json',encoded(report))
 if not report['ok']:raise ValueError('HTML_native_editing_v4_typed_failure:'+report['typed_failure']['reason']+':evidence='+str(artifact/'report.json'))
 return report
