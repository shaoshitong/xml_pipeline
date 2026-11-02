"""Restore SOURCE ordered non-font style tokens after final font attachment.

Pure XML transformation, no IO or runtime. Candidate effective non-font key/
value settings must agree with source; remaining named tokens must be a source
subsequence. Restores the original named tokens, duplicates and default reset,
while retaining candidate font fields. Caller still must prove full model,
physical fonts, glyphs and actual source-before/after pixels unchanged.
"""
import re,xml.etree.ElementTree as ET
FONT_KEYS={'fontFamily','fontStyle','fontSource'}
POLICY='source_final_font_attachment_complete_named_tokens_and_reset_restore_v1'
def tokens(value):
 if '\x00'in value:raise ValueError('source_style_NUL_not_supported')
 value=re.sub(r'((?:image|fontSource)=data:[^,]*,)',lambda m:m[0].replace(';','\x00'),value)
 return[part.replace('\x00',';')for part in value.split(';')]if value else[]
def _font(token):return '='in token and token.split('=',1)[0]in FONT_KEYS
def restore_style(source,candidate):
 a,b=tokens(source),tokens(candidate)
 values=lambda items:{k:v for t in items if'='in t for k,v in[t.split('=',1)]if k not in FONT_KEYS}
 if values(a)!=values(b):raise ValueError('final_font_attachment_changed_nonfont_style_value')
 names=[t for t in a if t and'='not in t];remaining=iter(names)
 for token in[t for t in b if t and'='not in t]:
  if not any(value==token for value in remaining):raise ValueError('final_font_attachment_added_or_reordered_named_style')
 kept=[t for t in a if not _font(t)];fonts=[t for t in b if _font(t)]
 leading=0
 while leading<len(kept)and kept[leading]=='':leading+=1
 trailing=len(kept)
 while trailing>leading and kept[trailing-1]=='':trailing-=1
 out=kept[:trailing]+fonts+kept[trailing:];value=';'.join(out)
 if value.startswith(';')!=source.startswith(';'):raise ValueError('final_font_attachment_default_reset_changed')
 if[t for t in tokens(value)if not _font(t)]!=kept:raise ValueError('final_font_attachment_source_nonfont_sequence_changed')
 return value

def restore(source_xml,candidate_xml,ordinary_cell_ids):
 source=ET.fromstring(source_xml);current=ET.fromstring(candidate_xml)
 def cells(root):
  parents={c:p for p in root.iter()for c in p};found={}
  for cell in root.iter('mxCell'):
   ident=cell.get('id')or parents[cell].get('id')
   if not ident or ident in found:raise ValueError('final_font_attachment_ambiguous_cell_ID')
   found[ident]=cell
  return found
 before,after=cells(source),cells(current)
 for ident in set(ordinary_cell_ids):
  if ident not in before or ident not in after:raise ValueError('final_font_attachment_missing_source_cell')
  after[ident].set('style',restore_style(before[ident].get('style',''),after[ident].get('style','')))
 return ET.tostring(current,encoding='unicode')
restore_font_binding_styles=restore
