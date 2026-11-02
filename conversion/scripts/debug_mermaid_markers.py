import json,math,re
from native_worker import W
from mermaid_native_v1 import marker
p=W/'mermaid_native_probe/ab692a4bc019ce00ed3be2f5838f2285c5789c6ddcb59fc94a6d2ba16c9ff9dd';d=json.loads((p/'dom.json').read_text());by={o['id']:o for o in d['objects']}
for o in d['objects']:
 if not o.get('mermaidMarker'):continue
 owner=by[o['markerOwner']];pts=owner['sampledPoints'];vals=[float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',o['pointsAttr'])];a,b,c,d,e,f=o['matrix'];poly=[(a*x+c*y+e,b*x+d*y+f) for x,y in zip(vals[::2],vals[1::2])];print(o['id'],'fill',o['style']['fill'],'line',owner['style']['stroke'],'polygon',poly,'end',pts[-2:],'found',marker(o,pts,'end'))
