"""Verified original context and portable source-asset resolution for remote Harness repairs."""
import base64,hashlib,html,io,json,re,urllib.parse,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from native_worker import R
sha=lambda b:hashlib.sha256(b).hexdigest()
DATA_IMAGE=re.compile(r'data:image/[A-Za-z0-9.+-]+(?:;[^,\s<>"\']*)?,[A-Za-z0-9+/=%._~-]+')

def build_context(source,inp,previous,work):
 reference=(R/inp['reference_image']).read_bytes();code=(R/inp['source_code']).read_text();assert sha(reference)==source['image_sha256'] and sha(code.encode())==source['code_sha256'];ref=Image.open(io.BytesIO(reference));width,height=ref.size;pixelsha=sha(ref.convert('RGBA').tobytes());assets={};aliases={};vectors=[];unresolved=[];excluded=[]
 def add(data,name,origin,expected=None):
  h=sha(data)
  if expected:assert h==expected,'original asset hash mismatch'
  try:im=Image.open(io.BytesIO(data));im.load()
  except Exception:
   if name.lower().endswith('.svg'):
    vectors.append({'source_name':name,'source':origin,'code':data.decode(),'sha256':h});return
   raise ValueError('unreadable referenced image asset '+name)
  if h==sha(reference) or im.size==(width,height) and sha(im.convert('RGBA').tobytes())==pixelsha:
   excluded.append({'source_name':name,'source':origin,'reason':'whole_reference_is_not_an_allowed_asset'});aliases[name]='REFERENCE_NOT_ALLOWED';return
  key='asset_'+h[:16];aliases[name]=key
  if key in assets:assets[key]['aliases'].append(name);return
  mime='image/jpeg' if im.format=='JPEG' else 'image/png';blob=data
  if im.format not in ('PNG','JPEG'):
   b=io.BytesIO();im.convert('RGBA').save(b,format='PNG');blob=b.getvalue()
  folder=work/'source_assets';folder.mkdir(exist_ok=True);ext='.jpg' if mime=='image/jpeg' else '.png';path=folder/(key+ext);path.write_bytes(blob);original=folder/(key+'.original');original.write_bytes(data)
  assets[key]={'id':key,'aliases':[name],'original_source':origin,'original_sha256':h,'embedded_sha256':sha(blob),'mime':mime,'width':im.width,'height':im.height,'file':str(path),'original_file':str(original),'bytes':blob,'original_bytes':data}
 for a in inp.get('panel_assets') or []:
  f=R/a['file'];add(f.read_bytes(),a['source_name'],a['file'],a['sha256'])
  key=aliases[a['source_name']]
  for panel in source.get('panel_assets',[]):
   if panel.get('image_sha256')==a['sha256'] and key in assets:
    for alias in panel.get('allowed_svg_references',[]):
     if alias not in assets[key]['aliases']:assets[key]['aliases'].append(alias)
     aliases[alias]=key
 asset_root=inp.get('asset_root') or source.get('asset_root');asset_root=(R/asset_root).resolve() if asset_root else None
 if asset_root:assert asset_root.is_relative_to(R/'clean') and asset_root.is_dir()
 # Preserve all available source image assets, not only a critic's chosen subset.
 if asset_root:
  for f in sorted(asset_root.rglob('*')):
   if not f.is_file() or f.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif','.bmp','.tif','.tiff','.svg'}:continue
   assert f.resolve().is_relative_to(asset_root),'asset symlink escapes original source asset root';add(f.read_bytes(),str(f.relative_to(asset_root)),str(f.relative_to(R)))
 for a in (previous or {}).get('source_assets',[]):
  origin=a.get('original_file') or a.get('source','')
  if not origin.startswith('clean/'):continue
  f=(R/origin).resolve();assert f.is_relative_to(R/'clean');add(f.read_bytes(),f.name,origin,a.get('original_sha256') or a.get('source_sha256'))
 source_for_prompt=code
 for n,uri in enumerate(dict.fromkeys(DATA_IMAGE.findall(code))):
  header,encoded=uri.split(',',1);blob=base64.b64decode(encoded) if ';base64' in header else urllib.parse.unquote_to_bytes(encoded);name='embedded_original_'+str(n)
  if 'image/svg+xml' in header:
   name+='.svg';add(blob,name,'inline_original_source');source_for_prompt=source_for_prompt.replace(uri,'vector-asset://'+sha(blob)[:16])
  else:add(blob,name,'inline_original_source');source_for_prompt=source_for_prompt.replace(uri,'asset://'+aliases[name])
 auxiliary=None
 if inp.get('source_data'):
  blob=(R/inp['source_data']).read_bytes();assert sha(blob)==inp['source_data_sha256'];auxiliary={'text':blob.decode(),'sha256':sha(blob),'locator':inp.get('source_data_locator')}
 fonts={}
 for f in (previous or {}).get('fonts',[]):
  path=(R/f['file']).resolve();assert path.is_relative_to(R/'clean');data=path.read_bytes();assert sha(data)==f['sha256'];fonts[f['family']]={**f,'bytes':data}
 required=set()
 references=re.findall(r'<(?:img|image)\b[^>]*?\b(?:src|href|xlink:href)\s*=\s*["\']([^"\']+)',source_for_prompt,re.I|re.S)
 references+=re.findall(r'url\(\s*["\']?([^"\')]+)',source_for_prompt,re.I)
 for refname in references:
  name=urllib.parse.unquote(html.unescape(refname)).removeprefix('./')
  if name.startswith('asset://') and name[8:] in assets:required.add(name[8:])
  for key,a in assets.items():
   if any(name==alias.removeprefix('./') for alias in a['aliases']):required.add(key)
 for a in (previous or {}).get('source_assets',[]):
  for key,value in assets.items():
   if (a.get('original_sha256') or a.get('source_sha256'))==value['original_sha256']:required.add(key)
 context={'reference':reference,'code':code,'source_for_prompt':source_for_prompt,'width':width,'height':height,'assets':assets,'asset_root':str(asset_root.relative_to(R)) if asset_root else None,'auxiliary':auxiliary,'fonts':fonts,'vector_assets':vectors,'unresolved':unresolved,'excluded_reference_assets':excluded,'required_asset_ids':sorted(required)}
 audit={k:context[k] for k in ['width','height','asset_root','unresolved','excluded_reference_assets','required_asset_ids']};audit.update(original_image_sha256=sha(reference),original_code_sha256=sha(code.encode()),assets=[{k:v for k,v in a.items() if k not in ('bytes','original_bytes')} for a in assets.values()],auxiliary={k:v for k,v in auxiliary.items() if k!='text'} if auxiliary else None,fonts=[{k:v for k,v in f.items() if k!='bytes'} for f in fonts.values()],vector_assets=[{k:v for k,v in a.items() if k!='code'} for a in vectors]);(work/'context.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return context

def prompt_assets(ctx):
 return [{k:a[k] for k in ['id','aliases','mime','width','height','original_sha256']} for a in ctx['assets'].values()]

def compact_xml(xml,ctx):
 root=E.fromstring(xml)
 for m in root.iter('mxGraphModel'):m.attrib.pop('extFonts',None)
 for c in root.iter('mxCell'):
  parts=c.get('style','').split(';');new=[]
  for part in parts:
   if part.startswith('fontSource='):continue
   if part.startswith('image=data:'):
    uri=part[6:];header,encoded=uri.split(',',1)
    try:blob=base64.b64decode(encoded);h=sha(blob);matches=[a['id'] for a in ctx['assets'].values() if h in [a['original_sha256'],a['embedded_sha256']]]
    except Exception:matches=[]
    if len(matches)!=1:raise ValueError('candidate contains an image absent from original asset allowlist')
    part='image=asset://'+matches[0]
   new.append(part)
  c.set('style',';'.join(new))
 return E.tostring(root,encoding='unicode')

def hydrate(xml,ctx):
 root=E.fromstring(xml);used=[];seenfonts=set()
 for c in root.iter('mxCell'):
  bare=[x for x in c.get('style','').split(';') if x and '=' not in x];styles=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x)
  image=styles.get('image')
  if image:
   if image.startswith('asset://'):
    key=image[8:]
    if key not in ctx['assets']:raise ValueError('unknown source asset token '+key)
    a=ctx['assets'][key];styles['image']='data:'+a['mime']+','+base64.b64encode(a['bytes']).decode();used.append({'cell':c.get('id'),'asset_id':key,'sha256':a['embedded_sha256']})
   elif image.startswith('data:'):
    try:blob=base64.b64decode(image.split(',',1)[1]);h=sha(blob)
    except Exception:raise ValueError('malformed raster resource')
    keys=[a['id'] for a in ctx['assets'].values() if h==a['embedded_sha256']]
    if len(keys)!=1:raise ValueError('raster must be a verified original source asset')
    used.append({'cell':c.get('id'),'asset_id':keys[0],'sha256':h})
   else:raise ValueError('external image resource forbidden')
  family=styles.get('fontFamily');styles.pop('fontSource',None)
  if family in ctx['fonts'] and family not in seenfonts:
   styles['fontSource']=urllib.parse.quote('data:font/otf;base64,'+base64.b64encode(ctx['fonts'][family]['bytes']).decode(),safe='');seenfonts.add(family)
  c.set('style',';'.join(bare+[k+'='+v for k,v in styles.items()])+';')
 for m in root.iter('mxGraphModel'):
  m.attrib.pop('extFonts',None)
  if seenfonts:m.set('extFonts','|'.join(name+'^data:font/otf;base64,'+base64.b64encode(ctx['fonts'][name]['bytes']).decode() for name in sorted(seenfonts)))
 return E.tostring(root,encoding='unicode'),used

def structure(xml,ctx):
 root=E.fromstring(xml);model=root.find('.//mxGraphModel') if root.tag!='mxGraphModel' else root;cells=list(model.iter('mxCell'));parents={c:p for p in model.iter() for c in p};cid=lambda c:c.get('id') or parents.get(c,E.Element('none')).get('id');label=lambda c:c.get('value') if c.get('value') is not None else parents.get(c,E.Element('none')).get('label','');ids=[cid(c) for c in cells];vertices={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];errors=[];visible_native=0;images=[]
 if not vertices:errors.append('no_editable_vertices')
 if not all(ids) or len(ids)!=len(set(ids)):errors.append('invalid_or_duplicate_ids')
 if any(e.get('source') not in vertices or e.get('target') not in vertices for e in edges):errors.append('unbound_or_invalid_edges')
 for c in cells:
  st=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);g=c.find('mxGeometry')
  if c.get('vertex')=='1' and st.get('opacity','100')!='0' and g is not None:
   if 'image' in st:images.append(cid(c))
   elif label(c) or st.get('fillColor','default')!='none' or st.get('strokeColor','default')!='none':visible_native+=1
  if re.search(r'<\s*(?:img|script|iframe|object)\b|javascript:',html.unescape(label(c)),re.I):errors.append('active_or_unverified_html_resource')
 if not visible_native:errors.append('no_visible_native_objects')
 if re.search(r'javascript:|file://',xml,re.I):errors.append('active_or_file_resource')
 return {'ok':not errors,'errors':errors,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'source_asset_image_cells':images,'visible_native_objects':visible_native,'labels':[html.unescape(re.sub('<[^>]+>',' ',label(c))) for c in cells if label(c)]}
