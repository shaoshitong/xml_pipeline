"""Per-source original image-unit mapping; no tracing or source execution.

Fresh SVG DOM observations supply resolved lengths and screen CTMs. Every
asset remains the exact original embedded byte stream. Mapping succeeds only
for single-frame PNG/JPEG/WebP or inert text-free original SVG image units,
positive diagonal CTMs, and none/meet aspect. Image interiors are not claimed
to be editable native text or vectors.
Candidate verification rederives geometry/header/hash from fresh DOM fields;
converter-authored IR acceptance flags are never used as evidence.
"""
from __future__ import annotations
import base64,copy,hashlib,io,math,re,urllib.parse,xml.etree.ElementTree as ET
POLICY='source_authored_asset_panel_positive_axis_none_or_meet_v1'
MAX_BYTES=64*1024*1024
MAX_PIXELS=64_000_000
EPS=1e-6
class ImagePending(ValueError):pass
def require(ok,reason):
 if not ok:raise ImagePending(reason)
def sha(blob):return hashlib.sha256(blob).hexdigest()
def num(v):return format(float(v),'.6f').rstrip('0').rstrip('.') or '0'
def _finite(v):
 require(type(v) in (int,float) and math.isfinite(v),'raster_image_nonfinite_number');return float(v)
def _svg_length(value):
 if value is None:return None
 m=re.fullmatch(r'\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)\s*(px|pt|pc|in|cm|mm|q)?\s*',str(value))
 require(m is not None,'svg_asset_intrinsic_length_units_pending')
 return float(m[1])*{'px':1,'pt':96/72,'pc':16,'in':96,'cm':96/2.54,'mm':96/25.4,'q':96/101.6,None:1}[m[2]]
def _svg_asset(raw,depth=0):
 """Inert isolated original SVG image unit; never claim its internals editable."""
 require(depth<=4,'svg_asset_nested_resource_depth_pending')
 require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper() and b'<?xml-stylesheet' not in raw.lower(),'svg_asset_xml_declaration_pending')
 try:root=ET.fromstring(raw)
 except Exception as e:raise ImagePending('svg_asset_xml_parse_failed:'+type(e).__name__)
 require(root.tag.rsplit('}',1)[-1]=='svg','svg_asset_root_not_svg')
 allowed={'svg','g','defs','path','rect','circle','ellipse','polygon','polyline','line','use','symbol','clipPath','mask','linearGradient','radialGradient','stop','pattern','title','desc','metadata','style','text','tspan','textPath','image','filter','feGaussianBlur','feOffset','feBlend','feColorMatrix','feComposite','feMerge','feMergeNode','feFlood','feDropShadow','feTurbulence','feDisplacementMap','feMorphology','feConvolveMatrix','feComponentTransfer','feFuncA','feFuncR','feFuncG','feFuncB','feDiffuseLighting','feSpecularLighting','feDistantLight','fePointLight','feSpotLight','feTile'}
 elements=list(root.iter());parents={c:p for p in elements for c in p};styles=[];texts=[];ids=set();refs=[]
 for e in elements:
  tag=e.tag.rsplit('}',1)[-1];require(tag in allowed,'svg_asset_active_or_unknown_element_pending:'+tag)
  if e.get('id'):require(e.get('id') not in ids,'svg_asset_duplicate_id');ids.add(e.get('id'))
  if tag=='style':styles.append(e.text or '')
  if tag in ('text','tspan','textPath') and ''.join(e.itertext()).strip():texts.append(e)
  for k,v in e.attrib.items():
   local=k.rsplit('}',1)[-1];require(not local.lower().startswith('on'),'svg_asset_event_attribute_pending');require(local not in ('src',),'svg_asset_src_resource_pending')
   if local=='href':
    if v.startswith('#'):refs.append(v[1:])
    elif tag=='image' and v.startswith('data:image/'):
     # Preserve source-authored nested data assets, requiring the same closure.
     decode_asset_uri(v,_depth=depth+1)
    else:raise ImagePending('svg_asset_external_or_active_href_pending')
   if local=='style':styles.append(v)
  # CSS paint-server URLs may reference only this asset's own definitions.
  for v in list(e.attrib.values())+([e.text or ''] if tag=='style' else []):
   require(not re.search(r'@import\b|expression\s*\(|javascript\s*:|(?:^|[;\s])(?:animation|transition)(?:-|\s*:)',v,re.I),'svg_asset_active_css_pending')
   for m in re.finditer(r'url\(\s*[\"\']?([^\"\')]+)',v,re.I):
    ref=m[1].strip()
    if ref.startswith('#'):refs.append(ref[1:])
    else:require(ref.startswith('data:font/') or ref.startswith('data:application/font-') or ref.startswith('data:application/x-font-'),'svg_asset_external_css_resource_pending')
 require(all(ref in ids for ref in refs),'svg_asset_dangling_internal_reference')
 w,h=_svg_length(root.get('width')),_svg_length(root.get('height'));vb=None
 if root.get('viewBox'):
  try:vb=[float(x) for x in re.split(r'[\s,]+',root.get('viewBox').strip())]
  except ValueError:raise ImagePending('svg_asset_viewbox_invalid')
  require(len(vb)==4 and all(math.isfinite(x) for x in vb) and vb[2]>0 and vb[3]>0,'svg_asset_viewbox_invalid')
 basis='explicit SVG image intrinsic width/height'
 if w is None and h is None and vb:w,h=vb[2:];basis='source viewBox intrinsic aspect ratio; absolute dimensions not asserted'
 elif w is None and h is not None and vb:w=h*vb[2]/vb[3]
 elif h is None and w is not None and vb:h=w*vb[3]/vb[2]
 require(w is not None and h is not None and 0<w and 0<h and w*h<=MAX_PIXELS,'svg_asset_intrinsic_dimensions_pending')
 # A supplied SVG image is an isolated document: outer SVG fonts/CSS do not
 # close fonts inside it. Text-free assets are closed without ambient fonts.
 fontproof={'closed':not texts,'basis':'text-free exact original SVG paths/shapes','text_elements':len(texts)}
 require(not texts,'svg_asset_internal_font_closure_requires_separate_text_profile')
 return {'format':'SVG','intrinsic_size':[w,h],'intrinsic_size_basis':basis,'frames':1,'inert_self_contained':True,'font_closure':fontproof,'interior_editability':'source_asset_unit_only'}
def decode_asset_uri(uri,*,native=False,_depth=0):
 """Return immutable asset identity/header metadata, never transcoded pixels."""
 require(isinstance(uri,str) and uri.startswith('data:'),'raster_image_external_or_missing_uri_pending')
 header,sep,payload=uri.partition(',');require(bool(sep),'raster_image_data_uri_missing_comma')
 mime=header[5:].split(';',1)[0].lower().strip()
 expected={'image/png':'PNG','image/jpeg':'JPEG','image/jpg':'JPEG','image/webp':'WEBP'}
 require(mime in expected or mime=='image/svg+xml','raster_image_mime_pending:'+mime)
 require(len(payload)<=MAX_BYTES*4//3+1024,'raster_image_encoded_asset_over_bound')
 try:
  raw=base64.b64decode(re.sub(r'\s+','',payload),validate=True) if ';base64' in header.lower() or native else urllib.parse.unquote_to_bytes(payload)
 except Exception as e:raise ImagePending('raster_image_data_uri_decode_failed:'+type(e).__name__)
 require(0<len(raw)<=MAX_BYTES,'raster_image_asset_size_bound')
 if mime=='image/svg+xml':
  proof=_svg_asset(raw,_depth);return {**proof,'mime_type':mime,'source_asset_sha256':sha(raw),'asset_bytes':len(raw),'uri_sha256':sha(uri.encode()),'canonical_native_uri':'data:'+mime+','+base64.b64encode(raw).decode()}
 from PIL import Image
 try:
  with Image.open(io.BytesIO(raw)) as im:
   require(im.format==expected[mime],'raster_image_declared_mime_header_mismatch');w,h=im.size;frames=int(getattr(im,'n_frames',1));orientation=int(im.getexif().get(274,1))
   require(frames==1,'raster_image_animation_requires_frame_semantics');require(orientation==1,'raster_image_exif_orientation_pending')
   require(w>0 and h>0 and w*h<=MAX_PIXELS,'raster_image_intrinsic_size_bound')
  with Image.open(io.BytesIO(raw)) as checked:checked.verify()
 except ImagePending:raise
 except Exception as e:raise ImagePending('raster_image_header_or_integrity_failed:'+type(e).__name__)
 return {'mime_type':'image/jpeg' if mime=='image/jpg' else mime,'format':expected[mime],'source_asset_sha256':sha(raw),'asset_bytes':len(raw),'intrinsic_size':[w,h],'frames':frames,'uri_sha256':sha(uri.encode()),'interior_editability':'source_asset_unit_only','canonical_native_uri':'data:'+('image/jpeg' if mime=='image/jpg' else mime)+','+base64.b64encode(raw).decode()}
def _matrix(value):
 if isinstance(value,dict):value=value.get('matrix')
 require(isinstance(value,(list,tuple)) and len(value)==6,'raster_image_fresh_screen_ctm_missing')
 out=[_finite(x) for x in value];a,b,c,d,e,f=out
 require(abs(b)<=1e-8 and abs(c)<=1e-8,'raster_image_shear_or_rotation_pending');require(a>0 and d>0,'raster_image_axis_flip_or_degenerate_pending');return out
def paint_rect(attrs,matrix,intrinsic,preserve='xMidYMid meet'):
 """Exact SVG image viewport -> intrinsic paint rect -> positive screen CTM."""
 vals={k:_finite(attrs.get(k)) for k in ('x','y','width','height')};x,y,w,h=[vals[k] for k in ('x','y','width','height')]
 require(w>0 and h>0,'raster_image_zero_or_negative_viewport_pending');iw,ih=intrinsic;require(iw>0 and ih>0,'raster_image_intrinsic_dimensions_missing')
 parts=str(preserve or 'xMidYMid meet').strip().split();require('defer' not in parts,'raster_image_defer_aspect_pending');require('slice' not in parts,'raster_image_slice_requires_clip_proof')
 if parts==['none']:
  px,py,pw,ph=x,y,w,h;align='none';mode='none'
 else:
  require(len(parts) in (1,2) and re.fullmatch(r'x(?:Min|Mid|Max)Y(?:Min|Mid|Max)',parts[0]) is not None and (len(parts)==1 or parts[1]=='meet'),'raster_image_aspect_policy_pending')
  align=parts[0];mode='meet';s=min(w/iw,h/ih);pw,ph=iw*s,ih*s;ax=0 if 'xMin' in align else 1 if 'xMax' in align else .5;ay=0 if 'YMin' in align else 1 if 'YMax' in align else .5;px,py=x+(w-pw)*ax,y+(h-ph)*ay
 a,b,c,d,e,f=_matrix(matrix)
 return {'x':a*px+e,'y':d*py+f,'w':a*pw,'h':d*ph}, {'x':a*x+e,'y':d*y+f,'w':a*w,'h':d*h}, {'alignment':align,'mode':mode,'local_paint_rect':[px,py,pw,ph]}
def _rect_close(a,b,tol=EPS):return all(abs(float(a[k])-float(b[k]))<=tol for k in ('x','y','w','h'))
def _derive_object(dom,obj):
 info=obj.get('sceneImage') or {};require(not obj.get('sceneUseContexts') and not obj.get('sceneMarkerContexts'),'raster_image_use_or_marker_instance_pending')
 require(info.get('originalInstance',True) is True,'raster_image_nonoriginal_instance_pending')
 css=obj.get('sceneComputedCss') or {}
 for key in ('filter','clipPath','maskImage'):
  require(css.get(key) in (None,'','none'),'raster_image_'+key+'_pending')
 require(css.get('mixBlendMode') in (None,'','normal'),'raster_image_blend_mode_pending')
 require(css.get('display') not in ('none',) and css.get('visibility') not in ('hidden','collapse'),'raster_image_hidden_object_pending')
 # Do not convert a group compositing operation into independent child alpha.
 for ancestor in obj.get('sceneAncestorOpacity',[]):
  opacity=_finite(ancestor.get('opacity',1));ref=ancestor.get('ref')
  if opacity!=1:
   shared=[o for o in dom.get('objects',[]) if ref in o.get('sceneAncestry',[])]
   require(len(shared)==1,'raster_image_group_opacity_compositing_pending')
 matrix=_matrix(info.get('matrix',obj.get('matrix')))
 if obj.get('matrix') is not None:require(all(abs(a-b)<=1e-7 for a,b in zip(matrix,_matrix(obj['matrix']))),'raster_image_fresh_ctm_inventory_changed')
 opacity=_finite((obj.get('style')or{}).get('opacity',1));require(0<opacity<=1,'raster_image_opacity_pending')
 asset=decode_asset_uri(obj.get('href',''));attrs=info.get('attrs') or info.get('sourceAttributes') or {};preserve=info.get('preserveAspectRatio','xMidYMid meet');rect,viewport,mathproof=paint_rect(attrs,matrix,asset['intrinsic_size'],preserve)
 observed=info.get('viewportBBox')
 if observed is not None:require(_rect_close(viewport,observed,.03),'raster_image_fresh_viewport_bbox_ctm_mismatch')
 require(isinstance(obj.get('id'),str) and obj['id'],'raster_image_native_owner_id_missing')
 return {**{k:v for k,v in asset.items() if k!='canonical_native_uri'},'policy':POLICY,'native_cell_id':obj['id'],'source_element_id':obj.get('sourceId') or info.get('originalElementId') or '', 'source_document_index':info.get('documentIndex'),'source_geometry':{k:float(attrs[k]) for k in ('x','y','width','height')},'ctm':matrix,'preserve_aspect_ratio':preserve,'paint_rect':rect,'viewport_rect':viewport,'math':mathproof,'opacity':opacity,'native_style':{'shape':'image','imageAspect':'0','opacity':num(opacity*100)}}
def extract(code_bytes):
 root=ET.fromstring(code_bytes);out=[]
 for i,e in enumerate(x for x in root.iter() if x.tag.rsplit('}',1)[-1]=='image'):
  uri=e.get('href') or e.get('{http://www.w3.org/1999/xlink}href') or ''
  try:asset=decode_asset_uri(uri);out.append({'document_index':i,'source_element_id':e.get('id',''),**{k:v for k,v in asset.items() if k!='canonical_native_uri'},'supported_asset':True})
  except ImagePending as error:out.append({'document_index':i,'source_element_id':e.get('id',''),'supported_asset':False,'pending_reason':str(error)})
 return {'policy':POLICY,'source_code_sha256':sha(code_bytes),'images':out,'geometry_requires_fresh_dom':True}
def apply_to_dom(dom,code_bytes):
 """Mutate only proved image bboxes and that image's prior aspect warning."""
 require(isinstance(code_bytes,bytes),'raster_image_original_source_bytes_required');root=ET.fromstring(code_bytes);source_images=[e for e in root.iter() if e.tag.rsplit('}',1)[-1]=='image'];objects=[o for o in dom.get('objects',[]) if o.get('type')=='image'];proofs=[];pending=[];used=set();success=set();svg_success=set()
 for order,obj in enumerate(objects):
  try:
   info=obj.get('sceneImage')or{};index=info.get('documentIndex')
   if index is None:
    # Compatibility for a unique original ID; never guess a repeated/anonymous use instance.
    sid=obj.get('sourceId') or info.get('originalElementId');choices=[i for i,e in enumerate(source_images) if sid and e.get('id')==sid]
    require(len(choices)==1,'raster_image_document_index_or_unique_original_id_required');index=choices[0]
   require(type(index) is int and 0<=index<len(source_images),'raster_image_original_document_index_missing');require(index not in used,'raster_image_original_owner_reused');used.add(index);e=source_images[index];uri=e.get('href') or e.get('{http://www.w3.org/1999/xlink}href') or ''
   src=decode_asset_uri(uri);native_uri=src['canonical_native_uri'];canonical_source=native_uri.replace(',', ';base64,',1);require(obj.get('href') in (uri,canonical_source),'raster_image_fresh_uri_differs_from_original_source');require((obj.get('sourceId')or'')==(e.get('id')or''),'raster_image_original_element_identity_changed');proof=_derive_object(dom,obj);require(proof['source_asset_sha256']==src['source_asset_sha256'],'raster_image_original_asset_hash_changed');proof['source_document_index']=index;proof['source_code_sha256']=sha(code_bytes);proof['original_source_uri_sha256']=sha(uri.encode());obj['preserve_original_href']=uri;obj['href']=canonical_source;obj['bbox']=dict(proof['paint_rect']);obj['raster_panel_ir']=proof;proofs.append(proof);success.add(obj['id'])
   if src['format']=='SVG':svg_success.add(obj['id'])
  except (ImagePending,ET.ParseError,ValueError,TypeError,KeyError) as error:
   issue={'id':obj.get('id'),'reason':'raster_panel_image_pending','detail':str(error),'severity':'unsupported','scope':'source_paint'};pending.append(issue)
 # All other clip/effect/opacity/vector warnings survive. Only this exact aspect gap is discharged.
 for key in ('issues','sceneIssues'):
  dom[key]=[i for i in dom.get(key,[]) if not (i.get('reason')=='scene_image_aspect_mapping_unproven' and i.get('id') in success or i.get('reason')=='scene_vector_image_requires_editable_expansion' and i.get('id') in svg_success)]+copy.deepcopy(pending)
 dom['raster_panel_ir']={'policy':POLICY,'source_code_sha256':sha(code_bytes),'images':proofs,'pending':pending,'ok':not pending,'new_whole_figure_wrappers':0,'interior_editability':'source_asset_unit_only','mapping':'one exact original self-contained image byte asset per source-authored image owner'};return dom
def _styles(value):
 value=re.sub(r'((?:image|fontSource)=data:[^,]*,)',lambda m:m[0].replace(';','\x00'),value)
 return {x.split('=',1)[0]:x.split('=',1)[1].replace('\x00',';') for x in value.split(';') if '=' in x}
def _world_box(cell,cells):
 g=cell.find('mxGeometry');require(g is not None and g.get('relative')!='1','raster_image_relative_native_geometry_pending');x,y,w,h=[float(g.get(k,'0')) for k in ('x','y','width','height')];seen={cell.get('id')};parent=cell.get('parent')
 while parent in cells and parent not in ('0','1'):
  require(parent not in seen,'raster_image_native_parent_cycle');seen.add(parent);p=cells[parent];style=_styles(p.get('style',''));require(float(style.get('rotation','0'))==0 and style.get('flipH','0')=='0' and style.get('flipV','0')=='0' and float(style.get('opacity','100'))==100,'raster_image_native_parent_transform_or_compositing_pending');pg=p.find('mxGeometry');require(pg is not None and pg.get('relative')!='1','raster_image_native_relative_parent_pending');x+=float(pg.get('x','0'));y+=float(pg.get('y','0'));parent=p.get('parent')
 require(all(math.isfinite(a) for a in (x,y,w,h)) and w>0 and h>0,'raster_image_native_nonfinite_geometry');return {'x':x,'y':y,'w':w,'h':h}
def verify_dom_candidate(dom,xml):
 """Independent per-object byte/paint/opacity check from freshly recaptured DOM."""
 root=ET.fromstring(xml);models=list(root.iter('mxGraphModel'));require(len(models)==1,'raster_image_one_uncompressed_native_model_required');cells={e.get('id'):e for e in models[0].iter('mxCell')};expected=[_derive_object(dom,o) for o in dom.get('objects',[]) if o.get('type')=='image'];image_cells={i:c for i,c in cells.items() if _styles(c.get('style','')).get('shape')=='image'};require(len(image_cells)==len(expected),'raster_image_candidate_owner_count_differs');seen=set();proofs=[]
 for row in expected:
  cid=row['native_cell_id'];require(cid in image_cells and cid not in seen,'raster_image_candidate_source_owner_missing_or_reused');seen.add(cid);c=image_cells[cid];require(c.get('vertex')=='1' and c.get('edge')!='1','raster_image_candidate_owner_not_individual_vertex');st=_styles(c.get('style',''));require(st.get('imageAspect')=='0','raster_image_native_aspect_must_be_zero_after_exact_paint_rect')
  for k in ('rotation','flipH','flipV','imageFlipH','imageFlipV','shadow'):require(float(st.get(k,'0'))==0,'raster_image_native_extra_transform_pending:'+k)
  for k in ('imageBackground','imageBorder'):require(st.get(k) in (None,'none',''),'raster_image_native_added_paint_pending:'+k)
  require(st.get('movable','1')!='0' and st.get('locked','0')!='1','raster_image_native_owner_not_editable');asset=decode_asset_uri(st.get('image',''),native=True);require(asset['source_asset_sha256']==row['source_asset_sha256'] and asset['mime_type']==row['mime_type'] and asset['intrinsic_size']==row['intrinsic_size'],'raster_image_native_asset_not_exact_original');box=_world_box(c,cells);require(_rect_close(box,row['paint_rect'],2e-6),'raster_image_native_paint_rectangle_differs');require(abs(float(st.get('opacity','100'))/100-row['opacity'])<=1e-8,'raster_image_native_opacity_differs');proofs.append({k:row[k] for k in ('native_cell_id','source_element_id','source_document_index','source_asset_sha256','asset_bytes','mime_type','intrinsic_size','paint_rect','opacity')})
 return {'ok':True,'policy':POLICY,'candidate_code_sha256':sha(xml.encode() if isinstance(xml,str) else xml),'image_owners':len(expected),'images':proofs,'exact_original_asset_bytes':True,'independently_rederived_from_fresh_dom':True,'no_extra_native_image_cells':True,'source_flags_trusted':False}
def self_test():
 from PIL import Image
 import unittest
 class Tests(unittest.TestCase):
  def fixture(self,fmt='PNG',size=(4,2)):
   b=io.BytesIO();Image.new('RGB',size,'red').save(b,format=fmt);return 'data:image/'+{'PNG':'png','JPEG':'jpeg','WEBP':'webp'}[fmt]+';base64,'+base64.b64encode(b.getvalue()).decode()
  def dom(self,preserve='xMidYMid meet',**kw):
   u=self.fixture();o={'id':'v1','type':'image','sourceId':'p','href':u,'matrix':[1,0,0,1,0,0],'style':{'opacity':.6},'sceneImage':{'documentIndex':0,'originalInstance':True,'attrs':{'x':10.,'y':20.,'width':100.,'height':100.},'preserveAspectRatio':preserve,'matrix':[1,0,0,1,0,0],'viewportBBox':{'x':10.,'y':20.,'w':100.,'h':100.}}};o.update(kw);return {'objects':[o],'issues':[{'id':'v1','reason':'scene_image_aspect_mapping_unproven'},{'id':'other','reason':'clipPath'}]},('<svg xmlns="http://www.w3.org/2000/svg"><image id="p" href="'+u+'"/></svg>').encode()
  def test_headers(self):
   for fmt in ('PNG','JPEG','WEBP'):self.assertEqual(decode_asset_uri(self.fixture(fmt))['format'],fmt)
  def test_svg_asset_unit(self):
   for src in (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 80"><path d="M0 0L5 8"/></svg>',b'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="200"><defs><pattern id="p" width="2" height="2" patternUnits="userSpaceOnUse"><circle r="1"/></pattern></defs><rect width="60" height="200" fill="url(#p)"/></svg>'):
    uri='data:image/svg+xml;base64,'+base64.b64encode(src).decode();r=decode_asset_uri(uri);self.assertEqual(r['source_asset_sha256'],sha(src));self.assertTrue(r['font_closure']['closed']);self.assertEqual(r['interior_editability'],'source_asset_unit_only')
  def test_svg_asset_security_font_pending(self):
   for src in (b'<svg width="5" height="5"><script>1</script></svg>',b'<svg width="5" height="5" onload="x()"/>',b'<svg width="5" height="5"><image href="https://example.invalid/x.png"/></svg>',b'<svg width="5" height="5"><text>not closed</text></svg>',b'<svg width="5" height="5"><text><tspan/>tail</text></svg>',b'<?xml-stylesheet href="https://example.invalid/x.css"?><svg width="5" height="5"/>'):
    uri='data:image/svg+xml;base64,'+base64.b64encode(src).decode()
    with self.assertRaises(ImagePending):decode_asset_uri(uri)
  def test_alignments(self):
   for a,x in [('xMin',10),('xMid',10),('xMax',10)]:
    for b,y in [('YMin',20),('YMid',45),('YMax',70)]:self.assertEqual(paint_rect({'x':10,'y':20,'width':100,'height':100},[1,0,0,1,0,0],[4,2],a+b+' meet')[0],{'x':float(x),'y':float(y),'w':100.,'h':50.})
  def test_none_ctm(self):self.assertEqual(paint_rect({'x':1,'y':2,'width':3,'height':4},[2,0,0,3,7,11],[4,2],'none')[0],{'x':9.,'y':17.,'w':6.,'h':12.})
  def test_reject_transform(self):
   for m in ([1,.1,0,1,0,0],[1,0,.1,1,0,0],[-1,0,0,1,0,0],[1,0,0,-1,0,0],[0,0,0,1,0,0]):
    with self.assertRaises(ImagePending):paint_rect({'x':0,'y':0,'width':10,'height':10},m,[4,2])
  def test_slice(self):
   with self.assertRaises(ImagePending):paint_rect({'x':0,'y':0,'width':10,'height':10},[1,0,0,1,0,0],[4,2],'xMidYMid slice')
  def test_pending_vector_remote(self):
   for u in ('https://example.invalid/a.png','data:image/svg+xml;base64,PHN2Zy8+'):
    with self.assertRaises(ImagePending):decode_asset_uri(u)
  def test_apply_preserves_other_issues(self):
   d,b=self.dom();apply_to_dom(d,b);self.assertEqual(d['objects'][0]['bbox'],{'x':10.,'y':45.,'w':100.,'h':50.});self.assertTrue(d['raster_panel_ir']['ok']);self.assertEqual(d['issues'],[{'id':'other','reason':'clipPath'}])
  def test_original_uri_binding(self):
   d,b=self.dom();d['objects'][0]['href']=self.fixture(size=(8,2));apply_to_dom(d,b);self.assertFalse(d['raster_panel_ir']['ok'])
  def test_verify_and_mutation(self):
   d,b=self.dom();apply_to_dom(d,b);o=d['objects'][0];u=decode_asset_uri(o['href'])['canonical_native_uri'];r=o['bbox'];xml='<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="v1" parent="1" vertex="1" style="shape=image;imageAspect=0;opacity=60;image='+u+';"><mxGeometry x="10" y="45" width="100" height="50" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>';self.assertTrue(verify_dom_candidate(d,xml)['ok'])
   for old,new in [('x="10"','x="11"'),('opacity=60','opacity=61'),('imageAspect=0','imageAspect=1')]:
    with self.assertRaises(ImagePending):verify_dom_candidate(d,xml.replace(old,new))
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=2).run(suite);require(r.wasSuccessful(),'raster_image_IR_self_tests_failed');return {'tests':r.testsRun,'ok':r.wasSuccessful()}
if __name__=='__main__':
 import json
 print(json.dumps(self_test()))
