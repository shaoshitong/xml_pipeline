"""Embed the physical OpenType face observed in the native renderer, preserving synthetic styles."""
import base64,collections,hashlib,io,json,subprocess,urllib.parse,xml.etree.ElementTree as E
from pathlib import Path
from fontTools.ttLib import TTFont
from native_worker import R,W,native
from pdf_to_native import attach_fonts

DRAW=r'''async xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';const g=new Graph(document.getElementById('g'));window.fontProbeGraph=g;const d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();const rows=[];for(const c of Object.values(g.model.cells)){const label=g.getLabel(c),s=g.view.getState(c);if(typeof label!=='string'||!label.trim()||!s?.text?.node)continue;const id='fontprobe_'+rows.length;s.text.node.id=id;const walker=document.createTreeWalker(s.text.node,NodeFilter.SHOW_TEXT),parents=new Set();while(walker.nextNode())if(walker.currentNode.textContent.trim())parents.add(walker.currentNode.parentElement);const selectors=[...parents].map((el,i)=>{el.id=id+'_'+i;return '#'+el.id});rows.push({cell:c.id,selector:'#'+id,selectors,label,style:g.getCellStyle(c),bbox:{x:s.x,y:s.y,width:s.width,height:s.height}});}return rows;}'''

def capture(page,xml):
 rows=page.evaluate(DRAW,xml);cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId']
 for r in rows:
  seen={}
  for selector in r['selectors']:
   node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId']
   for font in cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']:
    key=(font['postScriptName'],font['isCustomFont']);seen.setdefault(key,{**font,'glyphCount':0})['glyphCount']+=font['glyphCount']
  r['actual_fonts']=list(seen.values())
 cdp.detach();page.evaluate('fontProbeGraph.destroy();delete window.fontProbeGraph');return rows

def catalog():
 rows=collections.defaultdict(list)
 for line in subprocess.check_output(['fc-list','--format=%{postscriptname}\t%{file}\t%{index}\n'],text=True).splitlines():
  parts=line.split('\t')
  if len(parts)!=3:continue
  ps,file,index=parts
  if Path(file).suffix.lower() not in ('.ttf','.otf','.ttc','.woff','.woff2'):continue
  for name in ps.split(','):rows[name].append((file,int(index or 0)))
 return rows

def embed(xml,observations,directory):
 root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};cells={c.get('id') or parents[c].get('id'):c for c in root.iter('mxCell')};cat=catalog();fonts={};changes=[];issues=[]
 for r in observations:
  c=cells[r['cell']];style=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);actual=[f for f in r['actual_fonts'] if f['glyphCount']]
  if len(actual)!=1:issues.append({'cell':r['cell'],'reason':'mixed_or_missing_physical_font_requires_text_run_split','fonts':actual});continue
  f=actual[0]
  if f['isCustomFont']:issues.append({'cell':r['cell'],'reason':'existing_custom_font_requires_original_asset_lookup','font':f});continue
  # Inline rich text can encode local formatting beyond the cell flags; do not flatten it.
  if '<' in r['label'] and '>' in r['label']:issues.append({'cell':r['cell'],'reason':'inline_rich_text_requires_per_span_font_preservation'});continue
  matches=cat.get(f['postScriptName'],[]);unique={}
  for file,index in matches:
   blob=Path(file).read_bytes();key=(hashlib.sha256(blob).hexdigest(),index);unique[key]=(file,index,blob)
  if len(unique)!=1:issues.append({'cell':r['cell'],'reason':'physical_postscript_font_missing_or_ambiguous','postscript':f['postScriptName'],'matches':list(unique)});continue
  (_,index),(file,index,blob)=next(iter(unique.items()));ft=TTFont(io.BytesIO(blob),fontNumber=index);fs_type=ft['OS/2'].fsType if 'OS/2' in ft else 0
  if 'fvar' in ft:issues.append({'cell':r['cell'],'reason':'variable_font_requires_explicit_axis_preservation'});ft.close();continue
  if fs_type&0x2 or fs_type&0x200:issues.append({'cell':r['cell'],'reason':'font_embedding_restricted_by_font_flags','fsType':fs_type});ft.close();continue
  physical_bold=bool(ft['OS/2'].fsSelection&0x20) if 'OS/2' in ft else bool(ft['head'].macStyle&1);physical_italic=bool(ft['OS/2'].fsSelection&1) if 'OS/2' in ft else bool(ft['head'].macStyle&2);flags=int(r['style'].get('fontStyle',0));newflags=flags
  if physical_bold:newflags&=~1
  if physical_italic:newflags&=~2
  if blob[:4]==b'ttcf':buf=io.BytesIO();ft.save(buf);embedded=buf.getvalue()
  else:embedded=blob
  ft.close();digest=hashlib.sha256(embedded).hexdigest();family='NativeFace_'+digest[:20];ext='.otf' if embedded[:4]==b'OTTO' else '.ttf';path=directory/(digest+ext);directory.mkdir(parents=True,exist_ok=True);path.write_bytes(embedded);mime='font/otf' if ext=='.otf' else 'font/ttf';uri='data:'+mime+';base64,'+base64.b64encode(embedded).decode();fonts[family]={'family':family,'file':str(path),'sha256':digest,'uri':uri,'physical_postscript_name':f['postScriptName'],'physical_family_name':f['familyName'],'original_file':file,'collection_index':index,'original_sha256':hashlib.sha256(blob).hexdigest(),'fsType':fs_type,'physical_bold':physical_bold,'physical_italic':physical_italic};style['fontFamily']=family;style['fontStyle']=str(newflags);c.set('style',';'.join(k+'='+v for k,v in style.items())+';');changes.append({'cell':r['cell'],'before_family':r['style'].get('fontFamily'),'before_flags':flags,'after_flags':newflags,'family':family,'actual_font':f})
 out=attach_fonts(E.tostring(root,encoding='unicode'),fonts) if fonts else xml
 return out,fonts,{'changes':changes,'issues':issues,'text_cells_observed':len(observations),'font_files':len(fonts),'quality_state':'requires_actual_native_pixel_and_custom_font_validation'}

def ready_page(browser):
 page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));return page
