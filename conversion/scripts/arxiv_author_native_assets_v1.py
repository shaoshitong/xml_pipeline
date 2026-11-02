"""Bounded decoded-model dependency inventory; no importer or external fetch."""
from pathlib import Path
import base64,hashlib,html,io,json,mimetypes,re,urllib.parse,xml.etree.ElementTree as ET,zlib
from html.parser import HTMLParser
import tinycss2
from PIL import Image
LIMIT=64*1024**2
sha=lambda b:hashlib.sha256(b).hexdigest()
def models(xml):
 blob=xml.encode() if isinstance(xml,str) else xml
 if len(blob)>LIMIT or b'<!DOCTYPE' in blob.upper() or b'<!ENTITY' in blob.upper():raise ValueError('XML_size_or_DTD_not_supported')
 root=ET.fromstring(blob)
 if root.tag=='mxGraphModel':return root,[root]
 if root.tag!='mxfile':raise ValueError('not_drawio_XML')
 result=[]
 for page in root.findall('diagram'):
  model=page.find('mxGraphModel')
  if model is None:
   text=(page.text or '').strip()
   if text.startswith('<'):decoded=text.encode()
   else:
    compressed=base64.b64decode(''.join(text.split()),validate=True);decoder=zlib.decompressobj(-15);encoded=decoder.decompress(compressed,LIMIT+1)
    if len(encoded)>LIMIT or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:raise ValueError('invalid_or_unbounded_compressed_model')
    decoded=urllib.parse.unquote(encoded.decode(),errors='strict').encode()
   if len(decoded)>LIMIT or b'<!DOCTYPE' in decoded.upper() or b'<!ENTITY' in decoded.upper():raise ValueError('decoded_model_size_or_DTD_not_supported')
   model=ET.fromstring(decoded)
  if model.tag!='mxGraphModel':raise ValueError('decoded_page_not_graph_model')
  result.append(model)
 if not result:raise ValueError('no_graph_model')
 return root,result
def style_tokens(style):
 matches=list(re.finditer(r'(?:^|;)([A-Za-z_][\w-]*)=',style or ''));out=[]
 for i,m in enumerate(matches):
  end=matches[i+1].start() if i+1<len(matches) else len(style);value=style[m.end():end].removesuffix(';');out.append((m.group(1),value,m.end(),end))
 return out
def css(css,found,families,role='CSS_asset'):
 def tokens(values):
  for token in values:
   if token.type=='url':found.append((role,token.value))
   elif token.type=='function':
    if token.lower_name=='url':found.append((role,tinycss2.serialize(token.arguments).strip().strip('"\'')))
    else:tokens(token.arguments)
   elif hasattr(token,'content') and token.content is not None:tokens(token.content)
 for rule in tinycss2.parse_stylesheet(css,skip_comments=True,skip_whitespace=True):
  if getattr(rule,'content',None):
   for d in tinycss2.parse_declaration_list(rule.content,skip_comments=True,skip_whitespace=True):
    if d.type=='declaration' and d.lower_name=='font-family':families.add(tinycss2.serialize(d.value).strip())
    if d.type=='declaration':tokens(d.value)
  elif getattr(rule,'prelude',None):tokens(rule.prelude)
 # Inline style declarations have no surrounding stylesheet rule.
 for d in tinycss2.parse_declaration_list(css,skip_comments=True,skip_whitespace=True):
  if d.type=='declaration':
   if d.lower_name=='font-family':families.add(tinycss2.serialize(d.value).strip())
   tokens(d.value)
class HTML(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.refs=[];self.families=set();self.styles=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);tag=tag.lower()
  if tag in {'img','image','use','feimage'}:
   for k in ['src','href','xlink:href']:
    if a.get(k):self.refs.append(('HTML_image' if tag=='img' else 'SVG_image',a[k]))
   if a.get('srcset'):self.refs.append(('unsupported_srcset_dependency',a['srcset']))
  if tag=='link' and a.get('rel')=='stylesheet' and a.get('href'):self.refs.append(('CSS_stylesheet',a['href']))
  if tag=='font' and a.get('face'):self.families.add(a['face'])
  if a.get('style'):css(a['style'],self.refs,self.families)
  if tag=='style':self.styles=True
 def handle_endtag(self,tag):
  if tag.lower()=='style':self.styles=False
 def handle_data(self,data):
  if self.styles:css(data,self.refs,self.families)
def svg_refs(blob):
 root=ET.fromstring(blob);refs=[];families=set()
 for n in root.iter():
  tag=n.tag.split('}')[-1].lower()
  if tag in {'image','use','feimage'}:
   for k in ['href','{http://www.w3.org/1999/xlink}href']:
    if n.get(k):refs.append(('embedded_SVG_image',n.get(k)))
  if tag=='style':css(n.text or '',refs,families)
  if n.get('style'):css(n.get('style'),refs,families)
  if n.get('font-family'):families.add(n.get('font-family'))
 return refs,families
def inventory(xml):
 root,ms=models(xml);refs=[];families=set();shapes=set();parents={c:p for m in ms for p in m.iter() for c in p};font_sources=[]
 for page,m in enumerate(ms):
  for entry in (m.get('extFonts') or '').split('|'):
   if entry:
    name,uri=entry.split('^',1);families.add(name);refs.append({'page':page,'cell':None,'role':'extFont','uri':uri})
  background=m.get('backgroundImage')
  if background:
   try:uri=json.loads(background).get('src')
   except Exception:uri=background
   if uri:refs.append({'page':page,'cell':None,'role':'background_image','uri':uri})
  for c in m.iter('mxCell'):
   cid=c.get('id') or parents.get(c,ET.Element('x')).get('id');tokens={k:v for k,v,_,_ in style_tokens(c.get('style',''))}
   if tokens.get('shape'):shapes.add(tokens['shape'])
   if tokens.get('fontFamily'):families.add(tokens['fontFamily'])
   for key,role in [('image','cell_image'),('fontSource','fontSource')]:
    if tokens.get(key):refs.append({'page':page,'cell':cid,'role':role,'uri':urllib.parse.unquote(tokens[key]) if key=='fontSource' else tokens[key]})
   values=[c.get('value','')];p=parents.get(c)
   if p is not None and p.tag!='root' and p.get('label'):values.append(p.get('label'))
   for value in values:
    parser=HTML();parser.feed(value);families.update(parser.families);refs.extend({'page':page,'cell':cid,'role':role,'uri':uri} for role,uri in parser.refs)
 return root,ms,refs,families,shapes
def data_asset(uri):
 head,payload=uri.split(',',1);mime=head[5:].split(';',1)[0] or 'text/plain'
 if ';base64' in head:blob=base64.b64decode(payload,validate=True)
 elif payload.lstrip().startswith(('<','%','{')):blob=urllib.parse.unquote_to_bytes(payload)
 else:
  try:blob=base64.b64decode(payload,validate=True)
  except Exception:blob=urllib.parse.unquote_to_bytes(payload)
 if len(blob)>LIMIT:raise ValueError('inline_asset_above64MiB')
 meta={'mime':mime,'bytes':len(blob),'sha256':sha(blob)}
 if mime.startswith('image/') and mime!='image/svg+xml':
  with Image.open(io.BytesIO(blob)) as image:meta['dimensions']=list(image.size);image.verify()
 if mime.startswith(('font/','application/font','application/x-font')):
  from fontTools.ttLib import TTFont
  font=TTFont(io.BytesIO(blob));meta['font_postscript']=font['name'].getDebugName(6);meta['font_family']=font['name'].getDebugName(1);meta['font_embedding_fsType']=font['OS/2'].fsType if 'OS/2' in font else 0;font.close()
 return blob,meta
def dependencies(xml,author_file,pdf_file,war):
 root,ms,refs,families,shapes=inventory(xml);assets=[];assetmap={};issues=[];visited=set();war_entries=set(war.namelist())
 def one(ref,depth=0):
  uri=ref['uri'];key=(uri,ref['role']);meta={k:v for k,v in ref.items() if k!='uri'};meta.update(uri_sha256=sha(uri.encode()),uri_prefix=uri.split(',',1)[0][:100]);assets.append(meta)
  if key in visited:meta.update(duplicate_reference=True,status='duplicate_reference');return
  visited.add(key)
  if depth>8:meta['status']='pending_nested_asset_depth';issues.append(meta);return
  try:
   if uri.startswith('#'):meta['status']='internal_fragment';return
   if uri.startswith('data:'):
    blob,details=data_asset(uri);meta.update(details,status='inline_verified')
    if details['mime']=='image/svg+xml':
     nested,names=svg_refs(blob);families.update(names)
     for role,u in nested:one(dict(page=ref.get('page'),cell=ref.get('cell'),role=role,uri=u),depth+1)
    return
   p=urllib.parse.urlparse(uri)
   if p.scheme or p.netloc:meta.update(status='pending_external_asset',uri=uri[:1500]);issues.append(meta);return
   if depth>0:meta.update(status='pending_relative_dependency_inside_inline_SVG',uri=uri[:1500]);issues.append(meta);return
   path=urllib.parse.unquote(p.path);entry=urllib.parse.urlparse(urllib.parse.urljoin('http://source.invalid/',uri)).path.lstrip('/');adjacent=(author_file.parent/path).resolve();source=(pdf_file.parent/path).resolve()
   if adjacent.is_file() and adjacent.is_relative_to(author_file.parents[3]):meta.update(status='author_adjacent_file',file=str(adjacent),sha256=sha(adjacent.read_bytes()));assetmap[entry]=adjacent
   elif source.is_file() and '/clean/' in str(source):meta.update(status='source_only_relative_asset_needs_portable_closure',file=str(source),sha256=sha(source.read_bytes()));assetmap[entry]=source;issues.append(meta)
   elif entry in war_entries:meta.update(status='official_runtime_builtin_asset',archive_entry=entry,sha256=sha(war.read(entry)))
   else:meta.update(status='pending_missing_relative_asset',uri=uri[:1500]);issues.append(meta)
  except Exception as e:meta.update(status='pending_asset_decode',reason=type(e).__name__+':'+str(e)[:300]);issues.append(meta)
 for ref in refs:one(ref)
 return {'models':ms,'assets':assets,'issues':issues,'asset_map':assetmap,'declared_font_families':sorted(families),'native_shape_dependencies':sorted(shapes),'raw_XML_asset_self_contained':not issues,'decoded_model_SHA256':[sha(ET.tostring(m)) for m in ms]}
