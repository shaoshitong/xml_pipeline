"""Preserve mixed-font fallback runs as editable HTML spans, with exact native render gates."""
import html,json,xml.etree.ElementTree as E
from portable_native_fonts import capture,ready_page,embed as embed_single
from pdf_to_native import attach_fonts

def probe_runs(page,observations):
 entries=[]
 for r in observations:
  fs=[f for f in r['actual_fonts'] if f['glyphCount']]
  if len(fs)<2:continue
  if '<' in r['label'] and '>' in r['label']:continue
  entries.append({'cell':r['cell'],'text':html.unescape(r['label']),'family':r['style'].get('fontFamily','Arial'),'size':r['style'].get('fontSize',12),'flags':int(r['style'].get('fontStyle',0))})
 probes=page.evaluate('''items=>{const out=[],segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});for(const row of items){for(const {segment} of segmenter.segment(row.text)){const e=document.createElement('span');e.id='fallback-probe-'+out.length;e.style.cssText='position:absolute;left:-100000px;top:0;white-space:pre;';e.style.fontFamily=row.family;e.style.fontSize=row.size+'px';e.style.fontWeight=row.flags&1?'bold':'normal';e.style.fontStyle=row.flags&2?'italic':'normal';e.textContent=segment;document.body.appendChild(e);out.push({cell:row.cell,text:segment,selector:'#'+e.id});}}return out;}''',entries)
 page.evaluate("async()=>{await document.fonts.ready;for(const e of document.querySelectorAll('[id*=font-probe-],[id^=fallback-probe-]'))e.getBoundingClientRect();}")
 cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId'];runs={}
 for probe in probes:
  node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':probe['selector']})['nodeId'];fonts=[f for f in cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'] if f['glyphCount']];probe['fonts']=fonts;runs.setdefault(probe['cell'],[]).append(probe)
 cdp.detach();page.evaluate("()=>document.querySelectorAll('[id^=fallback-probe-]').forEach(e=>e.remove())");return runs

def probe_primary(page,observations):
 entries=[];keys={};cells={}
 for row in observations:
  key=(str(row['style'].get('fontFamily','Arial')),int(row['style'].get('fontStyle',0)),str(row['style'].get('fontSize',12)))
  if key not in keys:
   keys[key]=len(entries);entries.append({'family':key[0],'flags':key[1],'size':key[2],'index':keys[key]})
  cells[row['cell']]=keys[key]
 selectors=page.evaluate("""items=>items.map(row=>{const e=document.createElement('span');e.id='primary-font-probe-'+row.index;e.style.cssText='position:absolute;left:-100000px;top:0;white-space:pre;';e.style.fontFamily=row.family;e.style.fontSize=row.size+'px';e.style.fontWeight=row.flags&1?'bold':'normal';e.style.fontStyle=row.flags&2?'italic':'normal';e.textContent='M';document.body.appendChild(e);return '#'+e.id;})""",entries)
 page.evaluate("async()=>{await document.fonts.ready;for(const e of document.querySelectorAll('[id*=font-probe-],[id^=fallback-probe-]'))e.getBoundingClientRect();}")
 cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId'];fonts=[]
 for selector in selectors:
  node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId'];fs=[f for f in cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'] if f['glyphCount']];assert len(fs)==1,'Ambiguous primary font metrics: '+str({'entry':entries[len(fonts)],'fonts':fs});fonts.append(fs[0])
 cdp.detach();page.evaluate("()=>document.querySelectorAll('[id^=primary-font-probe-]').forEach(e=>e.remove())");return {cid:fonts[index] for cid,index in cells.items()}

def embed(xml,observations,directory,page):
 root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};cells={c.get('id') or parents[c].get('id'):c for c in root.iter('mxCell')};runs=probe_runs(page,observations);primary_faces=probe_primary(page,observations);fake=E.Element('mxfile');m=E.SubElement(E.SubElement(fake,'diagram'),'mxGraphModel');cr=E.SubElement(m,'root');fakeobs=[];mapping={};issues=[]
 for row in observations:
  actual=[f for f in row['actual_fonts'] if f['glyphCount']]
  if not actual:issues.append({'cell':row['cell'],'reason':'missing_visible_physical_font'});continue
  if '<' in row['label'] and '>' in row['label']:issues.append({'cell':row['cell'],'reason':'inline_rich_text_requires_original_span_validation'});continue
  for font in actual+[primary_faces[row['cell']]]:
   key=(font['postScriptName'],int(row['style'].get('fontStyle',0)))
   if key in mapping:continue
   cid='face'+str(len(mapping));mapping[key]=cid;E.SubElement(cr,'mxCell',id=cid,vertex='1',value='probe',style='fontStyle='+str(key[1])+';');fakeobs.append({'cell':cid,'label':'probe','style':row['style'],'actual_fonts':[font]})
 _,fonts,freport=embed_single(E.tostring(fake,encoding='unicode'),fakeobs,directory);issues.extend(freport['issues']);converted={c['cell']:c for c in freport['changes']};changes=[]
 for row in observations:
  actual=[f for f in row['actual_fonts'] if f['glyphCount']];flags=int(row['style'].get('fontStyle',0));cell=cells[row['cell']];style=dict(x.split('=',1) for x in cell.get('style','').split(';') if '=' in x)
  if not actual or any(mapping.get((f['postScriptName'],flags)) not in converted for f in actual):continue
  if '<' in row['label'] and '>' in row['label']:continue
  if len(actual)==1 and actual[0]['postScriptName']==primary_faces[row['cell']]['postScriptName']:
   change=converted[mapping[(actual[0]['postScriptName'],flags)]];style['fontFamily']=change['family'];style['fontStyle']=str(change['after_flags']);changes.append({**change,'cell':row['cell'],'actual_fonts':actual,'mixed_runs':None})
  else:
   if str(row['style'].get('html','0'))!='1':issues.append({'cell':row['cell'],'reason':'mixed_svg_text_requires_html_layout_validation'});continue
   source_fonts={f['postScriptName']:f for f in actual};segments=[];bad=False
   probes=runs.get(row['cell'],[]) if len(actual)>1 else [{'text':html.unescape(row['label']),'fonts':actual}]
   for p in probes:
    if len(p['fonts'])!=1 or p['fonts'][0]['postScriptName'] not in source_fonts:issues.append({'cell':row['cell'],'reason':'grapheme_font_differs_from_actual_context','probe':p});bad=True;break
    ps=p['fonts'][0]['postScriptName']
    if segments and segments[-1]['postscript']==ps:segments[-1]['text']+=p['text']
    else:segments.append({'text':p['text'],'postscript':ps})
   if bad:continue
   if ''.join(s['text'] for s in segments)!=html.unescape(row['label']):issues.append({'cell':row['cell'],'reason':'grapheme_text_roundtrip_mismatch'});continue
   spans=[]
   for s in segments:
    face=converted[mapping[(s['postscript'],flags)]];s.update(family=face['family'],flags=face['after_flags']);css='font-family:'+face['family']+';font-weight:'+('700' if s['flags']&1 else '400')+';font-style:'+('italic' if s['flags']&2 else 'normal')+';';spans.append('<span style="'+css+'">'+html.escape(s['text'],quote=False)+'</span>')
   # Preserve the primary face's line-box metrics even when the first glyph is CJK.
   primary=primary_faces[row['cell']]
   baseface=converted[mapping[(primary['postScriptName'],flags)]]
   cell.set('value',''.join(spans));style['fontFamily']=baseface['family'];style['fontStyle']=str(baseface['after_flags']);changes.append({'cell':row['cell'],'before_family':row['style'].get('fontFamily'),'before_flags':flags,'after_flags':baseface['after_flags'],'actual_fonts':actual,'mixed_runs':segments})
  cell.set('style',';'.join(k+'='+v for k,v in style.items())+';')
 return attach_fonts(E.tostring(root,encoding='unicode'),fonts),fonts,{'changes':changes,'issues':issues,'text_cells_observed':len(observations),'font_files':len(fonts),'mixed_text_cells':sum(bool(c['mixed_runs']) for c in changes),'grapheme_probes':runs,'primary_font_probes':primary_faces,'quality_state':'requires_exact_native_pixels_actual_font_counts_and_plain_text_roundtrip'}
