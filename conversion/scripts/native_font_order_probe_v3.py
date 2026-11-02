"""Original CSS physical fallback constraints, independent of target PNG scores.

A single candidate order is derived from observed original graphemes and the
unchanged physical fonts' cmaps. Context-sensitive or cyclic mappings stay
unsupported; exact fresh native pixels and glyph signatures are still gates.
"""
import hashlib,json


class Probe:
 def __init__(self,browser):
  self.page=browser.new_page();self.page.route('**/*',lambda request:request.abort())
  self.page.set_content('<html><body><span id="probe"></span></body></html>')
  self.cdp=self.page.context.new_cdp_session(self.page);self.cdp.send('DOM.enable');self.cdp.send('CSS.enable')
  self.cdp.send('DOM.getDocument',{'depth':-1});self.cache={}
 def close(self):self.cdp.detach();self.page.close()
 def fonts(self,family,flags,size,text):
  key=(family,int(flags),float(size),text)
  if key not in self.cache:
   self.page.evaluate('''async a=>{const e=document.querySelector('#probe');e.textContent=a.text;e.style.cssText='font-family:'+a.family+';font-size:'+a.size+'px;font-weight:'+(a.flags&1?'bold':'normal')+';font-style:'+(a.flags&2?'italic':'normal')+';white-space:pre;';await document.fonts.ready;e.getBoundingClientRect();}''',dict(family=family,flags=flags,size=size,text=text))
   root=self.cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId'];node=self.cdp.send('DOM.querySelector',{'nodeId':root,'selector':'#probe'})['nodeId']
   self.cache[key]=self.cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
  return self.cache[key]
 def graphemes(self,text):return self.page.evaluate('''s=>[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(s)].map(g=>g.segment)''',text)


def derive_order(probe,row,candidates,preferred,cmaps):
 """Return PS order + immutable source-probe evidence, or refuse ambiguities."""
 from html_actual_text_alignment import _plain
 family=str(row['style'].get('fontFamily','Arial'));flags=int(row['style'].get('fontStyle',0));size=float(row['style'].get('fontSize',12))
 actual={f['postScriptName'] for f in row['actual_fonts'] if f.get('glyphCount',0)}
 glyphs=sorted(set(probe.graphemes(_plain(row['label']))));constraints=set();observations=[]
 for text in glyphs:
  if text.isspace():continue
  chars=set(map(ord,text));eligible={ps for ps in actual if chars<=cmaps[ps]}
  if len(eligible)==1:
   # The original cell's independently observed physical face inventory and
   # unchanged cmap prove this choice without losing text-shaping context.
   wanted=next(iter(eligible));fonts=[];basis='unique_original_observed_cmap_face'
  else:
   fonts=[f for f in probe.fonts(family,flags,size,text) if f.get('glyphCount',0)]
   names={f['postScriptName'] for f in fonts}
   if len(names)!=1 or not names<=actual:raise ValueError('font_order_context_sensitive_or_ambiguous_grapheme')
   wanted=next(iter(names));basis='isolated_original_CSS_physical_font_probe'
  if not chars<=cmaps[wanted]:raise ValueError('font_order_non_cmap_grapheme_unsupported')
  observations.append(dict(text=text,fonts=fonts,wanted_postscript=wanted,basis=basis))
  for other in candidates:
   if other!=wanted and chars<=cmaps[other]:constraints.add((wanted,other))
 incoming={name:set() for name in candidates}
 for before,after in constraints:incoming[after].add(before)
 result=[];rank={name:i for i,name in enumerate(preferred)}
 while incoming:
  ready=sorted((name for name,parents in incoming.items() if not parents),key=lambda n:(rank.get(n,len(rank)),n))
  if not ready:raise ValueError('font_order_source_fallback_precedence_cycle')
  chosen=ready[0];result.append(chosen);del incoming[chosen]
  for parents in incoming.values():parents.discard(chosen)
 proof=dict(schema='original_CSS_grapheme_physical_fallback_precedence_v3',family=family,flags=flags,size=size,observations=observations,constraints=[list(pair) for pair in sorted(constraints)],ordered_postscript=result,no_target_image_score_used=True)
 proof['sha256']=hashlib.sha256(json.dumps(proof,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return result,proof
