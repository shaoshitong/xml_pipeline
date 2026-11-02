import json,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from fontmix_validation import verify_fonts
p=W/'font_portability_primary_v2/fixture';root=E.fromstring((p/'zero.drawio').read_text());root.find('.//mxGraphModel').attrib.pop('extFonts',None)
for cell in root.iter('mxCell'):cell.set('style',';'.join(x for x in cell.get('style','').split(';') if x and not x.startswith('fontSource='))+';')
w,h=Image.open(p/'zero.png').size;render=native.native_job(E.tostring(root,encoding='unicode'),w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];rejected=False
try:verify_fonts(json.loads((p/'observations.json').read_text()),render['native_render'],json.loads((p/'details.json').read_text()))
except AssertionError as e:rejected=True;reason=str(e)
assert rejected and render['png']!=(p/'zero.png').read_bytes();report={'at':now(),'ok':True,'stripped_embedded_fonts_rejected_by_actual_native_font_evidence':True,'stripping_fonts_changes_native_pixels':True,'reason':reason};(W/'native_font_v2_negative_test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
