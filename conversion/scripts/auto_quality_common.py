"""Revision-bound, machine-readable release checks; no per-item visual approval."""
import base64,collections,hashlib,html,io,json,re,urllib.parse,xml.etree.ElementTree as E
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from skimage.metrics import structural_similarity

POLICY='source_coverage_native_render_and_local_fidelity_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()

def clean_path(root,value):
 p=(root/value).resolve()
 if not p.is_relative_to((root/'clean').resolve()):raise ValueError('payload_outside_clean: '+str(value))
 if not p.is_file():raise ValueError('missing_payload: '+str(value))
 return p

def checked(root,value,digest):
 data=clean_path(root,value).read_bytes()
 if sha(data)!=digest:raise ValueError('payload_hash_mismatch: '+str(value))
 return data

def resource_checks(root,r,xml,reference):
 """All raster cells must be verified original assets, never the full reference."""
 allowed=set();files=[]
 for key,digest in [('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_png','source_render_png_sha256'),('original_source_data','source_data_sha256')]:
  if r.get(key):
   if not r.get(digest):raise ValueError('missing_source_payload_hash: '+key)
   checked(root,r[key],r[digest]);files.append(r[key])
 for asset in r.get('original_vector_assets') or []:
  checked(root,asset['file'],asset['sha256']);files.append(asset['file'])
 for asset in r.get('source_assets',[]):
  for key,digest in [('source','source_sha256'),('file','embedded_sha256'),('original_file','original_sha256')]:
   if asset.get(key) and asset.get(digest):
    data=checked(root,asset[key],asset[digest]);allowed.add(sha(data));files.append(asset[key])
 for font in (r.get('native_embedded_fonts') or [])+(r.get('fonts') or []):
  if font.get('file'):checked(root,font['file'],font['sha256']);files.append(font['file'])
  if font.get('original_file') and font.get('original_sha256'):
   checked(root,font['original_file'],font['original_sha256']);files.append(font['original_file'])
 # Source-inline original raster assets are also legitimate, but not SVG wrappers.
 source=checked(root,r['original_source_code'],r['source_code_sha256']).decode()
 uri_re=r'data:image/[A-Za-z0-9.+-]+(?:;[^,\s<>"\']*)?,[A-Za-z0-9+/=%._~-]+'
 for uri in re.findall(uri_re,source):
  header,payload=uri.split(',',1)
  if 'svg' in header:continue
  try:allowed.add(sha(base64.b64decode(payload) if ';base64' in header else urllib.parse.unquote_to_bytes(payload)))
  except Exception:pass
 ref=Image.open(io.BytesIO(reference)).convert('RGBA');refpixel=sha(ref.tobytes());images=[]
 for c in E.fromstring(xml).iter('mxCell'):
  style=dict(v.split('=',1) for v in c.get('style','').split(';') if '=' in v)
  uri=style.get('image')
  if not uri:continue
  if not uri.startswith('data:image/'):raise ValueError('external_or_unverified_image: '+str(c.get('id')))
  header,payload=uri.split(',',1)
  if 'svg' in header:raise ValueError('vector_image_requires_editable_objects: '+str(c.get('id')))
  # drawio commonly omits the literal ;base64 marker in style image values.
  data=base64.b64decode(payload)
  if sha(data) not in allowed:raise ValueError('raster_not_in_original_assets: '+str(c.get('id')))
  image=Image.open(io.BytesIO(data)).convert('RGBA')
  if sha(data)==sha(reference) or image.size==ref.size and sha(image.tobytes())==refpixel:
   raise ValueError('whole_reference_image_wrapper')
  images.append({'cell':c.get('id'),'sha256':sha(data)})
 return {'verified_files':sorted(set(files)),'verified_raster_cells':images}

def structure_checks(xml):
 from harness_context import structure
 result=structure(xml,{})
 if not result['ok']:raise ValueError('invalid_editable_structure: '+json.dumps(result['errors']))
 root=E.fromstring(xml);models=list(root.iter('mxGraphModel'))
 if len(models)!=1:raise ValueError('exactly_one_native_page_required')
 if root.tag=='mxfile' and len(root.findall('diagram'))!=1:raise ValueError('multiple_pages_not_silently_selected')
 parents={c:p for p in models[0].iter() for c in p}
 ids={c.get('id') or parents[c].get('id') for c in models[0].iter('mxCell')}
 for c in models[0].iter('mxCell'):
  if c.get('parent') and c.get('parent') not in ids:raise ValueError('dangling_parent')
 return {k:v for k,v in result.items() if k!='labels'}

def rgb(data):
 im=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
 return bg.convert('RGB')

def require_rendered_text(xml,render):
 root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};expected=set()
 for cell in root.iter('mxCell'):
  wrapper=parents.get(cell);value=cell.get('value')
  if value is None and wrapper is not None:value=wrapper.get('label','')
  if not html.unescape(re.sub('<[^>]*>','',value or '')).strip():continue
  cid=cell.get('id') or wrapper.get('id');expected.add(cid)
  if cell.get('visible')=='0':raise ValueError('source_text_cell_hidden: '+str(cid))
 actual=set()
 for row in render.get('actual_text_positions',[]):
  if any(c.get('text','').strip() and c.get('width',0)>0 and c.get('height',0)>0 for run in row.get('runs',[]) for c in run.get('chars',[])):actual.add(row['cell'])
 if expected-actual:raise ValueError('source_text_missing_from_actual_render: '+','.join(sorted(expected-actual)))
 return {'expected_text_objects':len(expected),'actually_positioned_text_objects':len(actual),'all_source_text_objects_rendered':True}

def image_quality(reference,png,record,text_positions=None):
 """Fixed global+foreground-local gates; white background cannot hide a blank result."""
 a=rgb(reference);b=rgb(png);registered=False
 if a.size!=b.size:
  contract=record.get('native_canvas_contract')
  padding=record.get('native_page_padding')
  offset=(contract or {}).get('offset') or (padding or {}).get('offset')
  if isinstance(offset,dict):offset=[offset.get('x'),offset.get('y')]
  if not offset or len(offset)!=2:raise ValueError('unregistered_reference_canvas_difference')
  x,y=map(int,offset)
  if min(x,y)<0 or x+a.width>b.width or y+a.height>b.height:raise ValueError('invalid_reference_page_registration')
  bg=Image.new('RGB',b.size,'white');bg.paste(a,(x,y));a=bg;registered=True
 exact=np.array_equal(np.array(a),np.array(b))
 # Shared proportional downsample only after exact canvas registration.
 scale=min(1,1024/max(a.size));size=tuple(max(8,round(v*scale)) for v in a.size)
 aa=np.array(a.resize(size,Image.Resampling.LANCZOS));bb=np.array(b.resize(size,Image.Resampling.LANCZOS))
 ssim=float(structural_similarity(aa,bb,channel_axis=2,data_range=255))
 ia=np.min(aa,axis=2)<225;ib=np.min(bb,axis=2)<225
 def expanded(mask):return np.array(Image.fromarray(mask.astype('uint8')*255).filter(ImageFilter.MaxFilter(5)))>0
 recall=float((ia&expanded(ib)).sum()/max(1,ia.sum()));precision=float((ib&expanded(ia)).sum()/max(1,ib.sum()))
 tiles=[]
 for y in range(0,size[1],96):
  for x in range(0,size[0],96):
   ca=aa[y:y+96,x:x+96];cb=bb[y:y+96,x:x+96];ink=ia[y:y+96,x:x+96]
   if min(ca.shape[:2])<7 or ink.sum()<max(12,ink.size*.01):continue
   tiles.append(float(structural_similarity(ca,cb,channel_axis=2,data_range=255)))
 p10=float(np.percentile(tiles,10)) if tiles else 0.
 local=[]
 # Inspect every rendered text line at native resolution, not only the silhouette.
 for row in text_positions or []:
  for run in row.get('runs',[]):
   lines={}
   for char in run.get('chars',[]):
    if not char.get('text','').strip() or char.get('width',0)<=0 or char.get('height',0)<=0:continue
    key=round(char['y']/2)*2;lines.setdefault(key,[]).append(char)
   for chars in lines.values():
    x0=max(0,int(np.floor(min(c['x'] for c in chars)))-2);y0=max(0,int(np.floor(min(c['y'] for c in chars)))-2)
    x1=min(a.width,int(np.ceil(max(c['x']+c['width'] for c in chars)))+2);y1=min(a.height,int(np.ceil(max(c['y']+c['height'] for c in chars)))+2)
    if x1-x0<3 or y1-y0<3:continue
    ar=np.array(a.crop((x0,y0,x1,y1)));br=np.array(b.crop((x0,y0,x1,y1)));win=min(7,min(ar.shape[:2]));win-=int(win%2==0)
    rawscore=float(structural_similarity(ar,br,channel_axis=2,data_range=255,win_size=win));score=rawscore;shift=[0,0]
    # PDF and browser glyph baselines can differ by a few device pixels.  Permit
    # bounded local registration, while source geometry is checked independently.
    # A missing/hidden word still has no matching ink in this fixed small window.
    radius=max(2,min(4,round((y1-y0)*.15)))
    if score<.55:
     for dy in range(-radius,radius+1):
      for dx in range(-radius,radius+1):
       if not(0<=x0+dx and 0<=y0+dy and x1+dx<=a.width and y1+dy<=a.height):continue
       shifted=np.array(a.crop((x0+dx,y0+dy,x1+dx,y1+dy)))
       candidate=float(structural_similarity(shifted,br,channel_axis=2,data_range=255,win_size=win))
       if candidate>score:score=candidate;shift=[dx,dy]
    local.append({'cell':row['cell'],'box':[x0,y0,x1,y1],'ssim':score,'unregistered_ssim':rawscore,'registration_shift':shift,'registration_radius':radius})
 inkfrac=float(ib.mean());failures=[]
 if not ia.any() or not ib.any():failures.append('blank_reference_or_native_render')
 if ssim<.90:failures.append('global_fidelity_below_0.90')
 if p10<.72:failures.append('foreground_tile_p10_below_0.72')
 if min(recall,precision)<.90:failures.append('foreground_coverage_below_0.90')
 if local and min(v['ssim'] for v in local)<.55:failures.append('local_text_line_ssim_below_0.55')
 return {'ok':not failures,'failures':failures,'exact_reference_pixels':bool(exact),'ssim_1024':ssim,'foreground_recall_2px':recall,'foreground_precision_2px':precision,'foreground_tile_p10_ssim':p10,'foreground_tiles':len(tiles),'native_ink_fraction':inkfrac,'registered_canvas':registered,'text_regions_checked':len(local),'worst_text_regions':sorted(local,key=lambda x:x['ssim'])[:20],'thresholds':{'ssim':.90,'tile_p10':.72,'foreground_precision_recall':.90,'each_text_line_ssim':.55},'scope':'Raster anomaly gate combined with independent full source coverage; never used alone.'}

def native_source_profile(record,xml,source):
 """Native original content must survive canonicalization, without semantic redrawing."""
 from native_worker import normalize
 baseline,pages,_=normalize(source)
 if pages!=1:return {'supported':True,'ok':False,'profile':'original_native_xml','failures':['multi_page_source_requires_explicit_conversion'],'evidence':{}}
 def fingerprint(text):
  model=E.fromstring(text).find('.//mxGraphModel')
  def node(element):
   attrs=dict(element.attrib)
   if element.tag=='mxGraphModel':attrs.pop('extFonts',None)
   style=attrs.pop('style',None)
   if style is not None:attrs['style']=';'.join(sorted(v for v in style.split(';') if v and not v.startswith(('fontFamily=','fontSource='))))
   return (element.tag,attrs,(element.text or '').strip(),[node(c) for c in element])
  return node(model)
 ok=fingerprint(baseline)==fingerprint(xml)
 return {'supported':True,'ok':ok,'profile':'original_native_xml','failures':[] if ok else ['native_source_objects_geometry_or_terminals_changed'],'evidence':{'unchanged_source_objects_except_portable_font_styles':ok,'source_pages':pages}}
