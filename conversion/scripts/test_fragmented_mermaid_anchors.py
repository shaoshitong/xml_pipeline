import json,sqlite3,copy,traceback
import numpy as np
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from mermaid_fragmented_anchor_fit import fit
from mermaid_reference_fit_v3 import rgb
src=np.full((200,300,3),255,dtype=np.uint8);nodes=[]
for i,(x,y,c) in enumerate([(20,20,[210,100,100]),(180,70,[100,210,100]),(90,140,[100,100,210])]):
 src[y:y+30,x:x+60]=c;nodes.append({'id':str(i),'color':c,'x0':x,'x1':x+60,'y0':y,'y1':y+30})
assert fit(src,src,nodes)['node_count']==3
negatives=[]
for name in ['missing_component','extra_component','non_affine_shift','wrong_color','ambiguous_source_nodes']:
 ref=src.copy();ns=copy.deepcopy(nodes)
 if name=='missing_component':ref[20:50,20:80]=255
 if name=='extra_component':ref[110:120,250:260]=[210,100,100]
 if name=='non_affine_shift':ref[20:50,20:80]=255;ref[20:50,40:100]=[210,100,100]
 if name=='wrong_color':ref[20:50,20:80]=[200,100,100]
 if name=='ambiguous_source_nodes':ns[1]=copy.deepcopy(ns[0])
 try:fit(src,ref,ns)
 except AssertionError:negatives.append(name)
 else:raise AssertionError('Accepted corruption '+name)
# Multipart fill: three nodes split by a dark internal separator, each region independently visible.
seg=src.copy()
for n in nodes:seg[n['y0']+13:n['y0']+17,n['x0']:n['x1']]=0
parts=fit(seg,seg,nodes);assert parts['component_count']==6
bad=seg.copy();bad[20:33,20:80]=255
try:fit(seg,bad,nodes)
except AssertionError:negatives.append('missing_one_subregion')
else:raise AssertionError('Accepted missing subregion')
results=[]
for row in json.loads((W/'fragmented_anchor_probe.json').read_text()):
 id=row['id'];B=W/'fragmented_anchor_probe'/id
 try:r=fit(rgb((B/'source.png').read_bytes()),rgb((R/row['reference']).read_bytes()),row['nodes']);results.append({'id':id,'ok':True,'node_count':r['node_count'],'component_count':r['component_count'],'fits':r['fits']})
 except AssertionError as e:results.append({'id':id,'ok':False,'error':str(e)})
out={'at':now(),'negative_checks':negatives,'synthetic_multipart':parts,'real_cases':results,'database_changed':False};(W/'fragmented_anchor_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
