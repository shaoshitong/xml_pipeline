"""Resolve explicit font full names to exact installed physical faces, without family guessing."""
import base64,copy,hashlib,io,json,subprocess,xml.etree.ElementTree as E
from pathlib import Path
from fontTools.ttLib import TTFont
from native_worker import R,W
from svg_convert_v2 import build as build_v2
from svg_convert_v3 import build as build_v3
sha=lambda b:hashlib.sha256(b).hexdigest()
class NoFullNameFace(Exception):pass

def face_for_fullname(name,directory):
 matches={}
 for line in subprocess.check_output(['fc-list','--format=%{file}\t%{index}\n'],text=True).splitlines():
  path,index=line.rsplit('\t',1);path=Path(path);index=int(index or 0)
  if path.suffix.lower() not in ['.ttf','.otf','.ttc']:continue
  with TTFont(path,fontNumber=index) as ft:
   full={n.toUnicode().casefold() for n in ft['name'].names if n.nameID==4};families={n.toUnicode().casefold() for n in ft['name'].names if n.nameID in [1,16]}
   if name.casefold() not in full or name.casefold() in families:continue
   blob=path.read_bytes();key=(sha(blob),index)
   if key in matches:continue
   assert 'fvar' not in ft,'Variable fullname face requires explicit axes';assert not ft['OS/2'].fsType&0x202,'Restricted physical font embedding';ps={n.toUnicode() for n in ft['name'].names if n.nameID==6};assert len(ps)==1
   if blob[:4]==b'ttcf':buf=io.BytesIO();ft.save(buf);payload=buf.getvalue()
   else:payload=blob
   digest=sha(payload);family='NativeFullFace_'+digest[:20];ext='.otf' if payload[:4]==b'OTTO' else '.ttf';directory.mkdir(exist_ok=True,parents=True);dest=directory/(digest+ext);dest.write_bytes(payload);mime='font/otf' if ext=='.otf' else 'font/ttf';matches[key]={'requested_fullname':name,'family':family,'file':str(dest),'sha256':digest,'uri':'data:'+mime+';base64,'+base64.b64encode(payload).decode(),'original_file':str(path),'original_sha256':sha(blob),'collection_index':index,'physical_postscript_name':next(iter(ps)),'physical_family_name':ft['name'].getDebugName(1),'physical_bold':bool(ft['OS/2'].fsSelection&32),'physical_italic':bool(ft['OS/2'].fsSelection&1),'fsType':ft['OS/2'].fsType}
 assert len(matches)<=1,'Ambiguous fullname physical faces: '+name
 return next(iter(matches.values())) if matches else None

def capture_source(browser,record,directory,width,height):
 key='source_render_svg' if record['source_format']=='python' else 'original_source_code';digest='source_render_svg_sha256' if key=='source_render_svg' else 'source_code_sha256';path=R/record[key];assert path.resolve().is_relative_to(R/'clean');svg=path.read_bytes();assert sha(svg)==record[digest];blocked=[];ctx=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=ctx.new_page();ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()))
 try:
  page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode());page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');before=page.evaluate((W/'scripts/svg_dom.js').read_text());before_png=page.screenshot();specs=page.evaluate('()=>[...document.querySelectorAll("svg text")].map((e,i)=>({index:i,family:getComputedStyle(e).fontFamily,weight:getComputedStyle(e).fontWeight,style:getComputedStyle(e).fontStyle,children:e.children.length}))');fonts={};mapping=[]
  for spec in specs:
   name=spec['family'].strip('"\'')
   if ',' in name:
    components=[x.strip().strip('"\'') for x in spec['family'].split(',')]
    for part in components:
     if part not in fonts:fonts[part]=face_for_fullname(part,directory/'fonts')
    assert not any(fonts[x] for x in components),'Full-name face inside fallback stack requires separate ordering proof'
    continue
   if name not in fonts:fonts[name]=face_for_fullname(name,directory/'fonts')
   f=fonts[name]
   if not f:continue
   assert spec['weight']=='400' and spec['style']=='normal' and spec['children']==0,'Styled/rich full-name source text requires separate face-style mapping'
   mapping.append({'index':spec['index'],'font':f,'requested_fullname':name})
  if not mapping:raise NoFullNameFace('No exact non-family full-name text faces found')
  faces={m['font']['family']:m['font'] for m in mapping};changes=page.evaluate('''async args=>{for(const f of args.faces){const face=new FontFace(f.family,'url('+f.uri+')',{weight:'normal',style:'normal'});await face.load();document.fonts.add(face);}const texts=[...document.querySelectorAll('svg text')],out=[];for(const m of args.mapping){const e=texts[m.index];e.style.fontFamily=m.family;e.dataset.fullnameProbe=String(m.index);out.push({index:m.index,selector:'[data-fullname-probe="'+m.index+'"]',text:e.textContent,family:m.family,requested_fullname:m.requested_fullname});}await document.fonts.ready;document.body.getBoundingClientRect();return out;}''',{'faces':[{'family':f['family'],'uri':f['uri']} for f in faces.values()],'mapping':[{'index':m['index'],'family':m['font']['family'],'requested_fullname':m['requested_fullname']} for m in mapping]});after=page.evaluate((W/'scripts/svg_dom.js').read_text());after_png=page.screenshot();cdp=ctx.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');node=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId']
  for c in changes:
   n=cdp.send('DOM.querySelector',{'nodeId':node,'selector':c['selector']})['nodeId'];used=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':n})['fonts'];c['actual_fonts']=used;assert sum(f['glyphCount'] for f in used)>0 and all(f['isCustomFont'] and f['postScriptName']==faces[c['family']]['physical_postscript_name'] for f in used if f['glyphCount'])
  cdp.detach();assert not blocked,blocked;assert before['sourceText']==after['sourceText'];return before,after,before_png,after_png,faces,changes
 finally:ctx.close()

def patch_native(xml,record,before,after,fonts,width,height):
 versions={'svg_native_v2_group_paint_order':build_v2,'svg_native_v3_group_paint_order_and_native_arrows':build_v3};build=versions[record['svg_conversion']['converter_version']];before_objects={o['id']:o for o in before['objects']};after_objects={o['id']:o for o in after['objects']};assert before_objects.keys()==after_objects.keys();assert before['nodes']==after['nodes'],'Fullname text changes node group bounds; connector-safe layout repair needed';changed=[]
 for id,a in before_objects.items():
  b=after_objects[id]
  if a==b:continue
  assert a['type']==b['type']=='text' and b['fontFamily'].strip('"\'') in fonts
  assert {k:v for k,v in a.items() if k not in ['fontFamily','bbox']}=={k:v for k,v in b.items() if k not in ['fontFamily','bbox']},'Unexpected source object/style change';changed.append(id)
 assert changed;before_xml,_=build(before,width,height);after_xml,_=build(after,width,height);old={c.get('id'):c for c in E.fromstring(before_xml).iter('mxCell')};new={c.get('id'):c for c in E.fromstring(after_xml).iter('mxCell')};root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};details=[]
 for id in changed:
  c=cells[id];expected=old[id];proposed=new[id];assert c.get('value')==expected.get('value')==proposed.get('value');assert c.get('parent')==expected.get('parent')==proposed.get('parent');assert E.canonicalize(E.tostring(c.find('mxGeometry'),encoding='unicode'))==E.canonicalize(E.tostring(expected.find('mxGeometry'),encoding='unicode')),'Native/source text geometry has diverged: '+id
  family=after_objects[id]['fontFamily'].strip('"\'');f=fonts[family];style=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);expected_style=dict(x.split('=',1) for x in proposed.get('style','').split(';') if '=' in x)
  for key in ['fontSize','fontStyle','align','verticalAlign','spacing','whiteSpace','overflow']:assert style.get(key)==expected_style.get(key),(id,key)
  import urllib.parse
  style.update(fontFamily=family,fontSource=urllib.parse.quote(f['uri'],safe=''));c.set('style',';'.join(k+'='+v for k,v in style.items())+';');before_geometry=E.tostring(c.find('mxGeometry'),encoding='unicode');c.remove(c.find('mxGeometry'));c.append(copy.deepcopy(proposed.find('mxGeometry')));details.append({'cell':id,'text':after_objects[id]['text'],'family':family,'requested_fullname':f['requested_fullname'],'physical_postscript_name':f['physical_postscript_name'],'before_geometry':before_geometry,'after_geometry':E.tostring(c.find('mxGeometry'),encoding='unicode'),'source_before_bbox':before_objects[id]['bbox'],'source_after_bbox':after_objects[id]['bbox']})
 model=root.find('.//mxGraphModel');existing=dict(s.split('^',1) for s in model.get('extFonts','').split('|') if s)
 for family,f in fonts.items():assert family not in existing or existing[family]==f['uri'];existing[family]=f['uri']
 model.set('extFonts','|'.join(k+'^'+v for k,v in existing.items()));result=E.tostring(root,encoding='unicode');verify_patch(xml,result,details);return result,details

def verify_patch(before,after,details):
 a=E.fromstring(before);b=E.fromstring(after);old={c.get('id'):c for c in a.iter('mxCell')};new={c.get('id'):c for c in b.iter('mxCell')};oldfonts=dict(s.split('^',1) for s in a.find('.//mxGraphModel').get('extFonts','').split('|') if s);newfonts=dict(s.split('^',1) for s in b.find('.//mxGraphModel').get('extFonts','').split('|') if s);assert all(newfonts.get(k)==v for k,v in oldfonts.items());assert set(newfonts)==set(oldfonts)|{d['family'] for d in details}
 for d in details:
  id=d['cell'];o=old[id];n=new[id];assert o.get('value')==n.get('value');assert E.tostring(o.find('mxGeometry'),encoding='unicode')==d['before_geometry'];assert E.tostring(n.find('mxGeometry'),encoding='unicode')==d['after_geometry'];os=dict(x.split('=',1) for x in o.get('style','').split(';') if '=' in x);ns=dict(x.split('=',1) for x in n.get('style','').split(';') if '=' in x);assert ns['fontFamily']==d['family'];import urllib.parse;assert urllib.parse.unquote(ns['fontSource'])==newfonts[d['family']];assert {k:v for k,v in os.items() if k not in ['fontFamily','fontSource']}=={k:v for k,v in ns.items() if k not in ['fontFamily','fontSource']};n.set('style',o.get('style'));n.remove(n.find('mxGeometry'));n.append(copy.deepcopy(o.find('mxGeometry')))
 b.find('.//mxGraphModel').set('extFonts',a.find('.//mxGraphModel').get('extFonts',''));assert E.canonicalize(E.tostring(a,encoding='unicode'))==E.canonicalize(E.tostring(b,encoding='unicode')),'Non-text graph or content changed'
 return True

def verify_render_fonts(before_render,after_render,changes,source_changes):
 import collections
 from native_text_clip import verify_positions
 def counts(fonts):
  result=collections.Counter()
  for f in fonts:result[f['postScriptName']]+=f['glyphCount']
  return dict(result)
 source={}
 for c in source_changes:
  key=(c['text'],c['family']);v=counts(c['actual_fonts']);assert key not in source or source[key]==v,'Ambiguous source font glyph context';source[key]=v
 actual={r['cell']:r['fonts'] for r in after_render['actual_platform_font_usage']};old={r['cell']:r['fonts'] for r in before_render['actual_platform_font_usage']};changed={c['cell'] for c in changes}
 for c in changes:
  fs=[f for f in actual[c['cell']] if f['glyphCount']];assert fs and all(f['isCustomFont'] and f['postScriptName']==c['physical_postscript_name'] for f in fs),'Native face does not match exact source fullname';assert counts(fs)==source[(c['text'],c['family'])],'Source/native physical glyph counts differ'
 assert {k:v for k,v in actual.items() if k not in changed}=={k:v for k,v in old.items() if k not in changed},'Unchanged text fonts differ'
 verify_positions([r for r in before_render['actual_text_positions'] if r['cell'] not in changed],after_render['actual_text_positions'])
 return True
