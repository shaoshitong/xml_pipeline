"""Preserve native shaping across fallback fonts when physical style flags agree."""
import copy,xml.etree.ElementTree as E

def stacked_variant(before,after,details):
 root=E.fromstring(after);cells={c.get('id'):c for c in root.iter('mxCell')};original={c.get('id'):c for c in E.fromstring(before).iter('mxCell')};d=copy.deepcopy(details);converted=[]
 for change in d['changes']:
  runs=change.get('mixed_runs')
  if not runs or any(r['flags']!=change['after_flags'] for r in runs):continue
  c=cells[change['cell']];style=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);families=list(dict.fromkeys([style['fontFamily']]+[r['family'] for r in runs]));style['fontFamily']=','.join(families);c.set('style',';'.join(k+'='+v for k,v in style.items())+';');c.set('value',original[change['cell']].get('value',''));change['font_stack']=families;change['mixed_runs']=None;converted.append(change['cell'])
 d['stacked_text_cells']=converted
 return E.tostring(root,encoding='unicode'),d
