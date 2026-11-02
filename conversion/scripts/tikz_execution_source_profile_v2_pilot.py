"""Exercise the batch source/marker APIs on the same unpublished real draft."""
import copy,hashlib,json,xml.etree.ElementTree as E
from native_worker import R,W,now
from tikz_execution_source_profile_v2 import FIELD,provenance_from_paint_pilot,check_execution_profile,check_execution_marker_render
sha=lambda b:hashlib.sha256(b).hexdigest()
paint=json.loads((W/'tikz_execution_marker_paint_pilot.json').read_text());assert paint['ok'];folder=R/paint['work'];pilot=json.loads((W/'tikz_execution_binding_pilot.json').read_text());record=json.loads((R/pilot['work']/'baseline_record.json').read_text());xml=(folder/'candidate.drawio').read_text();png=(folder/'candidate.png').read_bytes();record={**record,'code_sha256':sha(xml.encode()),'image_sha256':sha(png),FIELD:provenance_from_paint_pilot(folder/'report.json')}
source=check_execution_profile(record,xml);assert source['ok'],source;render=check_execution_marker_render(record,xml,png);assert render['ok'],render
negatives=[]
for name in ('current_native_text_corruption','current_native_relation_corruption','changed_script_pin','missing_script_pin','forged_native_png_hash'):
 bad=copy.deepcopy(record);text=xml
 if name in ('current_native_text_corruption','current_native_relation_corruption'):
  root=E.fromstring(xml)
  if name=='current_native_text_corruption':next(c for c in root.iter('mxCell') if c.get('value')).set('value','CORRUPTED TEXT')
  else:
   edge=next(c for c in root.iter('mxCell') if c.get('edge')=='1');edge.set('target',edge.get('source'))
  text=E.tostring(root,encoding='unicode');bad['code_sha256']=sha(text.encode());bad[FIELD]['candidate_code_sha256']=bad['code_sha256']
 if name=='changed_script_pin':bad[FIELD]['scripts']['tikz_execution_marker_paint_fit.py']['sha256']='0'*64
 if name=='missing_script_pin':bad[FIELD]['scripts'].pop('tikz_execution_binding_v2.py')
 if name=='forged_native_png_hash':bad['image_sha256']='0'*64
 result=check_execution_marker_render(bad,text,png) if name=='forged_native_png_hash' else check_execution_profile(bad,text);assert not result['ok'],name;negatives.append({'case':name,'rejected':True,'failures':result['failures']})
out={'at':now(),'ok':True,'published':False,'id':paint['id'],'work':paint['work'],'source':source,'native_marker_render':render,'negative_fixtures':negatives,'record_provenance_field':FIELD,'provenance':record[FIELD]};(folder/'source_profile_v2.json').write_text(json.dumps(out,indent=2)+'\n');(W/'tikz_execution_source_profile_v2_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'ok':True,'published':False,'source_profile_passed':source['ok'],'native_marker_gate_passed':render['ok'],'code_sha256':record['code_sha256'],'image_sha256':record['image_sha256'],'source_objects':source['evidence']['source_coverage']['original_source_objects'],'native_edges':source['evidence']['source_coverage']['native_bound_edges'],'negative_fixtures':len(negatives)}))
