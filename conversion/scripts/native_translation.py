"""Translate complete native drawings, preserving terminals, hierarchy and label offsets."""
import copy,math,xml.etree.ElementTree as E
from svg_convert_v2 import num

def translate(xml,dx,dy):
 if not all(math.isfinite(x) and abs(x)<=8 for x in (dx,dy)):raise ValueError('Native layout translation outside bounded repair range')
 root=E.fromstring(xml);model=root.find('.//mxGraphModel');w,h=float(model.get('pageWidth')),float(model.get('pageHeight'));changed=[];background=[]
 for c in root.iter('mxCell'):
  g=c.find('mxGeometry')
  if g is None:continue
  if c.get('vertex')=='1' and c.get('parent')=='1':
   x,y,cw,ch=[float(g.get(k,0)) for k in ['x','y','width','height']]
   if abs(x)<.01 and abs(y)<.01 and abs(cw-w)<.01 and abs(ch-h)<.01 and not c.get('value') and 'group=1' not in c.get('style',''):
    background.append(c.get('id'));continue
   g.set('x',num(x+dx));g.set('y',num(y+dy));changed.append(c.get('id'))
  elif c.get('edge')=='1':
   # Global coordinates belong only to top-level edges. Relative child labels stay unchanged.
   if c.get('parent')!='1':raise ValueError('Nested edge route needs coordinate-aware translation')
   for p in g.findall('Array/mxPoint')+g.findall('mxPoint'):
    if p.get('as')=='offset':continue
    p.set('x',num(float(p.get('x',0))+dx));p.set('y',num(float(p.get('y',0))+dy))
   changed.append(c.get('id'))
 # Prove every non-geometry attribute, text value, parent and terminal is identical.
 before=E.fromstring(xml);bc=list(before.iter('mxCell'));ac=list(root.iter('mxCell'));assert len(bc)==len(ac)
 for a,b in zip(bc,ac):assert a.attrib==b.attrib
 return E.tostring(root,encoding='unicode'),{'dx':dx,'dy':dy,'changed_geometry_cells':changed,'fixed_background_cells':background,'objects_and_styles_and_terminals_unchanged':True}
