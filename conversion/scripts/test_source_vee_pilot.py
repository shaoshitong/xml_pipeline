import copy,hashlib,json,math,re,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from native_worker import R,W,now
from source_vee_incremental import patch,verify
from source_vee_marker import vee
from native_vee_move_audit import audit
from native_marker_tail_audit import audit as tail_audit
from marker_pixel_audit import audit as pixel_audit
id='00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2';B=W/'source_vee_incremental_pilot'/id;r=json.loads((B/'before_record.json').read_text());dom=json.loads((R/r['native_source_font_repair']['source_after_dom_file']).read_text());xml=(B/'before.drawio').read_text();w,h=Image.open(R/r['original_reference']).size;new,proof=patch(xml,dom,w,h);assert new==(B/'candidate.drawio').read_text();(B/'changes.json').write_text(json.dumps(proof,indent=2));moves=audit(new,proof['markers']);(B/'moves.json').write_text(json.dumps(moves,indent=2));tails=tail_audit(xml,new,proof['markers']);(B/'tails.json').write_text(json.dumps(tails,indent=2));pixels=pixel_audit((B/'before.png').read_bytes(),(B/'candidate.png').read_bytes(),dom,proof['markers'],tails);(B/'pixels.json').write_text(json.dumps(pixels,indent=2));assert pixels['ok'],pixels;negative=[]
for name in ['node_geometry','wrong_arrow_type','font_payload']:
 root=E.fromstring(new)
 if name=='node_geometry':c=next(c for c in root.iter('mxCell') if c.get('id','').startswith('node_'));c.find('mxGeometry').set('x','999')
 elif name=='wrong_arrow_type':c=next(c for c in root.iter('mxCell') if c.get('edge')=='1');c.set('style',c.get('style').replace('endArrow=open;','endArrow=block;'))
 else:root.find('.//mxGraphModel').set('extFonts','')
 try:verify(xml,E.tostring(root,encoding='unicode'),proof)
 except AssertionError:negative.append(name)
 else:raise AssertionError('Mutation passed '+name)
objects={o['id']:o for o in dom['objects']};shape=copy.deepcopy(objects[proof['markers'][0]['source_arrow_object']]);p=objects[proof['markers'][0]['native_edge']];nums=re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',shape['pointsAttr']);nums[4]=str(float(nums[4])+10);shape['pointsAttr']=' '.join(nums);assert vee(shape,p['sampledPoints'],'end') is None;negative.append('asymmetric_vee_contour');out={'at':now(),'ok':True,'id':id,'native_markers':len(proof['markers']),'actual_endpoint_moves':len(moves['moves']),'maximum_original_tip_error_px':max(x['source_tip_error'] for x in moves['moves']),'pixel_audit':pixels,'verified_native_tails':len(tails),'negative_tests_rejected':negative,'accepted':False};(W/'source_vee_incremental_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
