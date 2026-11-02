import json,xml.etree.ElementTree as E
from native_worker import R,W,native,now
B=W/'font_portability_probe/fixture';xml=(B/'candidate.drawio').read_text();root=E.fromstring(xml);root.find('.//mxGraphModel').attrib.pop('extFonts',None)
for c in root.iter('mxCell'):
 s=c.get('style')
 if s:c.set('style',';'.join(x for x in s.split(';') if x and not x.startswith('fontSource='))+';')
broken=E.tostring(root,encoding='unicode');r=native.native_job(broken,680,240,90,W/'rendering_fontproof/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'];used=[f for row in r['native_render']['actual_platform_font_usage'] for f in row['fonts'] if f['glyphCount']];assert used and not any(f['isCustomFont'] for f in used);assert r['png']!=(B/'candidate.png').read_bytes();result={'at':now(),'ok':True,'removed_font_payload_detected_by_actual_platform_fonts':True,'removed_font_payload_changes_pixels':True};(W/'font_portability_probe/negative_tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
