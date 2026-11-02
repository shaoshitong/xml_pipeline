"""Affine fitting with independently verified multipart node fills."""
import collections
import numpy as np
from scipy.optimize import linear_sum_assignment
from mermaid_reference_fit_v3 import components

def fit(source,reference,nodes):
 assert source.shape==reference.shape and source.ndim==3
 h,w=source.shape[:2];assert 3<=len(nodes)<=80,'At least three independently visible source nodes required'
 groups=collections.defaultdict(list)
 for n in nodes:
  c=tuple(n['color']);assert len(c)==3 and c not in [(255,255,255),(0,0,0)],'Ambiguous background/ink fill'
  groups[c].append(n)
 pairs=[]
 for color,group in groups.items():
  min_area=max(32,min((n['x1']-n['x0'])*(n['y1']-n['y0']) for n in group)*.05)
  a=components(source,color,min_area);b=components(reference,color,min_area)
  assert len(a)==len(b) and len(group)<=len(a)<=8*len(group),f'Missing or extra color components: {color} {len(a)}/{len(b)}/{len(group)}'
  # A source node can have several disjoint fill regions (for example a cylinder).
  # Every component must belong to exactly one real source node; every node must be represented.
  memberships=collections.defaultdict(list)
  for box in a:
   matches=[n['id'] for n in group if box['x0']>=n['x0']-1 and box['y0']>=n['y0']-1 and box['x1']<=n['x1']+1 and box['y1']<=n['y1']+1]
   assert len(matches)==1,'Ambiguous source fill-to-node mapping'
   box['node']=matches[0];memberships[matches[0]].append(box)
  assert set(memberships)=={n['id'] for n in group},'A source node has no independently visible fill'
  for n in group:
   boxes=memberships[n['id']];assert 1<=len(boxes)<=8,'Unexpected node fragmentation'
   union={k:(min if k.endswith('0') else max)(x[k] for x in boxes) for k in ['x0','x1','y0','y1']}
   # Filled pixels begin inside the actual SVG stroke, plus up to two pixels for AA/grid rounding.
   assert max(abs(union[k]-n[k]) for k in union)<=max(4,n.get('strokeWidth',0)/2+2),'Source fill union does not match node geometry'
  centers=lambda boxes:np.array([[(x['x0']+x['x1'])/2/w,(x['y0']+x['y1'])/2/h] for x in boxes])
  ac,bc=centers(a),centers(b)
  # Align whole color-mask extents before assigning small parts of a compound node.
  for axis,index,size in [('x',0,w),('y',1,h)]:
   lo=min(x[axis+'0'] for x in a);hi=max(x[axis+'1'] for x in a);rlo=min(x[axis+'0'] for x in b);rhi=max(x[axis+'1'] for x in b);scale=(rhi-rlo)/(hi-lo);offset=rlo-scale*lo
   assert .85<=scale<=1.15 and abs(offset)<=size*.05,'Large coarse transform requires separate review'
   ac[:,index]=(ac[:,index]*size*scale+offset)/size
  dist=np.linalg.norm(ac[:,None,:]-bc[None,:,:],axis=2);ai,bi=linear_sum_assignment(dist)
  for i,j in zip(ai,bi):
   assert dist[i,j]<.12,'Reference geometry too far from source'
   alternatives=np.delete(dist[i],j)
   if len(alternatives):assert float(alternatives.min())>float(dist[i,j])+2/max(w,h),'Ambiguous reference component assignment'
   pairs.append({'color':list(color),'source':a[i],'reference':b[j]})
 fits={}
 for axis,size in [('x',w),('y',h)]:
  x=np.array([p['source'][axis+str(k)] for p in pairs for k in [0,1]],float);y=np.array([p['reference'][axis+str(k)] for p in pairs for k in [0,1]],float)
  assert np.ptp(x)>=size*.15,'Insufficient anchor extent'
  coeff=np.linalg.lstsq(np.column_stack([x,np.ones_like(x)]),y,rcond=None)[0];res=y-(coeff[0]*x+coeff[1])
  assert .85<=coeff[0]<=1.15 and abs(coeff[1])<=size*.05,'Large transform requires separate review'
  assert float(np.max(abs(res)))<=1.25,'Non-affine node layout difference'
  fits[axis]={'scale':float(coeff[0]),'offset':float(coeff[1]),'max_abs_residual':float(np.max(abs(res))),'residuals':res.tolist()}
 return {'pairs':pairs,'fits':fits,'node_count':len(nodes),'component_count':len(pairs),'component_memberships':dict(collections.Counter(p['source']['node'] for p in pairs)),'method':'all_source_fill_components_assigned_to_unique_source_nodes','scope':'Only whole-source geometry calibration; text, topology and native fidelity are separate gates.'}
