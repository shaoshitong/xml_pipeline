import collections,html,xml.etree.ElementTree as E
from html.parser import HTMLParser
from native_font_embedding_batch import canonical
class Plain(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.text=[];self.starts=[];self.ends=[]
 def handle_data(self,s):self.text.append(s)
 def handle_starttag(self,tag,attrs):self.starts.append((tag,attrs))
 def handle_endtag(self,tag):self.ends.append(tag)
def verify_graph(before,after,details):
 a=E.fromstring(before);b=E.fromstring(after);original={c.get('id'):c for c in a.iter('mxCell')};proposed={c.get('id'):c for c in b.iter('mxCell')};changed={c['cell'] for c in details['changes']}
 for ch in details['changes']:
  cid=ch['cell'];assert cid in original and cid in proposed,'Wrapped cell labels need separate verification'
  assert ch['before_flags']&~3==ch['after_flags']&~3,'Non-bold/italic text formatting changed'
  if not ch['mixed_runs']:continue
  p=Plain();p.feed(proposed[cid].get('value',''));assert ''.join(p.text)==html.unescape(original[cid].get('value','')),'Editable text characters changed'
  assert len(p.starts)==len(ch['mixed_runs']) and p.ends==['span']*len(p.starts),'Unexpected rich-text markup'
  for (tag,attrs),run in zip(p.starts,ch['mixed_runs']):
   assert tag=='span' and len(attrs)==1 and attrs[0][0]=='style','Unexpected span attributes'
   css=dict(x.split(':',1) for x in attrs[0][1].split(';') if x)
   assert set(css)<= {'font-family','font-weight','font-style','line-height'}
   assert css['font-family']==run['family'] and css['font-weight']==('700' if run['flags']&1 else '400') and css['font-style']==('italic' if run['flags']&2 else 'normal'),'Physical span face/style changed'
   assert css.get('line-height','0')=='0','Unsupported line-height override'
  proposed[cid].set('value',original[cid].get('value',''))
 assert canonical(before,changed)==canonical(E.tostring(b,encoding='unicode'),changed),'Non-font graph structure or geometry changed'
 return True

def zero_lineboxes(xml,details):
 root=E.fromstring(xml);mixed={ch['cell'] for ch in details['changes'] if ch['mixed_runs']}
 for c in root.iter('mxCell'):
  if c.get('id') in mixed:c.set('value',c.get('value').replace('<span style="','<span style="line-height:0;'))
 return E.tostring(root,encoding='unicode')

def verify_fonts(observed,render,details):
 actual={r['cell']:r['fonts'] for r in render['actual_platform_font_usage']};before={r['cell']:r['actual_fonts'] for r in observed};diff={}
 def counts(fs):
  out=collections.Counter()
  for f in fs:out[f['postScriptName']]+=f['glyphCount']
  return dict(out)
 for ch in details['changes']:
  cid=ch['cell'];fs=[f for f in actual.get(cid,[]) if f['glyphCount']]
  assert fs and all(f['isCustomFont'] for f in fs),'Font fell back to a system font: '+cid
  if counts(before[cid])!=counts(fs):diff[cid]={'before':counts(before[cid]),'after':counts(fs)}
 assert not diff,'Physical font glyph counts changed: '+str(diff)
 return True
