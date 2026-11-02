import json,xml.etree.ElementTree as E
from native_worker import W,now
from svg_source_coverage_v2 import audit
id='741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd';p=W/'plantuml_source_probe'/id;dom=json.loads((p/'dejavu_fonts_dom.json').read_text());stats=json.loads((p/'dejavu_fonts_stats.json').read_text());xml=(p/'dejavu_fonts.drawio').read_text();assert audit(dom,xml,stats)['ok'];results=[]
for name in ['wrong_terminal','missing_label','missing_shape']:
 root=E.fromstring(xml);cells=list(root.iter('mxCell'));container=root.find('.//mxGraphModel/root')
 if name=='wrong_terminal':next(c for c in cells if c.get('edge')=='1').set('target','node_nonexistent')
 elif name=='missing_label':container.remove(next(c for c in cells if c.get('value')))
 else:container.remove(next(c for c in cells if 'shape=stencil(' in c.get('style','')))
 result=audit(dom,E.tostring(root,encoding='unicode'),stats);assert not result['ok'];results.append({'mutation':name,'rejected':True,'errors':result['errors']})
out={'at':now(),'case':id,'results':results};(W/'plantuml_negative_checks.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
