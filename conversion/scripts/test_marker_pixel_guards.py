import io,json
from PIL import Image
from native_worker import R,W,now
from marker_pixel_audit import audit
B=W/'source_vee_incremental_pilot/00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2';r=json.loads((B/'before_record.json').read_text());dom=json.loads((R/r['native_source_font_repair']['source_after_dom_file']).read_text());proof=json.loads((B/'changes.json').read_text());tails=json.loads((B/'tails.json').read_text());before=(B/'before.png').read_bytes();after=(B/'candidate.png').read_bytes();rows=[]
for name,point,color in [('tiny_change_outside_any_native_stroke',(10,10),(254,254,254)),('material_change_on_unchanged_connector',(883,209),(255,0,0))]:
 im=Image.open(io.BytesIO(after)).convert('RGB');im.putpixel(point,color);buf=io.BytesIO();im.save(buf,format='PNG');result=audit(before,buf.getvalue(),dom,proof['markers'],tails);assert not result['ok'];assert any((x['x'],x['y'])==point for x in result['unexplained_pixels']);rows.append({'name':name,'rejected':True})
out={'at':now(),'ok':True,'tests':rows};(W/'marker_pixel_guard_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
