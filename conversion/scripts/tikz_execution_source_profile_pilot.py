"""Remote nonpublishing source-profile proof on the real bound draft."""
import copy,hashlib,json,uuid,xml.etree.ElementTree as E
from pathlib import Path
from native_worker import R,W,now
from tikz_execution_source_profile import check_execution_profile,provenance_from_pilot,FIELD
sha=lambda b:hashlib.sha256(b).hexdigest()
pilot=json.loads((W/'tikz_execution_binding_pilot.json').read_text());assert pilot['ok'];folder=R/pilot['work'];record=json.loads((folder/'baseline_record.json').read_text());xml=(folder/'candidate.drawio').read_text();record={**record,'code_sha256':sha(xml.encode()),FIELD:provenance_from_pilot(folder/'report.json')}
positive=check_execution_profile(record,xml);assert positive['ok'],positive
negatives=[]
for name in ('changed_current_text','forged_source_hash','wrong_sidecar_hash','wrong_baseline_hash','wrong_script_hash','missing_script_pin','changed_script_locator'):
 bad=copy.deepcopy(record);text=xml
 if name=='changed_current_text':
  root=E.fromstring(xml);next(c for c in root.iter('mxCell') if c.get('value')).set('value','CORRUPTED CURRENT LABEL');text=E.tostring(root,encoding='unicode');bad['code_sha256']=sha(text.encode());bad[FIELD]['candidate_code_sha256']=bad['code_sha256']
 if name=='forged_source_hash':bad['source_code_sha256']='0'*64;bad[FIELD]['source_code_sha256']='0'*64
 if name=='wrong_sidecar_hash':bad[FIELD]['files']['sidecar']['sha256']='0'*64
 if name=='wrong_baseline_hash':bad[FIELD]['files']['baseline_xml']['sha256']='0'*64
 if name=='wrong_script_hash':bad[FIELD]['scripts']['tikz_execution_binding.py']['sha256']='0'*64
 if name=='missing_script_pin':bad[FIELD]['scripts'].pop('tikz_execution_graph_hooks.tex')
 if name=='changed_script_locator':bad[FIELD]['scripts']['tikz_execution_binding.py']['file']=bad[FIELD]['scripts']['tikz_execution_graph.py']['file']
 result=check_execution_profile(bad,text);assert not result['ok'],name;negatives.append({'case':name,'rejected':True,'failures':result['failures']})
out={'at':now(),'ok':True,'id':pilot['id'],'positive':positive,'negative_fixtures':negatives,'published':False,'candidate_code_sha256':sha(xml.encode()),'source_profile_module_sha256':sha((W/'scripts/tikz_execution_source_profile.py').read_bytes()),'pilot_report':str((folder/'report.json').relative_to(R))}
(W/'tikz_execution_source_profile_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'at':out['at'],'ok':True,'id':pilot['id'],'source_coverage':positive['evidence']['source_coverage'],'fresh_pdf_identity':positive['evidence']['pdf_identity'],'negative_fixture_count':len(negatives),'native_marker_contour_gate_required':positive['evidence']['native_marker_contour_gate_required'],'published':False}))
