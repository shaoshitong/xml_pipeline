"""Upgrade only source-confirmed Graphviz vee markers; retain later text/font repairs."""
import copy,xml.etree.ElementTree as E
from svg_convert_v3 import build as build_before,unpack,pack
from source_vee_marker import build as build_after

class NoVeeDelta(ValueError):pass

def canon(e):return E.canonicalize(E.tostring(e,encoding='unicode'))
def patch(xml,dom,w,h):
 ax,ast=build_before(copy.deepcopy(dom),w,h);bx,bst=build_after(copy.deepcopy(dom),w,h);a={c.get('id'):c for c in E.fromstring(ax).iter('mxCell')};b={c.get('id'):c for c in E.fromstring(bx).iter('mxCell')};root=E.fromstring(xml);parent={c:p for p in root.iter() for c in p};current={c.get('id'):c for c in root.iter('mxCell')};assert not set(b)-set(a),'Unexpected added source cell';removed=set(a)-set(b);markers=[r for r in bst['native_graphviz_arrowheads'] if r['source_arrow_object'] in removed];assert removed=={m['source_arrow_object'] for m in markers},'Removed cells are not source-confirmed markers'
 if not removed:raise NoVeeDelta('No additional source-confirmed VEE marker in this revision')
 changes=[]
 for id in sorted(removed):
  assert id in current and canon(current[id])==canon(a[id]),'Standalone arrow changed since source conversion: '+id;parent[current[id]].remove(current[id])
 for id in sorted(set(a)&set(b)):
  if canon(a[id])==canon(b[id]):continue
  before,after,c=a[id],b[id],current[id];sa,sb,sc=[unpack(x.get('style','')) for x in [before,after,c]];keys={k for k in set(sa)|set(sb) if sa.get(k)!=sb.get(k)};change={'cell':id,'style_keys':sorted(keys),'style_changes':{k:[sa.get(k),sb.get(k)] for k in sorted(keys)}}
  assert {k:v for k,v in before.attrib.items() if k!='style'}=={k:v for k,v in after.attrib.items() if k!='style'},'Unexpected source attribute change'
  for key in ['edge','source','target','parent','value']:assert c.get(key)==before.get(key),'Native relationship/content diverged: '+id
  if keys:
   assert c.get('edge')=='1';assert keys<={'startArrow','endArrow','startSize','endSize','startFill','endFill','entryX','entryY','entryPerimeter','exitX','exitY','exitPerimeter'}
   for k in sorted(keys):
    assert sc.get(k)==sa.get(k),'Current edge style diverged: '+id+'/'+k
    if k in sb:sc[k]=sb[k]
    else:sc.pop(k,None)
   c.set('style',pack(sc))
  ga,gb,gc=[x.find('mxGeometry') for x in [before,after,c]]
  assert canon(gc)==canon(ga),'Native/source edge or label geometry diverged: '+id
  if canon(ga)!=canon(gb):
   assert c.get('vertex')=='1' and c.get('parent') in {m['native_edge'] for m in markers};change['before_geometry']=E.tostring(gc,encoding='unicode');change['after_geometry']=E.tostring(gb,encoding='unicode');c.remove(gc);c.append(copy.deepcopy(gb))
  changes.append(change)
 new=E.tostring(root,encoding='unicode');proof={'removed_arrows':sorted(removed),'markers':markers,'changes':changes,'source_stats_before':ast,'source_stats_after':bst};verify(xml,new,proof);return new,proof

def verify(before,after,proof):
 a=E.fromstring(before);b=E.fromstring(after);ac={c.get('id'):c for c in a.iter('mxCell')};bc={c.get('id'):c for c in b.iter('mxCell')};assert set(ac)-set(bc)==set(proof['removed_arrows']) and not set(bc)-set(ac)
 for ch in proof['changes']:
  ca,cb=ac[ch['cell']],bc[ch['cell']];sa,sb=unpack(ca.get('style','')),unpack(cb.get('style',''));assert all([sa.get(k),sb.get(k)]==v for k,v in ch['style_changes'].items());assert {k:v for k,v in sa.items() if k not in ch['style_keys']}=={k:v for k,v in sb.items() if k not in ch['style_keys']};cb.set('style',ca.get('style',''))
  if 'before_geometry' in ch:
   assert E.tostring(ca.find('mxGeometry'),encoding='unicode')==ch['before_geometry'];assert E.tostring(cb.find('mxGeometry'),encoding='unicode')==ch['after_geometry'];cb.remove(cb.find('mxGeometry'));cb.append(copy.deepcopy(ca.find('mxGeometry')))
 # Remove the same proven obsolete arrow vertices from the old tree, preserving all other order/content.
 pa={c:p for p in a.iter() for c in p}
 for id in proof['removed_arrows']:pa[ac[id]].remove(ac[id])
 assert canon(a)==canon(b),'Non-marker graph, font resources or text content changed';return True
