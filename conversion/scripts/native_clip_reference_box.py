"""Use the browser's actual CSS clip reference box, not the union of font glyph ranges."""
import copy,xml.etree.ElementTree as E

def correct_reference_boxes(xml,details,rows):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};lookup={x['cell']:x['clips'] for x in rows};out=copy.deepcopy(details);changed=[]
 for ch in out['changes']:
  clips=lookup[ch['cell']];assert len(clips)==1,'Ambiguous nested native clip spans';box=clips[0];assert len(box['fragments'])==1,'Multifragment native clip span';assert box['text']==ch['source_text'],'Native clip box text differs';left,top,right,bottom=ch['clip_bounds'];x,y=box['x'],box['y'];x1,y1=x+box['width'],y+box['height'];insets=[top-y,x1-right,y1-bottom,left-x];ch['native_clip_reference_bbox']=[x,y,x1,y1];ch['range_derived_insets']=ch['insets'];ch['insets']=insets
  value='<span style="clip-path:inset('+' '.join(format(v,'.8g')+'px' for v in insets)+');">'+ch['before_value']+'</span>'
  if cells[ch['cell']].get('value')!=value:changed.append(ch['cell']);cells[ch['cell']].set('value',value)
 out['reference_box_adjusted_cells']=changed;out['reference_box_method']='actual_official_native_css_span_border_box';return E.tostring(root,encoding='unicode'),out
