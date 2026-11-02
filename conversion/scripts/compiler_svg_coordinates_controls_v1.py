"""Finite existing positive and rehashed real-paint negative controls."""
import copy,json,sqlite3,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))

def main():
 import compiler_svg_general_guard_v2 as plugin
 import compiler_svg_scene_frontend_v6 as front
 from compiler_svg_scene_quality_ro_v6 import verify
 from svg_convert_v3 import unpack,pack
 identifier='5b91ae464a6f684b1e0cf5726ffb601db15b63953b7db1cb03ddb0f91017c1fc'
 positive_file=R/'clean/compiler_svg_scene_frontend_v6/5b'/identifier/'9ea82d45d89148f395a5a2376fbc7ff1/record.json'
 parent=W/'compiler_svg_scene_frontend_v6/controls'/uuid.uuid4().hex;parent.mkdir(parents=True);pin=plugin.configuration();rows=[]
 plan={'positive_record':front._entry(positive_file),'negative_variants':['explicit_endpoint_moved','filled_marker_removed','source_text_deleted','extra_opaque_cover'],'source_reference_gates_unchanged':True,'new_heldout_consumed':0,'frozen_configuration':pin}
 (parent/'plan.json').write_bytes(front.raw(plan));print(json.dumps({'controls':str(parent)}),flush=True)
 original=json.loads(positive_file.read_text());original_xml=(R/original['code_file']).read_text()
 for variant in plan['negative_variants']:
  root=E.fromstring(original_xml);cells={c.get('id'):c for c in root.iter('mxCell')};edges=[c for c in cells.values() if c.get('edge')=='1']
  if variant=='explicit_endpoint_moved':
   point=next(p for edge in edges for p in edge.findall('mxGeometry/mxPoint') if p.get('as') in ('sourcePoint','targetPoint'));point.set('x',str(float(point.get('x'))+3))
  elif variant=='filled_marker_removed':
   edge=next(e for e in edges if any(unpack(e.get('style')).get(k,'none')!='none' for k in ('startArrow','endArrow')));st=unpack(edge.get('style'));side=next(k for k in ('start','end') if st.get(k+'Arrow','none')!='none');st[side+'Arrow']='none';edge.set('style',pack(st))
  elif variant=='source_text_deleted':next(c for c in cells.values() if c.get('value','').strip()).set('value','')
  else:
   model=root.find('.//mxGraphModel/root');c=E.SubElement(model,'mxCell',{'id':'negative_opaque_cover','parent':'1','vertex':'1','style':'fillColor=#000000;strokeColor=none;'});E.SubElement(c,'mxGeometry',{'x':'20','y':'20','width':'30','height':'30','as':'geometry'})
  xml=E.tostring(root,encoding='unicode');record=copy.deepcopy(original);dest=R/'clean/compiler_svg_coordinates_negative_controls_v1'/identifier/uuid.uuid4().hex;dest.mkdir(parents=True);model=root.find('.//mxGraphModel');size=tuple(int(float(model.get(k))) for k in ('pageWidth','pageHeight'));render=front._native(xml,size)
  for name,blob in [('candidate.drawio',xml.encode()),('candidate.png',render['png'])]:(dest/name).write_bytes(blob)
  record.update(code_file=str((dest/'candidate.drawio').relative_to(R)),image_file=str((dest/'candidate.png').relative_to(R)),code_sha256=front.sha(xml.encode()),image_sha256=front.sha(render['png']),quality_state='actual_negative_control',accepted=False);rp=dest/'record.json';rp.write_bytes(front.raw(record))
  quality=verify(identifier,rp,R,Path(plugin.__file__),W/'prototype/candidate_quality_ro_v1'/('svg_coordinate_negative_'+variant+'_'+uuid.uuid4().hex));row={'variant':variant,'rejected':not quality['ok'],'fresh_actual_png':True,'rehashed_candidate':True,'record':front._entry(rp),'quality_report':front._entry(Path(quality['evidence_file'])),'failures':quality['failures']};rows.append(row);print(json.dumps(row),flush=True);(parent/'progress.json').write_bytes(front.raw(rows))
 regression=R/'release/compiler_iterations/controls/svg_general_scene_v5_guard_controls_20261101_v1/qualified.jsonl';baseline=json.loads(regression.read_text().splitlines()[0]);rp=R/baseline.get('record_file',baseline.get('record','')) if isinstance(baseline.get('record_file',baseline.get('record','')),str) else None
 # The root's accepted manifests record metadata_file, not the original proposal.
 if rp is None or not rp.is_file():rp=R/baseline['metadata_file']
 quality=verify(baseline['id'],rp,R,Path(plugin.__file__),W/'prototype/candidate_quality_ro_v1'/('svg_coordinates_existing_positive_'+uuid.uuid4().hex));old_positive={'id':baseline['id'],'ok':quality['ok'],'record':front._entry(rp),'quality_report':front._entry(Path(quality['evidence_file'])),'failures':quality['failures']};print(json.dumps({'regression_positive':old_positive}),flush=True)
 result={'schema':'svg_coordinate_actual_controls_v1','positive':front._entry(positive_file),'negative_controls':rows,'existing_positive':old_positive,'configuration_unchanged':plugin.configuration()==pin,'model_calls':0,'new_heldout_consumed':0,'passed':all(r['rejected'] for r in rows) and quality['ok'] and plugin.configuration()==pin};(parent/'receipt.json').write_bytes(front.raw(result));print(json.dumps({'receipt':str(parent/'receipt.json'),'passed':result['passed']}),flush=True)

if __name__=='__main__':main()
