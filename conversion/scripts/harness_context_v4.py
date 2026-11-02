"""Preserve all verified prior physical font assets across model compaction/hydration."""
import base64,json,urllib.parse,xml.etree.ElementTree as E
import harness_context_v3 as core
from harness_context_v3 import prompt_assets,structure,sha
from native_worker import R

def font_uri(f):
 return 'data:'+('font/otf' if f['bytes'][:4]==b'OTTO' else 'font/ttf')+';base64,'+base64.b64encode(f['bytes']).decode()
def build_context(source,inp,previous,work):
 ctx=core.build_context(source,inp,previous,work);verified=previous or {}
 if verified.get('source_font_recovery_archive'):
  path=(R/verified['source_font_recovery_archive']).resolve();assert path.is_relative_to(R/'conversion/harness_sessions');recovered=json.loads((path/'conversion.json').read_text());assert recovered['id']==verified['id'] and recovered['source_code_sha256']==verified['source_code_sha256'] and recovered['source_image_sha256']==verified['source_image_sha256'];verified=recovered
 ctx['verified_source_record']=verified
 for f in (previous or {}).get('native_embedded_fonts',[])+verified.get('native_embedded_fonts',[]):
  path=(R/f['file']).resolve();assert path.is_relative_to(R/'clean');blob=path.read_bytes();assert sha(blob)==f['sha256']
  if f.get('original_file') and f.get('original_sha256'):
   op=(R/f['original_file']).resolve();assert op.is_relative_to(R/'clean') and sha(op.read_bytes())==f['original_sha256']
  if f['family'] in ctx['fonts']:assert ctx['fonts'][f['family']]['sha256']==f['sha256'],'Conflicting physical font alias'
  ctx['fonts'][f['family']]={**f,'bytes':blob}
 audit=json.loads((work/'context.json').read_text());audit['fonts']=[{k:v for k,v in f.items() if k!='bytes'} for f in ctx['fonts'].values()];audit['native_embedded_fonts_preserved']=True;(work/'context.json').write_text(json.dumps(audit,indent=2))
 return ctx

def validate_font_resources(xml,ctx):
 root=E.fromstring(xml);allowed={f['sha256'] for f in ctx['fonts'].values()};declared=[]
 def digest(uri):
  assert uri.startswith('data:') and ';base64,' in uri,'Unapproved external font resource'
  return sha(base64.b64decode(uri.split(',',1)[1],validate=True))
 for m in root.iter('mxGraphModel'):
  for entry in m.get('extFonts','').split('|'):
   if not entry:continue
   name,uri=entry.split('^',1);assert name in ctx['fonts'] and digest(uri)==ctx['fonts'][name]['sha256'],'Embedded font absent from verified original registry';declared.append(name)
 for c in root.iter('mxCell'):
  styles=dict(s.split('=',1) for s in c.get('style','').split(';') if '=' in s)
  if styles.get('fontSource'):assert digest(urllib.parse.unquote(styles['fontSource'])) in allowed,'Unverified cell font payload'
 return declared

def compact_xml(xml,ctx):
 validate_font_resources(xml,ctx);return core.compact_xml(xml,ctx)

def hydrate(xml,ctx):
 validate_font_resources(xml,ctx);xml,used=core.hydrate(xml,ctx);root=E.fromstring(xml)
 for m in root.iter('mxGraphModel'):
  if ctx['fonts']:m.set('extFonts','|'.join(name+'^'+font_uri(f) for name,f in sorted(ctx['fonts'].items())))
  else:m.attrib.pop('extFonts',None)
 seen=set()
 for c in root.iter('mxCell'):
  pieces=[p for p in c.get('style','').split(';') if p and not p.startswith('fontSource=')];style=dict(s.split('=',1) for s in pieces if '=' in s);family=style.get('fontFamily','').split(',')[0].strip('"\' ')
  if family in ctx['fonts'] and family not in seen:pieces.append('fontSource='+urllib.parse.quote(font_uri(ctx['fonts'][family]),safe=''));seen.add(family)
  c.set('style',';'.join(pieces)+';')
 result=E.tostring(root,encoding='unicode');validate_font_resources(result,ctx);return result,used

def verify_source_fullname_faces(previous,native_render):
 mappings=(previous or {}).get('native_source_font_repair',{}).get('mappings',[])
 if not mappings:return {'ok':True,'applicable':False}
 usage={x['cell']:x['fonts'] for x in native_render['actual_platform_font_usage']};texts={}
 for row in native_render['actual_text_positions']:
  text=''.join(x['text'] for x in row['runs']);texts.setdefault(text,[]).append(row['cell'])
 checked=[]
 for m in mappings:
  expected={f['postScriptName'] for f in m['actual_fonts'] if f['glyphCount']};ids=texts.get(m['text'],[]);assert ids,'Verified source text missing: '+m['text']
  for id in ids:
   actual=[f for f in usage[id] if f['glyphCount']];assert actual and all(f['isCustomFont'] for f in actual) and {f['postScriptName'] for f in actual}==expected,'Verified source full-name physical face changed or became unembedded: '+m['text'];checked.append({'cell':id,'text':m['text'],'physical_faces':sorted(expected)})
 return {'ok':True,'applicable':True,'checked':checked}
