"""Corruptions of the real frozen candidate must retain the exact input XML."""
import copy,hashlib,json,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from native_worker import R,W,now,native
from tikz_execution_graph import parse_events
from tikz_execution_binding import bind_execution
sha=lambda b:hashlib.sha256(b).hexdigest()
report=json.loads((W/'tikz_execution_binding_pilot.json').read_text());assert report['ok'];folder=R/report['work'];xml=(folder/'baseline.drawio').read_text();record=json.loads((folder/'baseline_record.json').read_text());dom=json.loads((folder/'source_dom.json').read_text());locator=json.loads((folder/'sidecar_locator.json').read_text());proof=Path(locator['proof']);sidecar=json.loads(proof.read_text());events=parse_events((proof.parent/'instrumented/source.iic').read_text());matrix=locator['svg_root_screen_ctm']
candidate,positive=bind_execution(xml,copy.deepcopy(dom),copy.deepcopy(sidecar),events,matrix);assert positive['complete'];assert sha(candidate.encode())==report['output_code_sha256'];results=[]
for name in ('changed_text','changed_shape','changed_color','changed_geometry','missing_source_object','changed_source_relationship','wrong_physical_unit','preexisting_extra_edge','preexisting_parented_text'):
 root=E.fromstring(xml);bad_dom=copy.deepcopy(dom);bad_sidecar=copy.deepcopy(sidecar);bad_matrix=list(matrix)
 cells=list(root.iter('mxCell'));text=next(c for c in cells if c.get('value'));shape=next(c for c in cells if 'shape=stencil(' in c.get('style',''))
 if name=='changed_text':text.set('value','CORRUPTED TEXT')
 if name=='changed_shape':shape.set('style',shape.get('style').replace('shape=stencil(','shape=broken_stencil(',1))
 if name=='changed_color':text.set('style',text.get('style').replace('fontColor=','fontColor=#123456;previousFontColor=',1))
 if name=='changed_geometry':shape.find('mxGeometry').set('x',str(float(shape.find('mxGeometry').get('x'))+3))
 if name=='missing_source_object':bad_dom['objects'].pop(0)
 if name=='changed_source_relationship':bad_sidecar['graph']['edges'][0]['target']='NON_SOURCE_NODE'
 if name=='wrong_physical_unit':bad_matrix[0]*=1.1
 if name=='preexisting_extra_edge':E.SubElement(root.find('.//root'),'mxCell',id='fake',edge='1',source='v1',target='v15',parent='1')
 if name=='preexisting_parented_text':text.set('parent','v1')
 bad=E.tostring(root,encoding='unicode');output,proof_result=bind_execution(bad,bad_dom,bad_sidecar,events,bad_matrix);assert not proof_result['complete'] and output==bad,name
 results.append({'case':name,'rejected_without_partial_xml_changes':True,'issues':proof_result['issues']})
width,height=Image.open(R/record['original_reference']).size;fresh=native.native_job(candidate,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==(folder/'candidate.png').read_bytes()
assert sha((R/record['code_file']).read_bytes())==record['code_sha256'] and sha((R/record['image_file']).read_bytes())==record['image_sha256']
out={'at':now(),'ok':True,'id':report['id'],'real_baseline_candidate_reproduced':True,'fresh_native_png_byte_identical':True,'canonical_inputs_unchanged':True,'binding_module_sha256':sha((W/'scripts/tikz_execution_binding.py').read_bytes()),'candidate_code_sha256':sha(candidate.encode()),'candidate_png_sha256':sha(fresh['png']),'negative_fixtures':results,'published':False,'pilot_report':str((folder/'report.json').relative_to(R))}
(W/'tikz_execution_binding_guard_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
