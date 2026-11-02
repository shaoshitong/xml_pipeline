"""Preserve native shaping and intrinsic font styles using observed fallback precedence."""
import copy,html,xml.etree.ElementTree as E
from fontTools.ttLib import TTFont

def native_stack_variant(before,after,details,fonts):
 root=E.fromstring(after);cells={c.get('id'):c for c in root.iter('mxCell')};original={c.get('id'):c for c in E.fromstring(before).iter('mxCell')};d=copy.deepcopy(details);cmaps={};converted=[]
 for family,f in fonts.items():
  with TTFont(f['file']) as ft:cmaps[family]=set((ft.getBestCmap() or {}).keys())
 for ch in d['changes']:
  cid=ch['cell'];c=cells[cid];style=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);primary=style['fontFamily'].split(',')[0];runs=ch.get('mixed_runs')
  if runs:
   families=list(dict.fromkeys([primary]+[r['family'] for r in runs]));constraints={f:set() for f in families}
   # A fallback must precede another face that could also supply its observed text.
   for run in runs:
    chosen=run['family']
    if chosen==primary:continue
    for char in run['text']:
     if char.isspace():continue
     cp=ord(char)
     for other in families:
      if other not in [chosen,primary] and cp in cmaps[other]:constraints[other].add(chosen)
   ordered=[primary];remaining=[f for f in families if f!=primary]
   while remaining:
    ready=next((f for f in remaining if not (constraints[f]&set(remaining))),None)
    if ready is None:break
    ordered.append(ready);remaining.remove(ready)
   if remaining:
    # Context-dependent fallback has no single total order; retain the span candidate.
    ch['native_stack_unresolved']='context_dependent_fallback_precedence_cycle';continue
   style['fontFamily']=','.join(ordered)
  else:ordered=style['fontFamily'].split(',')
  style['fontStyle']=str(ch['before_flags']);c.set('style',';'.join(k+'='+v for k,v in style.items())+';');c.set('value',original[cid].get('value',''));ch['after_flags']=ch['before_flags'];ch['mixed_runs']=None;ch['native_font_stack']=ordered;converted.append(cid)
 d['native_stack_cells']=converted;return E.tostring(root,encoding='unicode'),d
