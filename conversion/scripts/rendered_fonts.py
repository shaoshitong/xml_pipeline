"""Read the actual fonts Chromium used, instead of guessing CSS fallback families."""
def resolve_fonts(page,dom):
 families=list(dict.fromkeys(o['fontFamilyRaw'] for o in dom['objects'] if o['type']=='text'))
 probes=[{'family':f,'text':' '.join(o['text'] for o in dom['objects'] if o['type']=='text' and o['fontFamilyRaw']==f)[:800]} for f in families]
 page.evaluate('items=>{for(let i=0;i<items.length;i++){const s=document.createElement("span");s.id="img2code-font-probe-"+i;s.style.cssText="position:absolute;left:-100000px;top:0;white-space:nowrap;font-size:16px;";s.style.fontFamily=items[i].family;s.textContent=items[i].text;document.body.appendChild(s);}}',probes)
 cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId'];mapping={}
 for i,f in enumerate(families):
  node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':'#img2code-font-probe-'+str(i)})['nodeId'];fonts=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'];assert fonts,'No actual platform font for '+f;primary=max(fonts,key=lambda x:x['glyphCount']);mapping[f]={'selected':primary['familyName'],'fonts':fonts}
  if any(x['isCustomFont'] for x in fonts):dom['unsupported'].append({'reason':'custom_font_requires_embedded_resource_support','font_stack':f})
 for o in dom['objects']:
  if o['type']=='text':o['fontFamily']=mapping[o['fontFamilyRaw']]['selected']
 page.evaluate('()=>document.querySelectorAll("[id^=img2code-font-probe-]").forEach(x=>x.remove())');cdp.detach();return mapping
