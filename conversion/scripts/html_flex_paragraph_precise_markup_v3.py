"""Serialize independently observed source numeric CSS without CSSOM rounding."""
import math,re
from html.parser import HTMLParser

def preserve_source_numeric_markup(group):
 markup=group['markup'];evidence=group['cssEvidence'];offsets=[0]
 for line in markup.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
 changes=[]
 class Parser(HTMLParser):
  def __init__(self):super().__init__(convert_charrefs=False);self.index=0
  def handle_starttag(self,tag,attrs):
   i=self.index;self.index+=1;assert i<len(evidence)and tag==evidence[i]['tag'].lower(),'precise_source_semantic_element_scope_changed'
   text=self.get_starttag_text();line,column=self.getpos();start=offsets[line-1]+column;assert markup[start:start+len(text)]==text
   match=re.search(r'\bstyle\s*=\s*([\"\'])(.*?)\1',text,re.S);assert match,'precise_source_original_element_style_missing';style=match[2];numeric={k:v['literal']for k,v in evidence[i].get('typedNumericCSS',{}).items()}
   if i>0:numeric.update({k:v['literal']for k,v in evidence[i].get('layoutSizingCSS',{}).items()})
   if i==0:numeric.update({k:format(group['rootRect'][k],'.17g')+'px'for k in('width','height')})
   for key,value in numeric.items():
    assert re.fullmatch(r'(?:auto|none|min-content|max-content|fit-content|stretch|[-+0-9.eE]+(?:px|em|rem|%|pt|cm|mm|in|pc|ex|ch|lh|rlh)?)',value),'precise_source_numeric_literal_invalid'
    if i==0 and key in('width','height'):assert math.isfinite(group['rootRect'][key])and group['rootRect'][key]>0
    # Upstream draw.io touches some SUP/SUB style declarations. CSSOM then
    # serializes ordinary numeric values with six significant digits. Custom
    # properties retain their original token strings, and var() keeps the
    # source value intact through that unavoidable upstream serialization.
    variable='--img2code-source-exact-'+key
    pattern=r'(^|;)\s*'+re.escape(key)+r'\s*:[^;]*';style,count=re.subn(pattern,lambda m:m[1]+key+': var('+variable+')',style);assert count<=1,'precise_source_numeric_declaration_scope_changed:'+key
    if count==0:
     assert key in evidence[i].get('layoutSizingCSS',{}),'precise_source_numeric_declaration_missing:'+key
     style=style.rstrip();style+=(''if style.endswith(';')else';')+' '+key+': var('+variable+');'
    style=style.rstrip();style+=(''if style.endswith(';')else';')+' '+variable+': '+value+';'
   updated=text[:match.start(2)]+style+text[match.end(2):];changes.append((start,start+len(text),updated))
  handle_startendtag=handle_starttag
 parser=Parser();parser.feed(markup);parser.close();assert parser.index==len(evidence),'precise_source_element_inventory_changed'
 pieces=[];cursor=0
 for start,end,text in changes:pieces.extend((markup[cursor:start],text));cursor=end
 pieces.append(markup[cursor:]);return ''.join(pieces)
