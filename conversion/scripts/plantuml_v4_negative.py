import copy,json,math
from native_worker import W,now
from plantuml_native_v4 import handwritten,shadow_filter
D=json.loads((W/'plantuml_v4_probe/003ac6c589d230952350e02d172bc5eeb920e31be1efc738f87d272de9962337/dom.json').read_text());o=next(x for x in D['objects'] if x['tag']=='polygon' and x.get('edge'));line=next(x for x in D['objects'] if x.get('edge')==o['edge'] and x['tag']=='path');pts=line['sampledPoints'];results=[]
def check(name,p):
 assert p,name;results.append({'test':name,'passed':True})
check('original handwritten marker recognized',handwritten(o,pts,'end') is not None)
check('wrong endpoint rejected',handwritten(o,pts,'start') is None)
z=copy.deepcopy(o);z['matrix'][4]+=100;check('distant marker rejected',handwritten(z,pts,'end') is None)
z=copy.deepcopy(o);poly=[(100+5*math.cos(i*math.pi/12),100+5*math.sin(i*math.pi/12)) for i in range(25)];z['pointsAttr']=','.join(str(v) for p in poly for v in p);check('circle not recognized as arrow',handwritten(z,pts,'end') is None)
f=next(x['filterDefinition'] for x in D['objects'] if x.get('filterDefinition'));check('source black shadow recognized',shadow_filter(f,[1,0,0,1,0,0])=={'dx':4.,'dy':4.,'blur':2.,'opacity':.4})
z=copy.deepcopy(f);z['children'][3]['attrs']['mode']='multiply';check('blend mode not misread as shadow',shadow_filter(z,[1,0,0,1,0,0]) is None)
z=copy.deepcopy(f);z['children'][1]['attrs']['values']='1 '+z['children'][1]['attrs']['values'][2:];check('colored matrix rejected',shadow_filter(z,[1,0,0,1,0,0]) is None)
check('anisotropic shadow transform rejected',shadow_filter(f,[1,0,0,2,0,0]) is None)
(W/'plantuml_v4_probe/negative_checks.json').write_text(json.dumps({'at':now(),'results':results},indent=2));print(json.dumps(results))
