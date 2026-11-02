import sys,json,uuid
from pathlib import Path
sys.path.insert(0,'/backup/shaoshitong/img2code_20261029/conversion/scripts')
import compiler_plantuml_actual_source_v3 as s
from playwright.sync_api import sync_playwright
from plantuml_fonts import resolve
base=s.W/'plantuml_textlength_probe_v1'/uuid.uuid4().hex;base.mkdir(parents=True)
record=json.loads((s.R/'clean/compiler_plantuml_natural_candidate_v8/05/05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798/e576d9b4928c49fb9fe992cc0ad1870c/record.json').read_text())
svg=s.R/record['source_render_svg']
JS=r'''()=>{function read(e){const rows=[];const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(n);const whole=range.getBoundingClientRect();const chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){range.setStart(n,i);range.setEnd(n,i+segment.length);const b=range.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}rows.push({text:n.textContent,whole:{x:whole.x,y:whole.y,width:whole.width,height:whole.height},chars});}return rows;}return [...document.querySelectorAll('svg text')].map((e,index)=>{const cs=getComputedStyle(e),length=e.getAttribute('textLength'),adjust=e.getAttribute('lengthAdjust'),a={index,text:e.textContent,attrs:{textLength:length,lengthAdjust:adjust,x:e.getAttribute('x'),y:e.getAttribute('y')},css:{font:cs.font,fontKerning:cs.fontKerning,letterSpacing:cs.letterSpacing,wordSpacing:cs.wordSpacing,fontFeatureSettings:cs.fontFeatureSettings},adjusted:read(e)};e.removeAttribute('textLength');a.natural=read(e);a.naturalComputedLength=e.getComputedTextLength();if(length!==null)e.setAttribute('textLength',length);a.adjustedComputedLength=e.getComputedTextLength();return a;});}'''
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=s.base.CHROME,args=['--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':600,'height':600});page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.read_text());page.evaluate(s.NATURAL);fonts=resolve(page,base);page.evaluate('document.fonts.ready');before=page.screenshot();rows=page.evaluate(JS);assert page.screenshot()==before
 (base/'report.json').write_text(json.dumps({'source':str(svg),'rows':rows,'fonts':fonts,'source_restored_pixels_identical':True},indent=2));b.close()
print(json.dumps({'report':str(base/'report.json'),'rows':[{'text':r['text'],'css':r['css'],'length':r['attrs'],'adjusted':r['adjusted'][0]['whole'],'natural':r['natural'][0]['whole'],'achars':r['adjusted'][0]['chars'][:3],'nchars':r['natural'][0]['chars'][:3]} for r in rows]}))
