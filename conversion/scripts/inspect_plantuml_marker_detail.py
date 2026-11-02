exec(open('/backup/shaoshitong/img2code_20261029/conversion/scripts/plantuml_native_v4.py').read().split('def build')[0])
from pathlib import Path
import json
R=Path('/backup/shaoshitong/img2code_20261029');d=json.loads((R/'conversion/plantuml_v2_probe/003ac6c589d230952350e02d172bc5eeb920e31be1efc738f87d272de9962337/dom.json').read_text())
for o in d['objects']:
 if o['tag']!='polygon' or not o.get('edge'):continue
 vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',o['pointsAttr'])];poly=list(zip(vals[::2],vals[1::2]))[:-1];i,j=max(((i,j) for i in range(len(poly)) for j in range(i+1,len(poly))),key=lambda ij:distance(poly[ij[0]],poly[ij[1]]));epsilon=min(.4,distance(poly[i],poly[j])*.035);simple=rdp(poly[i:j+1],epsilon)[:-1]+rdp(poly[j:]+poly[:i+1],epsilon)[:-1];line=next(x for x in d['objects'] if x.get('edge')==o['edge'] and x['tag']=='path');pts=line['sampledPoints'];print(o['id'],simple,'tangent',pts[-2:], 'res',handwritten(o,pts,'end'))
s=(R/'evaluation/assets/viewer-static.min.js').read_text()
for term in ['STYLE_SHADOW_BLUR','shadowStyle=','getShadowStyle']:
 ix=[m.start() for m in re.finditer(re.escape(term),s)]
 for i in ix[-5:]:print(s[max(0,i-220):i+600])
