"""Natural-coordinate PlantUML candidates and independent source-only audit.

The checker never reads producer proof/counts/DOM. It freshly prepares original
source for every B or C, then matches logical entities, connections and paint
objects by source identity/text/geometry, allowing candidate cell-ID renaming.
"""
from __future__ import annotations
import base64,collections,copy,html,io,json,math,re,subprocess,urllib.parse,uuid,zlib
from pathlib import Path
import xml.etree.ElementTree as ET
import compiler_plantuml_engine_surface_source_v1 as source
R=source.R;W=source.W;VERSION='compiler_plantuml_engine_surface_candidate_v1';UNIT='plantuml_official_Cuca_complete_source_surface_and_shadow_scene_native_v1'
sha=source.sha;raw=source.raw;require=source.require
UNITS={'plantuml':UNIT}

def configuration(data_root=R):
 c=source.configuration(data_root);pins=dict(c['pins']);pins[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes())
 for name in ('auto_quality_source_vector_v2.py','tikz_execution_marker_quality.py','auto_quality_move.py','deterministic_candidate_quality_ro_v1.py','plantuml_native_minimax_v1.py','native_svg_screen_offset_v1.py','plantuml_svg_builder_v4.py','plantuml_marker_minimax_v1.py','plantuml_marker_closed_paint_v1.py','compiler_plantuml_native_paint_quality_v1.py','plantuml_native_marker_probe_v1.py','tikz_execution_binding_v2.py','svg_source_scene_dom_v1.py','svg_dom_source_scene_v1.js','plantuml_marker_grid_rule_v1.py','plantuml_marker_calibration_proof_v1.py','plantuml_engine_surface_native_v1.py','plantuml_engine_surface_scene_quality_v1.py','plantuml_engine_text_layout_v1.py','plantuml_engine_native_editing_v1.py','plantuml_engine_marker_probe_v1.py','compiler_plantuml_engine_marker_quality_v1.py','plantuml_engine_surface_export_v1.py','plantuml_engine_surface_renderer_v1.py','compiler_plantuml_engine_surface_quality_ro_v1.py'):
  p=W/'scripts'/name
  if not p.is_file():p=W/'prototype'/name
  pins[str(p)]=sha(p.read_bytes())
 from plantuml_engine_surface_export_v1 import RENDERER
 pins[str(RENDERER)]=sha(RENDERER.read_bytes())
 from plantuml_marker_calibration_proof_v1 import verified
 calibration=verified();pins.update(calibration['pins'])
 import scipy.optimize._slsqp_py as optimizer
 for p in [Path(optimizer.__file__),*Path(optimizer.__file__).parent.glob('_slsqp*.so')]:pins[str(p)]=sha(p.read_bytes())
 return {'policy':VERSION+':'+sha(raw(pins))[:20],'pins':pins,'source_requires_native_info':True,'unit':UNIT,'source_policy':c['policy'],'candidate_proof_required':False,'automatic_rollout':False,'unseen_ready':False,'marker_calibration':{k:v for k,v in calibration.items() if k!='pins'}}

def static_support(record_or_job):return {**source.static_support(record_or_job),'unit':UNIT}
def prepare_source(record_or_job,work):return source.prepare_source(record_or_job,work)
def source_reproduction(record_or_job,work):return source.source_reproduction(record_or_job,work)

def _source_data(proof):
 require(proof.get('ok'),'source_reference_not_reproduced:'+str(proof.get('reason')))
 files=proof['source_artifacts']
 def read(name):return source.base._read(files[name])
 return {'dom':json.loads(read('source_dom.json')),'metadata':json.loads(read('source_entity_metadata.json')),'svg':read('source.svg'),'browser_png':read('source_browser_natural.png'),'source_png':read('source_engine_padded.png'),'original_reference':read('original_reference.png'),'ir':json.loads(read('source_engine_IR.json')),'source_surface_plan':proof['source_surface_inspection']['plan']}

def _plain(v):
 from auto_quality_source_vector_v2 import _plain as plain
 return plain(v)

def _decoded_shape(shape):
 if not shape.startswith('stencil('):return shape
 b=base64.b64decode(shape[8:-1]);text=urllib.parse.unquote(zlib.decompress(b,-15).decode());return ET.canonicalize(text)

def _fonts(xml):
 """Read actual embedded font bytes from XML; candidate metadata is irrelevant."""
 from fontTools.ttLib import TTFont
 model=ET.fromstring(xml).find('.//mxGraphModel');pairs=[]
 for item in (model.get('extFonts') or '').split('|'):
  if '^' in item:pairs.append(item.split('^',1))
 out={}
 for family,uri in pairs:
  require(uri.startswith('data:font/') and ';base64,' in uri,'unproved_embedded_font_uri');b=base64.b64decode(uri.split(',',1)[1],validate=True);ft=TTFont(io.BytesIO(b));ps={n.toUnicode() for n in ft['name'].names if n.nameID==6};out[family]={'bytes':b,'sha256':sha(b),'postscript_names':ps,'font':ft}
 return out

def _source_font(obj):
 """The source helper resolved one actual physical family, no glyph fallback."""
 family=obj['fontFamily'].split(',')[0].strip('"\'');style=('Bold' if obj.get('bold') else '')+(' Italic' if obj.get('italic') else '')
 pattern=family+(':style='+style.strip() if style.strip() else '')
 line=subprocess.check_output(['fc-match','-f','%{file}\t%{index}\n',pattern],text=True).splitlines()[0];path,index=line.split('\t');require(int(index or 0)==0 and Path(path).suffix.lower() in ('.ttf','.otf'),'source_font_collection_or_format_unsupported');b=Path(path).read_bytes()
 from fontTools.ttLib import TTFont
 ft=TTFont(io.BytesIO(b));ps={n.toUnicode() for n in ft['name'].names if n.nameID==6};cmap=ft.getBestCmap();require(all(ord(ch) in cmap for ch in obj['text'] if not ch.isspace()),'source_font_lacks_unicode_glyph')
 return {'file':path,'sha256':sha(b),'postscript_names':ps,'font':ft,'family':family}

def _glyphs(expected,actual,text):
 """Verify each logical source Unicode maps to the same contour and advance."""
 from fontTools.pens.recordingPen import RecordingPen
 a,b=expected['font'],actual['font'];ac,bc=a.getBestCmap(),b.getBestCmap();ags,bgs=a.getGlyphSet(),b.getGlyphSet();count=0
 for ch in text:
  if ch.isspace():continue
  cp=ord(ch);require(cp in ac and cp in bc,'source_unicode_glyph_missing');pa,pb=RecordingPen(),RecordingPen();ags[ac[cp]].draw(pa);bgs[bc[cp]].draw(pb);require(pa.value==pb.value,'source_glyph_contour_changed');require(a['hmtx'][ac[cp]]==b['hmtx'][bc[cp]],'source_glyph_advance_changed');count+=1
 return count

def _match_candidate(dom,metadata,xml):
 from plantuml_engine_surface_scene_quality_v1 import match
 return match(dom,metadata,xml)

def _marker_raster_gate(data,xml,match,native_png,size):
 """Fixed source/native marker contour gate, without case-specific waivers."""
 import numpy as np
 from PIL import Image
 from scipy.ndimage import binary_erosion,distance_transform_edt
 from tikz_execution_marker_quality import _mask,_color
 from auto_quality_source_vector_v2 import _style
 # Natural SVG's proved empty extra row/column can be omitted; all paint was
 # independently proved within this fixed reference viewport before this step.
 a=np.asarray(Image.open(io.BytesIO(data['browser_png'])).convert('RGB'))[:size[1],:size[0]];b=np.asarray(Image.open(io.BytesIO(native_png)).convert('RGB'));require(a.shape==b.shape,'marker_reference_canvas_mismatch');details=[]
 dom=data['dom'];paths=[o for o in dom['objects'] if o.get('edge') and o['tag']=='path' and o['style']['fill']=='none']
 for arrow in [o for o in dom['objects'] if o.get('edge') and o['tag']=='polygon']:
  candidates=[o for o in paths if o['edge']['id']==arrow['edge']['id']];require(len(candidates)==1,'source_marker_path_ambiguous');path=candidates[0];center=[arrow['bbox']['x']+arrow['bbox']['w']/2,arrow['bbox']['y']+arrow['bbox']['h']/2];dist=[math.dist(center,path['sampledPoints'][i]) for i in (0,-1)];require(abs(dist[0]-dist[1])>=1,'source_marker_side_ambiguous');side='start' if dist[0]<dist[1] else 'end';cell=match['cells'][match['edge_map'][path['id']]];st=_style(cell);require(st.get(side+'Arrow','none')!='none','source_marker_detached')
  box=arrow['bbox'];x0=max(0,math.floor(box['x'])-3);y0=max(0,math.floor(box['y'])-3);x1=min(size[0],math.ceil(box['x']+box['w'])+3);y1=min(size[1],math.ceil(box['y']+box['h'])+3);expected=_color(arrow['style']['fill']);am=_mask(a[y0:y1,x0:x1],expected);bm=_mask(b[y0:y1,x0:x1],expected)
  require(am.any() and bm.any(),'source_marker_ink_missing');aa=am&~binary_erosion(am,structure=np.ones((3,3)),border_value=0);bb=bm&~binary_erosion(bm,structure=np.ones((3,3)),border_value=0);distance=float(max(distance_transform_edt(~bb)[aa].max(),distance_transform_edt(~aa)[bb].max()));ratio=float(bm.sum()/am.sum());ok=distance<=1+1e-8 and .8<=ratio<=1.25;details.append({'source_arrow':arrow['id'],'native_edge':cell.get('id'),'side':side,'boundary_distance_px':distance,'ink_area_ratio':ratio,'ok':ok})
 return {'ok':all(r['ok'] for r in details),'markers':details,'policy':'source_marker_boundary_1px_ink_area_0.8_1.25_no_case_waiver','failures':[] if all(r['ok'] for r in details) else [{'reason':'source_native_marker_contour_changed'}]}

def _marker_gate(data,xml,match,native_png,size):
 if not any(o.get('edge') and o['tag']=='polygon' for o in data['dom']['objects']):
  from auto_quality_source_vector_v2 import _style
  require(all(_style(c).get(side+'Arrow','none') in ('none','') for c in ET.fromstring(xml).iter('mxCell') if c.get('edge')=='1' for side in ('start','end')),'undeclared_native_marker')
  return {'ok':True,'markers':[],'failures':[],'policy':'complete_actual_source_marker_inventory_is_zero','actual_full_closed_marker_paint_and_editing':{'ok':True,'markers':[],'code_sha256':sha(xml.encode()),'no_original_markers_and_no_native_markers':True}}
 from compiler_plantuml_engine_marker_quality_v1 import verify
 from plantuml_marker_grid_rule_v1 import decision,POLICY
 result=_marker_raster_gate(data,xml,match,native_png,size);actual=verify(data,xml,match);result['actual_full_closed_marker_paint_and_editing']=actual
 rows={(m['source_arrow'],m['native_edge'],m['side']):m for m in actual['markers']}
 for marker in result['markers']:
  key=(marker['source_arrow'],marker['native_edge'],marker['side']);require(key in rows,'actual_source_marker_inventory_incomplete');physical=rows[key]
  require(physical['actual_bound_move_and_shaft_rotation'],'actual_native_marker_editing_failed');require(len(physical['source_polygon'])==len(physical['actual_native_polygon']),'source_native_marker_polygon_topology_changed')
  # verify() above independently requires equal opaque fill/stroke colors,
  # widths, joins and miter limits. No producer metadata supplies this flag.
  verdict=decision(marker['boundary_distance_px'],marker['ink_area_ratio'],physical['continuous_full_paint_certificate'],opaque_paint_style_equivalent=True)
  if len(physical['source_polygon'])!=4:
   verdict.update(ok=physical['ok'] and marker['boundary_distance_px']<=1+1e-8 and .8<=marker['ink_area_ratio']<=1.25,grid_alias_eligible=False,grid_alias_used=False,raster_grid_cap_px=1.,policy='unchanged_triangular_native_marker_one_pixel_raster_with_full_paint_proof')
  marker.update(verdict)
 result['ok']=actual['ok'] and bool(result['markers']) and all(m['ok'] for m in result['markers']);result['failures']=[] if result['ok'] else [{'reason':'source_native_marker_full_paint_or_grid_rule_failed'}];result['policy']=POLICY;result['unchanged_physical_closed_paint_cap_px']=1.;result['unchanged_ink_area_ratio']=[.8,1.25];result['calibration_required_and_pinned']=True
 return result


def validate_source(record,xml,native_info=None,native_png=None):
 out={'profile':VERSION,'supported':True,'ok':False,'failures':[],'evidence':{}}
 try:
  require(sha(xml.encode())==record['code_sha256'],'candidate_hash_changed');require(record['source_format']=='plantuml','requires_plantuml')
  proof=prepare_source(record,W/source.VERSION/'independent_candidate_checks'/record['id']/uuid.uuid4().hex);require(proof['ok'],'source_reference_not_reproduced:'+str(proof['reason']));data=_source_data(proof);match=_match_candidate(data['dom'],data['metadata'],xml);out['failures'].extend(match['errors']);require(match['ok'],'independent_source_semantic_or_paint_failed')
  embedded=_fonts(xml);glyph_count=0;font_evidence=[]
  usage={r['cell']:r.get('fonts',[]) for r in (native_info or {}).get('actual_platform_font_usage',[])}
  from auto_quality_source_vector_v2 import _style
  for obj,cid in match['font_pairs']:
   expected=_source_font(obj);st=_style(match['cells'][cid]);family=st.get('fontFamily');require(family in embedded,'source_font_not_embedded');actual=embedded[family];glyph_count+=_glyphs(expected,actual,obj['text']);require(expected['postscript_names']&actual['postscript_names'],'source_physical_font_face_changed');physical=actual['font'];physical_bold=bool(physical['OS/2'].fsSelection&0x20) if 'OS/2' in physical else bool(physical['head'].macStyle&1);physical_italic=bool(physical['OS/2'].fsSelection&1) if 'OS/2' in physical else bool(physical['head'].macStyle&2);expected_flags=(1 if obj.get('bold') and not physical_bold else 0)|(2 if obj.get('italic') and not physical_italic else 0);require(int(st.get('fontStyle',0))&3==expected_flags,'source_physical_font_synthetic_style_changed')
   if native_info is not None:
    fonts=[f for f in usage.get(cid,[]) if f.get('glyphCount',0)>0];require(fonts and all(f.get('isCustomFont') and f.get('postScriptName') in expected['postscript_names'] for f in fonts),'actual_source_font_face_or_glyph_fallback_changed')
   font_evidence.append({'cell':cid,'source_font_sha256':expected['sha256'],'embedded_font_sha256':actual['sha256'],'source_postscript_names':sorted(expected['postscript_names']),'characters':len(obj['text'])})
  for f in embedded.values():f['font'].close()
  if native_png is None:
   from plantuml_engine_surface_export_v1 import render as surface_render
   w,h=proof['reference_size'];render=surface_render(xml,[w,h]);require(render['ok'],'fresh_native_render_failed');native_png=render['png']
  # Keep the visual acceptance unit fixed to each complete SOURCE label. HTML
  # producer span boundaries must never split one original line into easier
  # independently registered text fragments.
  from auto_quality_common_v4 import image_quality
  source_label_positions=[]
  for obj,cid in match['font_pairs']:
   b=obj['bbox'];source_label_positions.append({'cell':cid,'runs':[{'chars':[{'text':obj['text'],'x':b['x'],'y':b['y'],'width':b['w'],'height':b['h']}]}]})
  source_label_visual=image_quality(data['original_reference'],native_png,{},source_label_positions);require(source_label_visual['ok'],'complete_source_label_original_reference_visual_failed')
  require(native_info is not None,'actual_source_grapheme_native_observation_required')
  from plantuml_engine_text_layout_v1 import plans,audit,verify_labels
  source_plans=plans(data['dom']);text_mapping={o['id']:cid for o,cid in match['font_pairs']};verify_labels(xml,source_plans,text_mapping);text_layout=audit(source_plans,native_info,text_mapping)
  from plantuml_engine_surface_export_v1 import verify_declaration,require_native_render
  verify_declaration(xml,data['source_surface_plan']);require_native_render(native_info,*proof['reference_size'])
  native_effects=native_info['actual_dom_paint_bounds'].get('source_shadow_effects',[]);require({r['cell']for r in native_effects}=={r['native_cell']for r in match['source_effects']['rows']},'actual_source_native_shadow_effect_inventory_changed')
  marker=_marker_gate(data,xml,match,native_png,proof['reference_size']);out['failures'].extend(marker['failures'])
  text_ids=[cid for _,cid in match['font_pairs']];out['evidence']={'complete_source_coverage':match['ok'],'required_text_cell_ids':text_ids,'candidate_code_sha256':record['code_sha256'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'fresh_source_proof':proof,'semantic_and_paint':{k:v for k,v in match.items() if k not in ('font_pairs','normalized_xml','cells')},'source_glyphs_verified':glyph_count,'physical_fonts':font_evidence,'source_native_markers':marker,'fresh_source_grapheme_layout':text_layout,'complete_source_label_reference_visual':source_label_visual,'producer_Cproof_consulted':False,'candidate_IDs_may_be_renamed':True};out['ok']=not out['failures']
 except Exception as e:out['failures'].append({'reason':str(e).split(':',1)[0],'detail':str(e)[:2500]})
 return out

def check_source(record,xml,original_source,data_root,native_info=None):
 require(Path(data_root).resolve()==R,'requires_registered_root');require(sha(original_source.encode())==record['source_code_sha256'],'source_argument_changed');return validate_source(record,xml,native_info=native_info)

def audit_editing(record,xml,profile,data_root):
 from auto_quality_move import audit
 require(profile.get('ok') and profile['evidence']['candidate_code_sha256']==sha(xml.encode()),'editing_requires_current_source_profile');markers=profile['evidence']['source_native_markers']['actual_full_closed_marker_paint_and_editing'];require(markers['ok'] and markers['code_sha256']==sha(xml.encode()),'actual_full_closed_marker_geometry_and_direction_proof_missing');r=audit(xml);expected=sum(c.get('edge')=='1' for c in ET.fromstring(xml).iter('mxCell'));require(len(r['moves'])==2*expected,'endpoint_editing_coverage_incomplete')
 for m in r['moves']:
  require(abs(m['delta']['x']-17)<.05 and abs(m['delta']['y']-11)<.05,'edge_endpoint_did_not_follow')
  require(all(abs(v['x']-17)<.05 and abs(v['y']-11)<.05 for v in m['child_deltas']),'terminal_child_did_not_follow')
  for label in m['label_member_deltas']:
   members=label['members'];require(not members or all(abs(v[k]-members[0][k])<.05 for v in members for k in ('x','y')),'edge_child_label_group_split')
 from plantuml_engine_native_editing_v1 import audit as all_entities
 groups=list(profile['evidence']['semantic_and_paint']['engine_entities'].values());entities=all_entities(xml,groups);require(entities['ok'] and entities['entities_checked']==len(groups),'actual_every_engine_entity_or_container_move_failed')
 return {'ok':True,'profile':VERSION+'_editing','endpoint_moves':len(r['moves']),'details':r,'actual_source_marker_endpoint_rotation_and_restoration':markers,'actual_every_engine_entity_container_and_owned_paint_editing':entities}

def convert(record,job,work):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 from plantuml_engine_surface_native_v1 import build
 from portable_native_fonts import ready_page,capture,embed
 from native_worker import native
 from plantuml_engine_surface_export_v1 import render as surface_render,declare,geometry_identity,require_native_render
 work=Path(work).resolve();require(work.is_relative_to(W/VERSION),'unowned_candidate_work');work.mkdir(parents=True,exist_ok=False);out={'ok':False,'qualified':False,'model_calls':0}
 try:
  j=source.base._job(job);src,code,ref=source.base._inputs(record,j);proof=prepare_source(j,W/source.VERSION/'candidate_sources'/src['pair_sha256']/uuid.uuid4().hex);require(proof['ok'],'source_reference_not_reproduced:'+str(proof['reason']));data=_source_data(proof);w,h=proof['reference_size'];xml,stats=build(data['dom'],w,h,data['metadata'])
  from native_svg_screen_offset_v1 import observe,transform
  native_frame=observe(xml);xml=transform(xml,native_frame['offsets'],-1);before_declaration=xml;xml=declare(xml,data['source_surface_plan']);geometry_identity(before_declaration,xml)
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=source.base.CHROME,args=['--disable-dev-shm-usage'])
   try:
    page=ready_page(browser)
    try:observations=capture(page,xml);candidate,fonts,fontproof=embed(xml,observations,work/'fonts');require(not fontproof['issues'],'source_font_embedding_unsupported')
    finally:page.close()
   finally:browser.close()
  renders=[]
  for value in (xml,candidate):
   r=surface_render(value,[w,h]);require(r['ok'],'native_render_failed');require_native_render(r['native_render'],w,h);renders.append(r)
  require(renders[0]['png']==renders[1]['png'],'font_embedding_changed_native_pixels')
  from plantuml_engine_text_layout_v1 import plans,apply,audit
  source_plans=plans(data['dom']);candidate=apply(candidate,source_plans)
  spaced=surface_render(candidate,[w,h]);require(spaced['ok'],'native_spacing_render_failed');require_native_render(spaced['native_render'],w,h);(work/'native_text_candidate_before_origin.drawio').write_text(candidate);(work/'native_text_before_origin.json').write_bytes(raw(spaced['native_render']));(work/'source_text_plans.json').write_bytes(raw(source_plans));origin=audit(source_plans,spaced['native_render'],allow_origin=True);candidate=apply(candidate,source_plans,origin['whole_run_origin'])
  aligned=surface_render(candidate,[w,h]);require(aligned['ok'],'native_origin_render_failed');require_native_render(aligned['native_render'],w,h);(work/'native_text_candidate_aligned.drawio').write_text(candidate);(work/'native_text_aligned.json').write_bytes(raw(aligned['native_render']));textproof=audit(source_plans,aligned['native_render']);renders[1]=aligned
  dest=R/'clean'/VERSION/src['pair_sha256'][:2]/src['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True)
  payloads={'diagram.drawio':candidate.encode(),'image.png':renders[1]['png'],'original_source.puml':code,'original_reference.png':ref,'source.svg':data['svg'],'source.png':data['source_png'],'source_dom.json':raw(data['dom']),'source_engine_IR.json':raw(data['ir']),'text_layout_proof.json':raw(textproof),'font_proof.json':raw(fontproof),'source_proof.json':raw(proof)}
  for name,b in payloads.items():(dest/name).write_bytes(b)
  for f in fonts.values():
   for k,d in [('file','sha256'),('original_file','original_sha256')]:
    b=Path(f[k]).read_bytes();require(sha(b)==f[d],'font_bytes_changed');p=dest/(k+'_'+f[d]+Path(f[k]).suffix);p.write_bytes(b);f[k]=str(p.relative_to(R))
  cells=list(ET.fromstring(candidate).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];config=configuration()
  proposed={'id':src['pair_sha256'],'source_pair_sha256':src['pair_sha256'],'source':src['source'],'category':src['category'],'source_format':'plantuml','format':'drawio','source_record':src,'source_code_sha256':src['code_sha256'],'source_image_sha256':src['image_sha256'],'code_file':str((dest/'diagram.drawio').relative_to(R)),'code_sha256':sha(candidate.encode()),'image_file':str((dest/'image.png').relative_to(R)),'image_sha256':sha(renders[1]['png']),'original_source_code':str((dest/'original_source.puml').relative_to(R)),'original_reference':str((dest/'original_reference.png').relative_to(R)),'source_render_svg':str((dest/'source.svg').relative_to(R)),'source_render_svg_sha256':sha(data['svg']),'source_render_png':str((dest/'source.png').relative_to(R)),'source_render_png_sha256':sha(data['source_png']),'native_embedded_fonts':list(fonts.values()),'conversion_method':VERSION,'quality_state':'pending_independent_full_quality','model':None,'model_calls':0,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'svg_conversion':stats,'accepted':False,'candidate_quality_adapter':{'file':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes()),'policy':config['policy']}}
  (dest/'record.json').write_bytes(raw(proposed));out.update(ok=True,record=proposed,record_file=str(dest/'record.json'),reason='native_candidate_pending_independent_QA')
 except Exception as e:out.update(reason=str(e).split(':',1)[0],detail=str(e)[:2500])
 (work/'result.json').write_bytes(raw(out));return out
