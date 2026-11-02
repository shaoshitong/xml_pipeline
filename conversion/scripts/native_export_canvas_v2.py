"""Normalize a native source's tight export without changing any source paint.

The only permitted change is an integer translation of all layer-root geometry
and declared page dimensions. The reference determines size and ink origin;
there is no search, scaling or fitted object geometry. Both full-paint equality
and unchanged original-reference image metrics are required separately.
"""
import copy,hashlib,io,json,math,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
OWNER=R/'conversion/native_export_canvas_v2'
SCHEMA='original_native_export_translation_full_paint_v2'
RASTER_ROUNDOFF_CHANNEL_LIMIT=2
FOREGROUND_WHITE_THRESHOLD=250
GLYPH_TRANSLATION_TOLERANCE=1e-6
LABEL_ROUNDING_LIMIT=1.01
SOURCE_VIEW_RENDERER_SHA256='5594c647be77dba616fe07e0bcb9c12e22b9831ea93fcda972a3c110f9e7836a'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def pixels(blob):
 from PIL import Image
 im=Image.open(io.BytesIO(blob)).convert('RGBA');background=Image.new('RGBA',im.size,'white');background.alpha_composite(im);return background.convert('RGB')
def bbox(im):
 import numpy as np
 a=np.asarray(im);y,x=np.nonzero(np.min(a,axis=2)<250);require(len(x)>0,'native_export_blank_paint');return [int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]
def translate(xml,dx,dy,size):
 from native_source_font_profile_v4 import _models,_cells
 root,model=_models(xml);cells=_cells(root);layers={cid for cid,c in cells.items() if c.get('parent')=='0' and c.get('vertex')!='1' and c.get('edge')!='1'}|{'1'}
 def number(n):return str(int(n)) if float(n).is_integer() else format(n,'.15g')
 for cid,c in cells.items():
  if c.get('parent') not in layers:continue
  g=c.find('mxGeometry')
  if g is None:continue
  if c.get('vertex')=='1' and g.get('relative','0')!='1':
   for k,d in [('x',dx),('y',dy)]:g.set(k,number(float(g.get(k,0))+d))
  elif c.get('vertex')=='1':
   # A relative layer-root vertex cannot be translated without a viewport.
   raise ValueError('native_export_relative_root_vertex_requires_viewport_support')
  if c.get('edge')=='1':
   points=[p for p in g.findall('mxPoint') if p.get('as') in ('sourcePoint','targetPoint')]
   points += list(g.findall("Array[@as='points']/mxPoint"))
   for p in points:
    for k,d in [('x',dx),('y',dy)]:p.set(k,number(float(p.get(k,0))+d))
 model.set('pageWidth',str(int(size[0])));model.set('pageHeight',str(int(size[1])))
 return E.tostring(root,encoding='unicode')
def exact_shift(before,after,dx,dy):
 import numpy as np
 from PIL import Image
 a=pixels(before);b=pixels(after);outside=np.min(np.asarray(a),axis=2)<255
 x0=max(0,-dx);y0=max(0,-dy);x1=min(a.width,b.width-dx);y1=min(a.height,b.height-dy)
 if x1>x0 and y1>y0:outside[y0:y1,x0:x1]=False
 require(not outside.any(),'native_export_translation_would_crop_source_paint')
 shifted=Image.new('RGB',b.size,'white');shifted.paste(a,(dx,dy))
 a1=np.asarray(shifted);b1=np.asarray(b);error=np.abs(a1.astype('int16')-b1.astype('int16'))
 require(np.array_equal(np.min(a1,axis=2)<FOREGROUND_WHITE_THRESHOLD,np.min(b1,axis=2)<FOREGROUND_WHITE_THRESHOLD),'native_export_translation_changes_foreground_mask')
 require(int(error.max())<=RASTER_ROUNDOFF_CHANNEL_LIMIT,'native_export_translation_exceeds_renderer_roundoff')
 return {'all_original_nonwhite_paint_preserved':True,'exact_translated_pixels':not bool(error.any()),'nonwhite_source_paint_clipped':0,'maximum_channel_roundoff':int(error.max()),'channel_roundoff_limit':RASTER_ROUNDOFF_CHANNEL_LIMIT,'changed_pixels':int(np.any(error,axis=2).sum()),'foreground_mask_exact':True}
def verify_render_translation(before,after,dx,dy):
 from native_source_font_profile_v4 import signature
 require(signature(before['actual_platform_font_usage'])==signature(after['actual_platform_font_usage']),'native_export_translation_changes_physical_font_glyph_counts')
 a={r['cell']:[c for run in r.get('runs',[]) for c in run.get('chars',[])] for r in before['actual_text_positions']};b={r['cell']:[c for run in r.get('runs',[]) for c in run.get('chars',[])] for r in after['actual_text_positions']}
 require(a.keys()==b.keys(),'native_export_translation_changes_text_scope')
 glyphs=0
 for cid,chars in a.items():
  require(len(chars)==len(b[cid]),'native_export_translation_changes_glyph_count')
  for c,n in zip(chars,b[cid]):
   require(c.get('text')==n.get('text'),'native_export_translation_changes_text')
   for key,delta in [('x',dx),('y',dy),('width',0),('height',0)]:require(abs(float(n[key])-float(c[key])-delta)<=GLYPH_TRANSLATION_TOLERANCE,'native_export_translation_changes_actual_glyph_geometry')
   glyphs+=1
 for field in ('graphBounds',):
  for key,delta in [('x',dx),('y',dy),('width',0),('height',0)]:require(abs(float(after[field][key])-float(before[field][key])-delta)<=GLYPH_TRANSLATION_TOLERANCE,'native_export_translation_changes_actual_graph_bounds')
 return {'actual_graphemes':glyphs,'actual_graphemes_exactly_translated':True,'actual_physical_font_counts_unchanged':True,'actual_graph_bounds_exactly_translated':True}

def render(xml,size):
 from native_worker import native
 out=native.native_job(xml,*size,180,R/'conversion/rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 require(out.get('ok'),'native_export_render_failed')
 audit=out['native_render'].get('outside_page_pixel_audit') or {}
 require(audit.get('white_threshold')==255 and audit.get('nonwhite_outside_pixels')==0,'native_export_original_or_current_paint_outside_page')
 return out

def export_plan(reference,baseline):
 size=list(pixels(reference).size);basebox=bbox(pixels(baseline['png']));refbox=bbox(pixels(reference))
 require(all(abs((refbox[i+2]-refbox[i])-(basebox[i+2]-basebox[i]))<=max(3,.02*(basebox[i+2]-basebox[i])) for i in (0,1)),'native_export_reference_content_extent_requires_other_conversion')
 bounds=baseline['native_render']['graphBounds'];bx=(size[0]-math.ceil(bounds['width']))/2;by=(size[1]-math.ceil(bounds['height']))/2
 if 0<=bx<=64 and abs(bx-by)<1e-8 and abs(bx-round(bx))<1e-8:
  return bx-bounds['x'],by-bounds['y'],size,basebox,refbox,'official_graph_bounds_uniform_border'
 return refbox[0]-basebox[0],refbox[1]-basebox[1],size,basebox,refbox,'integer_ink_origin'
def render_view(xml,size,dx,dy):
 from native_worker import native
 root=E.fromstring(xml);model=root.find('.//mxGraphModel') if root.tag!='mxGraphModel' else root
 model.set('pageWidth',str(size[0]));model.set('pageHeight',str(size[1]));model.set('nativeExportDxV2',str(dx));model.set('nativeExportDyV2',str(dy))
 renderer=R/'conversion/rendering_native_export_view_v2/remote_render.py'
 require(sha(renderer.read_bytes())==SOURCE_VIEW_RENDERER_SHA256,'native_export_source_view_renderer_changed')
 out=native.native_job(E.tostring(root,encoding='unicode'),*size,180,renderer,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 require(out.get('ok'),'native_export_independent_source_view_render_failed')
 require(out['native_render'].get('translate')=={'x':dx,'y':dy},'native_export_independent_source_view_translation_not_applied')
 audit=out['native_render'].get('outside_page_pixel_audit') or {};require(audit.get('white_threshold')==255 and audit.get('nonwhite_outside_pixels')==0,'native_export_independent_source_view_clips_source_paint')
 return out
def bridge_labels(xml,source,target):
 from native_source_font_profile_v4 import signature,_models,_cells
 require(signature(source['actual_platform_font_usage'])==signature(target['actual_platform_font_usage']),'native_export_label_bridge_changes_physical_glyphs')
 rows=lambda info:{r['cell']:[c for run in r.get('runs',[]) for c in run.get('chars',[])] for r in info['actual_text_positions']}
 a,b=rows(source),rows(target);require(a.keys()==b.keys(),'native_export_label_bridge_changes_text_scope')
 root,_=_models(xml);cells=_cells(root);changes=[]
 for cid,chars in a.items():
  require(len(chars)==len(b[cid]),'native_export_label_bridge_changes_text_length')
  if not chars:continue
  dx=chars[0]['x']-b[cid][0]['x'];dy=chars[0]['y']-b[cid][0]['y']
  for c,n in zip(chars,b[cid]):
   require(c['text']==n['text'] and abs(c['width']-n['width'])<=1e-6 and abs(c['height']-n['height'])<=1e-6,'native_export_label_bridge_changes_text_or_size')
   require(abs(c['x']-n['x']-dx)<=1e-6 and abs(c['y']-n['y']-dy)<=1e-6,'native_export_label_bridge_nonuniform_remainder')
  if max(abs(dx),abs(dy))<=1e-6:continue
  require(max(abs(dx),abs(dy))<=LABEL_ROUNDING_LIMIT,'native_export_label_bridge_exceeds_rounding_bound')
  cell=cells[cid];style={p.split('=',1)[0]:p.split('=',1)[1] for p in cell.get('style','').split(';') if '=' in p}
  require(style.get('html')=='1' and 'value' in cell.attrib and 'clip-path' not in cell.get('value',''),'native_export_label_bridge_requires_unclipped_html_label')
  value=cell.get('value','');prefix='<span data-native-export-label-offset="v2" style="position:relative;left:'+format(dx,'.10g')+'px;top:'+format(dy,'.10g')+'px;">'
  cell.set('value',prefix+value+'</span>');changes.append({'cell':cid,'dx':dx,'dy':dy,'before_value':value,'prefix':prefix})
 return E.tostring(root,encoding='unicode'),changes

def paint_proof(xml,baseline,fresh,dx,dy,size,mode):
 if mode=='official_graph_bounds_uniform_border':
  source_view=render_view(xml,size,dx,dy)
  from native_source_font_profile_v4 import signature
  require(signature(baseline['native_render']['actual_platform_font_usage'])==signature(source_view['native_render']['actual_platform_font_usage']),'native_export_source_view_changes_physical_glyph_scope')
  text=lambda info:{r['cell']:[c['text'] for run in r.get('runs',[]) for c in run.get('chars',[])] for r in info['actual_text_positions']}
  require(text(baseline['native_render'])==text(source_view['native_render']),'native_export_source_view_changes_text_scope')
  geometry=verify_render_translation(source_view['native_render'],fresh['native_render'],0,0)
  delta=exact_shift(source_view['png'],fresh['png'],0,0)
  return {**delta,**geometry,'independent_original_graph_view_translation_verified':True,'source_view_png_sha256':sha(source_view['png'])}
 delta=exact_shift(baseline['png'],fresh['png'],dx,dy);delta.update(verify_render_translation(baseline['native_render'],fresh['native_render'],dx,dy));return delta

def repair(record,job,work):
 from fixed_batch_case_v1 import checked,save,raw
 try:
  require(record.get('source_format')=='drawio','native_export_original_drawio_required')
  require(not record.get('auto_quality_canvas_repair') and not record.get('native_export_canvas_v2'),'native_export_existing_lineage_requires_separate_support')
  xml=checked(record['code_file'],record['code_sha256']).decode();reference=checked(record['original_reference'],record['source_image_sha256'])
  checked(record['original_source_code'],record['source_code_sha256'])
  model=E.fromstring(xml).find('.//mxGraphModel');oldsize=[int(float(model.get(k,0))) for k in ('pageWidth','pageHeight')];size=list(pixels(reference).size)
  baseline=render(xml,oldsize);dx,dy,size,basebox,refbox,mode=export_plan(reference,baseline)
  if [dx,dy]==[0,0] and size==oldsize:return {'ok':True,'record':record,'no_op':True,'evidence':{'reason':'native_export_already_registered'}}
  new=translate(xml,dx,dy,size);fresh=render(new,size);bridge=[]
  if mode=='official_graph_bounds_uniform_border':
   source_view=render_view(xml,size,dx,dy);new,bridge=bridge_labels(new,source_view['native_render'],fresh['native_render'])
   if bridge:fresh=render(new,size)
  diagnostic=Path(work).resolve();require(diagnostic.is_relative_to((R/'conversion').resolve()),'native_export_unowned_development_work');diagnostic.mkdir(parents=True,exist_ok=True)
  for name,blob in [('before.drawio',xml.encode()),('candidate.drawio',new.encode()),('baseline.png',baseline['png']),('candidate.png',fresh['png']),('baseline.native.json',raw(baseline['native_render'])),('candidate.native.json',raw(fresh['native_render']))]:save(diagnostic/name,blob)
  save(diagnostic/'plan.json',raw({'dx':dx,'dy':dy,'oldsize':oldsize,'size':size}))
  delta=paint_proof(xml,baseline,fresh,dx,dy,size,mode)
  folder=OWNER/record['id']/uuid.uuid4().hex;dest=R/'clean/native_export_canvas_v2'/record['id'][:2]/record['id']/folder.name;folder.mkdir(parents=True);dest.mkdir(parents=True)
  for name,blob in [('before.drawio',xml.encode()),('candidate.drawio',new.encode()),('baseline.png',baseline['png']),('candidate.png',fresh['png'])]:save(folder/name,blob)
  save(folder/'before_record.json',raw(record));save(dest/'diagram.drawio',new.encode());save(dest/'image.png',fresh['png'])
  proof={'schema':SCHEMA,'id':record['id'],'input_code_sha256':record['code_sha256'],'output_code_sha256':sha(new.encode()),'baseline_png_sha256':sha(baseline['png']),'output_image_sha256':sha(fresh['png']),'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'old_page':oldsize,'new_page':size,'translation':[dx,dy],'translation_mode':mode,'label_rounding_bridge':bridge,'native_ink_bbox':basebox,'reference_ink_bbox':refbox,'paint':delta,'audit':str((folder/'proof.json').relative_to(R)),'accepted':False}
  save(folder/'proof.json',raw(proof));out={**record,'code_file':str((dest/'diagram.drawio').relative_to(R)),'code_sha256':proof['output_code_sha256'],'image_file':str((dest/'image.png').relative_to(R)),'image_sha256':proof['output_image_sha256'],'native_export_canvas_v2':proof,'render':fresh['native_render'],'quality_state':'pending_complete_source_reference_native_quality'}
  save(folder/'candidate_record.json',raw(out));save(dest/'conversion.json',raw(out));return {'ok':True,'record':out,'evidence':proof}
 except Exception as e:return {'ok':False,'reason':'native_export_refused','error_type':type(e).__name__,'detail':str(e)}

def validate(record,xml):
 """Reconstruct geometry and rerender both revisions, independent of proof booleans."""
 from fixed_batch_case_v1 import checked
 proof=record['native_export_canvas_v2'];folder=(R/proof['audit']).resolve(strict=True).parent
 require(folder.is_relative_to(OWNER.resolve()) and folder.parent.name==record['id'],'native_export_unowned_proof')
 require(json.loads((folder/'proof.json').read_bytes())==proof,'native_export_proof_changed')
 before=(folder/'before.drawio').read_text();previous=json.loads((folder/'before_record.json').read_bytes());current=json.loads((folder/'candidate_record.json').read_bytes())
 require(sha(before.encode())==previous['code_sha256']==proof['input_code_sha256'] and sha(xml.encode())==record['code_sha256']==proof['output_code_sha256'],'native_export_revision_mismatch')
 require((folder/'candidate.drawio').read_text()==xml and current['code_sha256']==record['code_sha256'] and current['image_sha256']==record['image_sha256'],'native_export_current_frozen_revision_mismatch')
 require(current.get('native_export_canvas_v2')==proof,'native_export_frozen_contract_changed')
 for obj in [previous,current,proof]:require(all(obj.get(k)==record.get(k) for k in ('id','source_code_sha256','source_image_sha256')),'native_export_source_identity_changed')
 dx,dy=proof['translation'];require(all(type(v) in (int,float) and math.isfinite(v) for v in (dx,dy)),'native_export_nonfinite_translation')
 expected=translate(before,dx,dy,proof['new_page'])
 if proof.get('translation_mode')=='official_graph_bounds_uniform_border':
  source_view=render_view(before,proof['new_page'],dx,dy);unbridged=render(expected,proof['new_page']);expected,bridge=bridge_labels(expected,source_view['native_render'],unbridged['native_render'])
  require(bridge==proof.get('label_rounding_bridge'),'native_export_label_remainder_not_rederived_from_source')
 else:require(not proof.get('label_rounding_bridge'),'native_export_unexpected_label_bridge')
 require(E.canonicalize(expected)==E.canonicalize(xml),'native_export_nontranslation_source_graph_changed')
 reference=checked(record['original_reference'],record['source_image_sha256']);require(list(pixels(reference).size)==proof['new_page'],'native_export_reference_size_changed')
 beforefresh=render(before,proof['old_page']);fresh=render(xml,proof['new_page']);plan=export_plan(reference,beforefresh)
 require(list(plan[:2])==[dx,dy] and plan[-1]==proof['translation_mode'],'native_export_translation_not_derived_from_original_source_bounds')
 paint_proof(before,beforefresh,fresh,dx,dy,proof['new_page'],proof['translation_mode'])
 require(pixels(checked(record['image_file'],record['image_sha256'])).tobytes()==pixels(fresh['png']).tobytes(),'native_export_current_png_differs_from_fresh_render')
 return previous,before,{'schema':SCHEMA,'current_code_sha256':record['code_sha256'],'translation':[dx,dy],'output_page':proof['new_page'],'all_source_paint_preserved':True,'exact_native_translation_reproved':True,'accepted':False}
