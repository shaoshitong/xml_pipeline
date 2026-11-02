"""Source-only SVG spacing lowering and independent actual grapheme proof.

Only a uniform inter-grapheme spacing and one bounded whole-run origin are
representable. No reference image is used to choose any text parameter.
"""
from __future__ import annotations
import html,math,re,statistics,xml.etree.ElementTree as E
POLICY='plantuml_source_textLength_uniform_spacing_actual_graphemes_v1'
TOL=.03
MAX_ORIGIN=2.
def require(ok,reason):
 if not ok:raise ValueError(reason)

OBSERVER=r"""()=>{function read(e){const rows=[],walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(n);const b=range.getBoundingClientRect(),chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){range.setStart(n,i);range.setEnd(n,i+segment.length);const c=range.getBoundingClientRect();chars.push({text:segment,x:c.x,y:c.y,width:c.width,height:c.height});}rows.push({text:n.textContent,whole:{x:b.x,y:b.y,width:b.width,height:b.height},chars});}return rows;}return [...document.querySelectorAll('svg text')].flatMap((e,index)=>{const c=getComputedStyle(e),m=e.getScreenCTM(),length=e.getAttribute('textLength'),adjust=e.getAttribute('lengthAdjust'),rows=read(e),out={source_element_index:index,text:e.textContent,element_children:e.children.length,attrs:{textLength:length,lengthAdjust:adjust,rotate:e.getAttribute('rotate')},matrix:[m.a,m.b,m.c,m.d,m.e,m.f],css:{fontFamily:c.fontFamily,fontSize:parseFloat(c.fontSize),fontWeight:c.fontWeight,fontStyle:c.fontStyle,fontKerning:c.fontKerning,fontFeatureSettings:c.fontFeatureSettings,fontVariantLigatures:c.fontVariantLigatures,letterSpacing:c.letterSpacing,wordSpacing:c.wordSpacing,direction:c.direction,writingMode:c.writingMode,textAnchor:c.textAnchor},adjusted:rows};try{e.removeAttribute('textLength');out.natural=read(e);}finally{if(length!==null)e.setAttribute('textLength',length);else e.removeAttribute('textLength');}return rows.length?[out]:[];});}"""


def px(value):
 if value=='normal':return 0.
 require(isinstance(value,str) and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)px',value) is not None,'source_or_native_spacing_not_pixels');return float(value[:-2])

def plan(row):
 require(row['element_children']==0 and len(row['adjusted'])==len(row['natural'])==1,'source_text_nested_runs_unsupported');require(row['attrs'].get('rotate') in (None,''),'source_text_rotation_list_unsupported');m=row['matrix'];require(all(abs(v-w)<=1e-7 for v,w in zip(m[:4],[1,0,0,1])),'source_text_scaled_or_rotated_unsupported');c=row['css'];require(c['direction']=='ltr' and c['writingMode']=='horizontal-tb' and c['textAnchor']=='start','source_text_direction_or_anchor_unsupported');require(c['fontKerning']=='auto' and c['fontFeatureSettings']=='normal' and c['fontVariantLigatures']=='normal' and abs(px(c['wordSpacing']))<=1e-9,'source_text_shaping_css_unsupported')
 a=row['adjusted'][0];n=row['natural'][0];chars=a['chars'];require(chars and [x['text'] for x in chars]==[x['text'] for x in n['chars']] and ''.join(x['text'] for x in chars)==row['text'],'source_graphemes_changed');require(row['text']==row['text'].strip() and '\n' not in row['text'] and '\r' not in row['text'] and '\t' not in row['text'],'source_whitespace_layout_unsupported');base=px(c['letterSpacing']);length=row['attrs']['textLength'];delta=0.
 if length is not None:
  require(row['attrs']['lengthAdjust'] in (None,'spacing'),'source_lengthAdjust_requires_glyph_scaling_unsupported');require(re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)',length) is not None,'source_textLength_non_numeric_unsupported');target=float(length);require(target>0,'source_textLength_not_positive')
  if len(chars)==1:require(abs(target-n['whole']['width'])<=TOL,'single_grapheme_length_adjust_unsupported')
  else:delta=(target-n['whole']['width'])/(len(chars)-1)
 require(math.isfinite(delta) and abs(delta)<=float(c['fontSize'])/2,'source_uniform_spacing_out_of_supported_range')
 # Source DOM ranges quantize contextual glyph advances to 1/64px. Prove
 # one uniform gap exists within the unchanged .03px source range bound,
 # then choose the closest value to the source textLength declaration.
 ideal_delta=delta
 chunks=[];start=0
 for i in range(1,len(chars)):
  if chars[i-1]['text'].isspace() and not chars[i]['text'].isspace():chunks.append((start,i));start=i
 chunks.append((start,len(chars)))
 def interval(parts):
  lower=-float('inf');upper=float('inf')
  for first,last in parts:
   for i in range(first+1,last):
    difference=(chars[i]['x']-chars[first]['x'])-(n['chars'][i]['x']-n['chars'][first]['x']);lower=max(lower,(difference-TOL)/(i-first));upper=min(upper,(difference+TOL)/(i-first))
  return lower,upper
 lower,upper=interval([(0,len(chars))]);mode='uniform'
 if lower>upper:
  require(len(chunks)>1,'source_grapheme_spacing_has_no_uniform_solution');lower,upper=interval(chunks);mode='source_words'
 require(lower<=upper,'source_word_internal_spacing_has_no_shared_uniform_solution')
 if len(chars)>1:
  inside=min(1e-9,max(0.,upper-lower)/4);delta=0. if lower<=0<=upper and abs(ideal_delta)*(len(chars)-1)<=2*TOL else min(max(ideal_delta,lower+inside),upper-inside);require(abs(delta-ideal_delta)*(len(chars)-1)<=2*TOL+1e-9,'source_spacing_correction_not_range_quantization')
 for i,(want,natural) in enumerate(zip(chars,n['chars'])):
  first=0 if mode=='uniform' else next(a for a,b in chunks if a<=i<b)
  difference=(want['x']-chars[first]['x'])-(natural['x']-n['chars'][first]['x'])
  require(abs(difference-(i-first)*delta)<=TOL and abs(want['y']-natural['y'])<=TOL,'source_length_adjust_not_uniform_within_source_word');require(abs(want['width']-natural['width'])<=TOL and abs(want['height']-natural['height'])<=TOL,'source_length_adjust_changed_grapheme_size')
 return {'layout_mode':mode,'source_words':[{'start':a,'end':b,'text':''.join(x['text'] for x in chars[a:b]),'x':chars[a]['x']-chars[0]['x'],'y':chars[a]['y']-chars[0]['y']} for a,b in chunks],'source_whole_box':row['adjusted'][0]['whole'],'text':row['text'],'graphemes':[x['text'] for x in chars],'chars':chars,'base_spacing':base,'spacing':base+delta,'spacing_delta':delta,'declared_spacing_delta_before_range_quantization':ideal_delta,'uniform_source_spacing_feasible_interval':[lower,upper] if len(chars)>1 else None,'fontSize':c['fontSize'],'actual_fonts':row['actual_fonts'],'source_declared_textLength':length,'source_natural_width':n['whole']['width'],'policy':POLICY}

def plans(dom):return {o['id']:plan(o['source_textlength_layout']) for o in dom['objects'] if o['type']=='text'}
def label(identifier,p,dx=0.,dy=0.):
 require(all(math.isfinite(v) and abs(v)<=MAX_ORIGIN for v in (dx,dy)),'source_native_origin_delta_exceeds_supported_rounding');last=p['graphemes'][-1];prefix=p['text'][:-len(last)]
 if p.get('layout_mode')=='source_words':
  words=[]
  for word in p['source_words']:
   text=word['text'];inside=html.escape(text)
   words.append('<span style="position:absolute;left:'+format(word['x'],'.9f')+'px;top:'+format(word['y'],'.9f')+'px;white-space:pre;letter-spacing:'+format(p['spacing'],'.9f')+'px;">'+inside+'</span>')
  box=p['source_whole_box'];return '<span data-engine-source-words-v1="'+html.escape(identifier,quote=True)+'" style="display:inline-block;position:relative;vertical-align:top;width:'+format(box['width'],'.9f')+'px;height:'+format(box['height'],'.9f')+'px;left:'+format(dx,'.9f')+'px;top:'+format(dy,'.9f')+'px;">'+''.join(words)+'</span>'
 # One text node preserves kerning across the final pair. CSS adds a
 # trailing advance to its Range width, which the intrinsic-size observer
 # subtracts explicitly; source-fixed geometry keeps that nonpainted advance
 # from changing the source editor frame or the complete-label visual unit.
 return '<span data-plantuml-textlength-v1="'+html.escape(identifier,quote=True)+'" style="position:relative;left:'+format(dx,'.9f')+'px;top:'+format(dy,'.9f')+'px;letter-spacing:'+format(p['spacing'],'.9f')+'px;">'+html.escape(p['text'])+'</span>'

def apply(xml,source_plans,corrections=None):
 from auto_quality_source_vector_v2 import _plain
 tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')};corrections=corrections or {}
 for identifier,p in source_plans.items():
  require(identifier in cells and _plain(cells[identifier].get('value',''))==p['text'],'source_text_not_preserved_before_lowering');c=corrections.get(identifier,{});cells[identifier].set('value',label(identifier,p,c.get('dx',0.),c.get('dy',0.)))
 return E.tostring(tree,encoding='unicode')

def _signature(fonts):return sorted((r['postScriptName'],r['glyphCount']) for r in fonts if r.get('glyphCount'))

def _rows(info):
 out={}
 for row in info.get('actual_text_positions',[]):
  require(row['cell'] not in out,'duplicate_actual_native_text');chars=[]
  for run in row['runs']:
   spacing=px(run['letterSpacing']);require(run.get('fontKerning')=='auto' and run.get('fontFeatureSettings')=='normal','actual_native_text_shaping_css_changed')
   for char in run['chars']:chars.append({**char,'actual_css_letter_spacing':spacing,'intrinsic_range_width':char['width']-spacing})
  out[row['cell']]=chars
 return out

def audit(source_plans,info,mapping=None,allow_origin=False):
 observed=_rows(info);fonts={r['cell']:r['fonts'] for r in info.get('actual_platform_font_usage',[])};mapping=mapping or {i:i for i in source_plans};require(set(mapping)==set(source_plans),'source_text_mapping_incomplete');require(set(mapping.values())==set(observed),'source_native_text_inventory_changed');details=[];corrections={}
 for identifier,p in source_plans.items():
  cid=mapping[identifier];actual=observed[cid];wanted=p['chars'];require([a['text'] for a in actual]==p['graphemes'],'actual_source_native_graphemes_changed');require(_signature(p['actual_fonts'])==_signature(fonts.get(cid,[])),'actual_source_native_physical_font_or_glyph_count_changed');require(all(r.get('isCustomFont') for r in fonts[cid] if r.get('glyphCount')),'actual_native_text_font_not_embedded')
  dx=statistics.median(a['x']-b['x'] for a,b in zip(wanted,actual)) if allow_origin else 0.;dy=statistics.median(a['y']-b['y'] for a,b in zip(wanted,actual)) if allow_origin else 0.;require(all(math.isfinite(v) and abs(v)<=MAX_ORIGIN for v in (dx,dy)),'source_native_origin_delta_exceeds_supported_rounding');max_position=max_size=0.
  for i,(want,got) in enumerate(zip(wanted,actual)):
   spacing=p['spacing'];require(abs(got['actual_css_letter_spacing']-spacing)<=1e-6,'actual_source_declared_uniform_spacing_changed');max_position=max(max_position,abs(got['x']+dx-want['x']),abs(got['y']+dy-want['y']));max_size=max(max_size,abs(got['intrinsic_range_width']-want['width']),abs(got['height']-want['height']))
  require(max_position<=TOL,'actual_source_native_grapheme_position_changed:'+identifier+':'+str(max_position)+':'+str([(a['text'],round(a['x']-b['x']+dx,5),round(a['y']-b['y']+dy,5)) for a,b in zip(actual,wanted)]));require(max_size<=TOL,'actual_source_native_grapheme_size_changed');corrections[identifier]={'dx':dx,'dy':dy};details.append({'source_object':identifier,'native_cell':cid,'graphemes':len(wanted),'source_declared_textLength':p['source_declared_textLength'],'source_natural_width':p['source_natural_width'],'source_spacing_delta':p['spacing_delta'],'source_positioning_mode':p.get('layout_mode','uniform'),'actual_grapheme_position_max_error_px':max_position,'actual_intrinsic_range_size_max_error_px':max_size,'source_uniform_spacing_and_physical_font_verified':True})
 return {'ok':True,'policy':POLICY,'details':details,'whole_run_origin':corrections,'position_tolerance_px':TOL,'intrinsic_range_size_tolerance_px':TOL,'max_whole_run_origin_px':MAX_ORIGIN,'reference_pixels_used_for_alignment':False,'per_character_offsets_or_scaling':False}

def verify_labels(xml,source_plans,mapping):
 tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')}
 for identifier,p in source_plans.items():
  cid=mapping[identifier];value=cells[cid].get('value','')
  if '<' not in value and '>' not in value and html.unescape(value)==p['text']:continue
  if p.get('layout_mode')=='source_words':
   found=re.fullmatch(r'<span data-engine-source-words-v1="[^"<>]+" style="display:inline-block;position:relative;vertical-align:top;width:[+\-\d.eE]+px;height:[+\-\d.eE]+px;left:([+\-\d.eE]+)px;top:([+\-\d.eE]+)px;">.*</span>',value,re.S);require(found is not None,'source_word_IR_label_structure_changed');dx,dy=float(found[1]),float(found[2]);actual=re.sub(r'data-engine-source-words-v1="[^"<>]+"','data-engine-source-words-v1="'+identifier+'"',value,count=1);require(actual==label(identifier,p,dx,dy),'source_word_IR_positions_spacing_or_Unicode_changed');continue
  match=re.fullmatch(r'<span data-plantuml-textlength-v1="[^"<>]+" style="position:relative;left:([+\-\d.eE]+)px;top:([+\-\d.eE]+)px;letter-spacing:[+\-\d.eE]+px;">(.*)</span>',value,re.S);require(match is not None,'candidate_text_lowering_not_source_declared_span');dx,dy=float(match[1]),float(match[2]);require(all(math.isfinite(v) and abs(v)<=MAX_ORIGIN for v in (dx,dy)),'candidate_text_origin_outside_rounding_bound')
  # IDs may be renamed; declaration contents and all CSS must remain exact.
  expected=label(identifier,p,dx,dy);actual=re.sub(r'data-plantuml-textlength-v1="[^"<>]+"','data-plantuml-textlength-v1="'+identifier+'"',value,count=1);require(actual==expected,'candidate_text_spacing_or_unapproved_rich_style_changed')
 return True

import plantuml_textlength_layout_v1 as frozen
_MUTATION="try{e.removeAttribute('textLength');out.natural=read(e);}finally{if(length!==null)e.setAttribute('textLength',length);else e.removeAttribute('textLength');}"
assert frozen.OBSERVER.count(_MUTATION)==1
READ_ONLY=frozen.OBSERVER.replace(_MUTATION,'out.natural=[];')
def inspect(page,dom):
 before=page.screenshot();rows=page.evaluate(READ_ONLY);require(page.screenshot()==before,'read_only_source_grapheme_observer_changed_pixels');clone=page.context.new_page()
 try:
  clone.set_viewport_size(page.viewport_size);clone.set_content(page.content());clone.evaluate('document.fonts.ready');require(clone.screenshot()==before,'isolated_source_text_clone_pixels_changed');clone.evaluate("()=>{for(const e of document.querySelectorAll('svg text'))e.removeAttribute('textLength');}");natural=clone.evaluate(READ_ONLY);require(len(natural)==len(rows),'isolated_source_text_clone_inventory_changed')
  for source,plain in zip(rows,natural):
   require(source['text']==plain['text'] and source['source_element_index']==plain['source_element_index'] and source['css']==plain['css'],'isolated_natural_source_text_or_font_style_changed');source['natural']=plain['adjusted']
 finally:clone.close()
 objects=[o for o in dom['objects'] if o['type']=='text'];require(len(objects)==len(rows),'source_text_object_count_differs');session=page.context.new_cdp_session(page)
 try:
  session.send('DOM.enable');session.send('CSS.enable');root=session.send('DOM.getDocument',{'depth':1})['root']['nodeId'];nodes=session.send('DOM.querySelectorAll',{'nodeId':root,'selector':'svg text'})['nodeIds']
  for obj,row in zip(objects,rows):
   require(obj['text']==row['text'] and len(row['adjusted'])==len(row['natural'])==1,'source_text_run_order_or_mixed_content_unsupported');row['actual_fonts']=session.send('CSS.getPlatformFontsForNode',{'nodeId':nodes[row['source_element_index']]})['fonts'];obj['source_textlength_layout']=row;plan(row)
 finally:session.detach()
 require(page.screenshot()==before,'source_text_clone_or_font_observer_changed_original_pixels');return rows
