"""Natural-coordinate PlantUML candidates and independent source-only audit.

The checker never reads producer proof/counts/DOM. It freshly prepares original
source for every B or C, then matches logical entities, connections and paint
objects by source identity/text/geometry, allowing candidate cell-ID renaming.
"""
from __future__ import annotations
import base64,collections,copy,html,io,json,math,re,subprocess,urllib.parse,uuid,zlib
from pathlib import Path
import xml.etree.ElementTree as ET
import compiler_plantuml_actual_source_v3 as source
R=source.R;W=source.W;VERSION='compiler_plantuml_natural_candidate_v8';UNIT='plantuml_flat_engine_actual_source_closed_paint_minimax_native_v8'
sha=source.sha;raw=source.raw;require=source.require
UNITS={'plantuml':UNIT}

def configuration(data_root=R):
 c=source.configuration(data_root);pins=dict(c['pins']);pins[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes())
 for name in ('auto_quality_source_vector_v2.py','tikz_execution_marker_quality.py','auto_quality_move.py','deterministic_candidate_quality_ro_v1.py','plantuml_native_minimax_v1.py','native_svg_screen_offset_v1.py','plantuml_svg_builder_v4.py','plantuml_marker_minimax_v1.py','plantuml_marker_closed_paint_v1.py','compiler_plantuml_native_paint_quality_v1.py','plantuml_native_marker_probe_v1.py','tikz_execution_binding_v2.py','svg_source_scene_dom_v1.py','svg_dom_source_scene_v1.js','plantuml_marker_grid_rule_v1.py','plantuml_marker_calibration_proof_v1.py'):
  p=W/'scripts'/name
  if not p.is_file():p=W/'prototype'/name
  pins[str(p)]=sha(p.read_bytes())
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
 return {'dom':json.loads(read('source_dom.json')),'metadata':json.loads(read('source_entity_metadata.json')),'svg':read('source.svg'),'browser_png':read('source_browser_natural.png'),'source_png':read('source_engine_padded.png')}

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
 """Independent semantic + primitive mapping, never a C expected-XML replay."""
 from auto_quality_source_vector_v2 import _style,_world_box,_paint_coverage,_graphviz_coverage
 from svg_convert_v2 import stencil
 from native_svg_screen_offset_v1 import observe,transform
 native_frame=observe(xml);xml=transform(xml,native_frame['offsets'],1)
 root=ET.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};require(len(cells)==len(list(root.iter('mxCell'))),'duplicate_candidate_cell_id')
 children=collections.defaultdict(list)
 for c in cells.values():children[c.get('parent')].append(c)
 def text_under(cid):return ''.join(_plain(c.get('value','')) for c in [cells[cid],*desc(cid)] if c.get('value'))
 def desc(cid):return [v for c in children[cid] for v in [c,*desc(c.get('id'))]]
 mapping={};source_nodes={g['uid']:g for g in metadata['groups']};entity_map={};errors=[]
 text_source=collections.defaultdict(list)
 for o in dom['objects']:
  if o['type']=='text' and o.get('node'):text_source[o['node']].append(o['text'])
 for uid,g in source_nodes.items():
  wanted=''.join(text_source[uid]);candidates=[]
  for cid,c in cells.items():
   if c.get('vertex')!='1' or text_under(cid)!=wanted:continue
   if c.get('parent') in cells and cells[c.get('parent')].get('vertex')=='1' and text_under(c.get('parent'))==wanted:continue
   candidates.append(cid)
  require(len(candidates)==1,'source_entity_missing_or_ambiguous:'+g['name']);entity_map[uid]=candidates[0];mapping[candidates[0]]='node_'+uid
 native_edges=[c for c in cells.values() if c.get('edge')=='1'];paths=[o for o in dom['objects'] if o.get('edge') and o['tag']=='path' and o['style']['fill']=='none'];require(len(paths)==len(native_edges),'source_edge_count_changed')
 edge_map={};used=set()
 for obj in paths:
  title=obj['edge']['title'];parts=re.split(r'->|--',title);require(len(parts)==2 and all(p in entity_map for p in parts),'source_edge_identity_missing')
  wanted=[o['text'] for o in dom['objects'] if (o.get('edge') or {}).get('id')==obj['edge']['id'] and o['type']=='text']
  choices=[e for e in native_edges if e.get('id') not in used and e.get('source')==entity_map[parts[0]] and e.get('target')==entity_map[parts[1]] and text_under(e.get('id'))==''.join(wanted)]
  require(len(choices)==1,'source_edge_endpoints_or_labels_changed:'+obj['id']);e=choices[0];edge_map[obj['id']]=e.get('id');mapping[e.get('id')]=obj['id'];used.add(e.get('id'))
 # Match all remaining visible primitives by independent source geometry and
 # content. The mapping never assumes producer-specific cell IDs.
 font_pairs=[];normal_shapes={}
 for obj in dom['objects']:
  if obj['type']=='shape' and obj.get('edge') and obj['tag']=='polygon':continue
  if obj['id'] in edge_map:continue
  choices=[]
  expected_shape,expected_box=stencil(obj) if obj['type']=='shape' else (None,tuple(obj['bbox'][k] for k in ('x','y','w','h')))
  for cid,c in cells.items():
   if cid in mapping or c.get('vertex')!='1' or _style(c).get('group')=='1':continue
   st=_style(c)
   try:b=_world_box(c,cells)
   except Exception:continue
   tol=2 if obj['type']=='text' else .03
   if any(abs(a-bb)>tol for a,bb in zip(b,expected_box)):continue
   if obj['type']=='text':
    if _plain(c.get('value',''))!=obj['text'] or st.get('shape')!='text':continue
   elif obj['type']=='shape':
    actual=st.get('shape','rectangle');equivalent=_decoded_shape(actual)==_decoded_shape(expected_shape)
    if not equivalent and obj['tag']=='rect' and not obj['attrs'].get('rx') and not obj['attrs'].get('ry'):
     equivalent=actual in ('rectangle','') and st.get('rounded','0')=='0' and st.get('rotation','0')=='0'
    if not equivalent:continue
   else:continue
   # Ownership is a semantic requirement, not inferred from visual proximity.
   expected_parent=entity_map.get(obj.get('node'))
   if expected_parent:
    ancestors=[];p=c.get('parent')
    while p in cells and p not in ancestors:ancestors.append(p);p=cells[p].get('parent')
    if expected_parent not in ancestors:continue
   choices.append(cid)
  require(len(choices)==1,'source_primitive_or_text_missing_ambiguous:'+obj['id']);cid=choices[0];mapping[cid]=obj['id']
  if expected_shape:normal_shapes[cid]=expected_shape
  if obj['type']=='text':font_pairs.append((obj,cid))
 # Rewrite only an audit copy after matching; the candidate is unchanged.
 original_ids={c:c.get('id') for c in root.iter('mxCell')}
 for c,cid in original_ids.items():
  c.set('id',mapping.get(cid,'unmapped_'+str(cid)) if cid not in ('0','1') else cid)
  for attr in ('source','target','parent'):
   old=c.get(attr)
   if old in mapping:c.set(attr,mapping[old])
   elif old not in (None,'0','1'):c.set(attr,'unmapped_'+str(old))
  if cid in normal_shapes:
   st=_style(c);st['shape']=normal_shapes[cid];c.set('style',';'.join(k+'='+v for k,v in st.items())+';')
 normalized=ET.tostring(root,encoding='unicode');derived_stats={'native_graphviz_arrowheads':[{'source_arrow_object':o['id']} for o in dom['objects'] if o['type']=='shape' and o.get('edge') and o['tag']=='polygon']}
 graph=_graphviz_coverage(dom,normalized,derived_stats);paint=_paint_coverage(dom,normalized)
 require(abs(paint['source_layout_translation']['dx'])<=.03 and abs(paint['source_layout_translation']['dy'])<=.03,'candidate_source_origin_moved')
 errors.extend(graph['errors']);errors.extend(paint['errors'])
 return {'ok':not errors,'errors':errors,'graph':graph,'paint':paint,'candidate_to_source_mapping':mapping,'font_pairs':font_pairs,'edge_map':edge_map,'normalized_xml':normalized,'cells':cells}

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
 from compiler_plantuml_native_paint_quality_v1 import verify
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
   expected=_source_font(obj);st=_style(match['cells'][cid]);family=st.get('fontFamily');require(family in embedded,'source_font_not_embedded');actual=embedded[family];glyph_count+=_glyphs(expected,actual,obj['text']);require(expected['postscript_names']&actual['postscript_names'],'source_physical_font_face_changed')
   if native_info is not None:
    fonts=[f for f in usage.get(cid,[]) if f.get('glyphCount',0)>0];require(fonts and all(f.get('isCustomFont') and f.get('postScriptName') in expected['postscript_names'] for f in fonts),'actual_source_font_face_or_glyph_fallback_changed')
   font_evidence.append({'cell':cid,'source_font_sha256':expected['sha256'],'embedded_font_sha256':actual['sha256'],'source_postscript_names':sorted(expected['postscript_names']),'characters':len(obj['text'])})
  for f in embedded.values():f['font'].close()
  if native_png is None:
   from native_worker import native
   w,h=proof['reference_size'];render=native.native_job(xml,w,h,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(render['ok'],'fresh_native_render_failed');native_png=render['png']
  marker=_marker_gate(data,xml,match,native_png,proof['reference_size']);out['failures'].extend(marker['failures'])
  text_ids=[cid for _,cid in match['font_pairs']];out['evidence']={'complete_source_coverage':match['ok'],'required_text_cell_ids':text_ids,'candidate_code_sha256':record['code_sha256'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'fresh_source_proof':proof,'semantic_and_paint':{k:v for k,v in match.items() if k not in ('font_pairs','normalized_xml','cells')},'source_glyphs_verified':glyph_count,'physical_fonts':font_evidence,'source_native_markers':marker,'producer_Cproof_consulted':False,'candidate_IDs_may_be_renamed':True};out['ok']=not out['failures']
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
 return {'ok':True,'profile':VERSION+'_editing','endpoint_moves':len(r['moves']),'details':r,'actual_source_marker_endpoint_rotation_and_restoration':markers}

def convert(record,job,work):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 from plantuml_native_minimax_v1 import build
 from portable_native_fonts import ready_page,capture,embed
 from native_worker import native
 from strict_canvas_gate import require_declared_page
 work=Path(work).resolve();require(work.is_relative_to(W/VERSION),'unowned_candidate_work');work.mkdir(parents=True,exist_ok=False);out={'ok':False,'qualified':False,'model_calls':0}
 try:
  j=source.base._job(job);src,code,ref=source.base._inputs(record,j);proof=prepare_source(j,W/source.VERSION/'candidate_sources'/src['pair_sha256']/uuid.uuid4().hex);require(proof['ok'],'source_reference_not_reproduced:'+str(proof['reason']));data=_source_data(proof);w,h=proof['reference_size'];xml,stats=build(data['dom'],w,h,data['metadata'])
  from native_svg_screen_offset_v1 import observe,transform
  native_frame=observe(xml);xml=transform(xml,native_frame['offsets'],-1)
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=source.base.CHROME,args=['--disable-dev-shm-usage'])
   try:
    page=ready_page(browser)
    try:observations=capture(page,xml);candidate,fonts,fontproof=embed(xml,observations,work/'fonts');require(not fontproof['issues'],'source_font_embedding_unsupported')
    finally:page.close()
   finally:browser.close()
  renders=[]
  for value in (xml,candidate):
   r=native.native_job(value,w,h,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(r['ok'],'native_render_failed');require_declared_page(r['native_render'],w,h);renders.append(r)
  require(renders[0]['png']==renders[1]['png'],'font_embedding_changed_native_pixels');dest=R/'clean'/VERSION/src['pair_sha256'][:2]/src['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True)
  payloads={'diagram.drawio':candidate.encode(),'image.png':renders[1]['png'],'original_source.puml':code,'original_reference.png':ref,'source.svg':data['svg'],'source.png':data['source_png'],'source_dom.json':raw(data['dom']),'font_proof.json':raw(fontproof),'source_proof.json':raw(proof)}
  for name,b in payloads.items():(dest/name).write_bytes(b)
  for f in fonts.values():
   for k,d in [('file','sha256'),('original_file','original_sha256')]:
    b=Path(f[k]).read_bytes();require(sha(b)==f[d],'font_bytes_changed');p=dest/(k+'_'+f[d]+Path(f[k]).suffix);p.write_bytes(b);f[k]=str(p.relative_to(R))
  cells=list(ET.fromstring(candidate).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];config=configuration()
  proposed={'id':src['pair_sha256'],'source_pair_sha256':src['pair_sha256'],'source':src['source'],'category':src['category'],'source_format':'plantuml','format':'drawio','source_record':src,'source_code_sha256':src['code_sha256'],'source_image_sha256':src['image_sha256'],'code_file':str((dest/'diagram.drawio').relative_to(R)),'code_sha256':sha(candidate.encode()),'image_file':str((dest/'image.png').relative_to(R)),'image_sha256':sha(renders[1]['png']),'original_source_code':str((dest/'original_source.puml').relative_to(R)),'original_reference':str((dest/'original_reference.png').relative_to(R)),'source_render_svg':str((dest/'source.svg').relative_to(R)),'source_render_svg_sha256':sha(data['svg']),'source_render_png':str((dest/'source.png').relative_to(R)),'source_render_png_sha256':sha(data['source_png']),'native_embedded_fonts':list(fonts.values()),'conversion_method':VERSION,'quality_state':'pending_independent_full_quality','model':None,'model_calls':0,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'svg_conversion':stats,'accepted':False,'candidate_quality_adapter':{'file':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes()),'policy':config['policy']}}
  (dest/'record.json').write_bytes(raw(proposed));out.update(ok=True,record=proposed,record_file=str(dest/'record.json'),reason='native_candidate_pending_independent_QA')
 except Exception as e:out.update(reason=str(e).split(':',1)[0],detail=str(e)[:2500])
 (work/'result.json').write_bytes(raw(out));return out
