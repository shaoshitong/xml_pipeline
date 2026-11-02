"""Actual source SVG grapheme/font observations for deterministic HTML rounding.

Only one <=2px whole-run translation is emitted after proving identical text,
shaping, widths, heights and embedded physical fonts. No reference pixels.
"""
import json
from compiler_scene_text_v2 import offsets,apply_offsets,_chars,_fonts,_font_signature

def source_positions(page,dom):
 rows=page.evaluate('''()=>{const out=[];for(const [index,e] of [...document.querySelectorAll('svg text')].entries()){e.dataset.tikzSourceTextV2=String(index);const n=e.firstChild;if(!n||n.nodeType!==Node.TEXT_NODE||e.childNodes.length!==1)throw Error('source PDF glyph run must be flat text');const chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+segment.length);const b=r.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}out.push({source_element_index:index,text:n.textContent,chars});}return out;}''')
 objects=[o for o in dom['objects'] if o['type']=='text']
 rows=[r for r in rows if r['text'].strip()]
 if len(rows)!=len(objects):raise ValueError('actual_PDF_source_text_run_coverage_differs')
 session=page.context.new_cdp_session(page)
 try:
  session.send('DOM.enable');session.send('CSS.enable');document=session.send('DOM.getDocument',{'depth':1})['root']['nodeId'];out={}
  for row,obj in zip(rows,objects):
   if row['text']!=obj['text']:raise ValueError('actual_PDF_source_text_order_or_content_differs')
   node=session.send('DOM.querySelector',{'nodeId':document,'selector':'[data-tikz-source-text-v2="'+str(row['source_element_index'])+'"]'})['nodeId']
   fonts=session.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
   if not fonts or not all(f.get('isCustomFont') for f in fonts if f.get('glyphCount')):raise ValueError('actual_PDF_source_glyph_font_not_embedded')
   out[obj['id']]={**row,'bbox':obj['bbox'],'fontSize':obj['fontSize'],'fontFamily':obj['fontFamily'],'actual_fonts':fonts}
  return out
 finally:session.detach()

def correct(xml,source,native_info):
 delta=offsets(source,native_info);return apply_offsets(xml,source,delta),delta

def validate(source,native_info):
 delta=offsets(source,native_info)
 # offsets() already proves per-grapheme width/height/shaping/font equality.
 # After applying the one source-derived correction there must be no residual.
 for identifier,item in delta.items():
  if max(abs(item['dx']),abs(item['dy']))>.03:raise ValueError('fresh_native_PDF_source_grapheme_anchor_mismatch:'+identifier)
 return {'ok':True,'objects':len(source),'graphemes':sum(len(x['chars']) for x in source.values()),'tolerance_px':.03,'actual_source_fonts_and_shaping_preserved':True,'reference_pixels_used':False}
