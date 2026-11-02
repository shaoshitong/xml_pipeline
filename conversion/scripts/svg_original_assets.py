"""Resolve original SVG image references from verified dataset assets, without network access."""
import base64,html,urllib.parse,xml.etree.ElementTree as E
from harness_context_v3 import build_context,sha
E.register_namespace('','http://www.w3.org/2000/svg');E.register_namespace('xlink','http://www.w3.org/1999/xlink')

def resolve(source,inp,previous,work):
 ctx=build_context(source,inp,previous,work);root=E.fromstring(ctx['code']);used=[]
 for element in root.iter():
  if element.tag.rsplit('}',1)[-1]!='image':continue
  name='href' if 'href' in element.attrib else '{http://www.w3.org/1999/xlink}href';ref=element.get(name)
  if not ref:raise ValueError('source SVG image has no href')
  if ref.startswith('data:'):
   header,encoded=ref.split(',',1);data=base64.b64decode(encoded) if ';base64' in header else urllib.parse.unquote_to_bytes(encoded);digest=sha(data);matches=[a for a in ctx['assets'].values() if digest==a['original_sha256']]
  else:
   alias=urllib.parse.unquote(html.unescape(ref)).removeprefix('./');matches=[a for a in ctx['assets'].values() if alias in [x.removeprefix('./') for x in a['aliases']]]
  if len(matches)!=1:raise ValueError('SVG image reference missing/ambiguous or not an allowed original raster: '+ref[:160])
  asset=matches[0];element.set(name,'data:'+asset['mime']+';base64,'+base64.b64encode(asset['bytes']).decode());used.append({'source_href':ref[:200] if not ref.startswith('data:') else 'inline_original_source','asset_id':asset['id'],'original_sha256':asset['original_sha256'],'embedded_sha256':asset['embedded_sha256']})
 return E.tostring(root,encoding='unicode'),used,ctx
