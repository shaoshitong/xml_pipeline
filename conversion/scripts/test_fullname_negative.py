import json,urllib.parse,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from svg_fullname_fonts import verify_patch,verify_render_fonts
id='00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2';B=W/'svg_fullname_native_pilot'/id;before=(B/'before.drawio').read_text();after=(B/'candidate.drawio').read_text();changes=json.loads((B/'changes.json').read_text());source=json.loads((B/'source_font_changes.json').read_text());baseline=json.loads((B/'before_render.json').read_text());passed=[]
for mode in ['move_nontext_node','corrupt_text','alter_clip_geometry']:
 root=E.fromstring(after)
 if mode=='move_nontext_node':c=next(c for c in root.iter('mxCell') if c.get('id','').startswith('node_'));g=c.find('mxGeometry');g.set('x',str(float(g.get('x'))+1))
 elif mode=='corrupt_text':c=next(c for c in root.iter('mxCell') if c.get('id')==changes[0]['cell']);c.set('value',c.get('value')+'X')
 else:c=next(c for c in root.iter('mxCell') if c.get('id')==changes[0]['cell']);g=c.find('mxGeometry');g.set('width',str(float(g.get('width'))+1))
 rejected=False
 try:verify_patch(before,E.tostring(root,encoding='unicode'),changes)
 except AssertionError:rejected=True
 assert rejected,mode;passed.append(mode)
root=E.fromstring(after);model=root.find('.//mxGraphModel');urls=dict(s.split('^',1) for s in model.get('extFonts').split('|'));old=json.loads((B/'before_record.json').read_text());wrong_family=next(f['family'] for f in old['native_embedded_fonts'] if f['physical_postscript_name']=='TimesNewRomanPSMT');wrong_uri=urls[wrong_family]
for change in changes:urls[change['family']]=wrong_uri
model.set('extFonts','|'.join(k+'^'+v for k,v in urls.items()));changed={c['cell'] for c in changes}
for c in root.iter('mxCell'):
 if c.get('id') in changed:
  styles=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);styles['fontSource']=urllib.parse.quote(wrong_uri,safe='');c.set('style',';'.join(k+'='+v for k,v in styles.items())+';')
xml=E.tostring(root,encoding='unicode');w,h=Image.open(B/'candidate.png').size;render=native.native_job(xml,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];rejected=False
try:verify_render_fonts(baseline,render['native_render'],changes,source)
except AssertionError:rejected=True
assert rejected;actual=[f for row in render['native_render']['actual_platform_font_usage'] if row['cell'] in changed for f in row['fonts'] if f['glyphCount']];assert actual and all(f['isCustomFont'] and f['postScriptName']=='TimesNewRomanPSMT' for f in actual);out={'at':now(),'ok':True,'graph_corruption_negatives_rejected':passed,'loaded_but_wrong_physical_font_rejected':True,'wrong_font_still_loaded_as_custom':True};(W/'svg_fullname_font_negative_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
