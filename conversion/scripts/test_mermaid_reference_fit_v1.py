import json,sqlite3,copy,traceback
import numpy as np
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from mermaid_reference_fit_v1 import fit,convert_variant
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
ids=['0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641','02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce','042a622a01d9659d0716ba8be9ce5a6c70030e4d080b908c402ac5280e644035','047acd3596838a3e998ae96081f3d778bdec3210a6eb1e0ced7e4aafbe81733f'];D=sqlite3.connect(W/'jobs.sqlite',timeout=60);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for id in ids:
  r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);folder=W/'mermaid_reference_fit_smoke'/id;folder.mkdir(parents=True,exist_ok=True);(folder/'before_record.json').write_text(json.dumps(r,indent=2));variants=[]
  for name,font in [('default',None),('arial','Arial')]:
   try:
    report=convert_variant(b,r,folder/name,font);variants.append({'variant':name,'ok':True,'score':report['native_reference_ssim'],'prior':report['prior_ssim'],'moves':report['actual_endpoint_moves'],'parameters':report['parameters']})
   except Exception as e:
    (folder/(name+'_error.txt')).write_text(traceback.format_exc());variants.append({'variant':name,'ok':False,'error':repr(e)})
  results.append({'id':id,'variants':variants});print(json.dumps(results[-1]),flush=True)
 b.close()
out={'at':now(),'guard_negative_tests':negatives,'results':results,'db_changed':False,'accepted':False};(W/'mermaid_reference_fit_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
