"""One bounded two-process full-QA revalidation after marker inventory hardening."""
import concurrent.futures,copy,json,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
PRIOR=W/'compiler_svg_scene_frontend_v6/controls/e52c3d31c8504dd9a2fd06e0099dfe61/receipt.json'
DEVELOPMENT=W/'compiler_svg_scene_frontend_v6/development/630da459933c4d45a03e6c58513602d9/report.json'

def evaluate(task):
 import compiler_svg_general_guard_v2 as plugin
 import compiler_svg_scene_frontend_v6 as front
 from compiler_svg_scene_quality_ro_v6 import verify
 rp=Path(task['record_file']);record=json.loads(rp.read_bytes());quality=verify(record['id'],rp,R,Path(plugin.__file__),W/'prototype/candidate_quality_ro_v1'/('svg_coordinates_final_'+task['name']+'_'+uuid.uuid4().hex))
 return {**task,'id':record['id'],'ok':quality['ok'],'failures':quality['failures'],'record':front._entry(rp),'quality_report':front._entry(Path(quality['evidence_file']))}

def main():
 import compiler_svg_general_guard_v2 as plugin
 import compiler_svg_scene_frontend_v6 as front
 from svg_convert_v3 import unpack,pack
 pin=plugin.configuration();prior=json.loads(PRIOR.read_text());dev=json.loads(DEVELOPMENT.read_text());parent=W/'compiler_svg_scene_frontend_v6/controls'/uuid.uuid4().hex;parent.mkdir(parents=True);tasks=[]
 for row in dev['results']:
  if (row.get('full_quality') or {}).get('ok'):tasks.append({'name':'positive_'+row['id'][:8],'role':'positive','record_file':row['record_file']})
 regression=prior['existing_positive'];tasks.append({'name':'existing_positive','role':'regression','record_file':str(R/regression['record']['file'])})
 for row in prior['negative_controls']:tasks.append({'name':row['variant'],'role':'negative','record_file':str(R/row['record']['file'])})
 # Predeclared extra arrow must actually paint: this catches tiny undeclared
 # markers even if a global image tolerance happened to overlook their pixels.
 original=json.loads((R/prior['positive']['file']).read_text());tree=E.fromstring((R/original['code_file']).read_text());edge=next(c for c in tree.iter('mxCell') if c.get('edge')=='1' and unpack(c.get('style')).get('startArrow','none')=='none');style=unpack(edge.get('style'));style.update(startArrow='block',startSize='8',startFill='1',startFillColor='#000000',startStrokeColor='transparent');edge.set('style',pack(style));xml=E.tostring(tree,encoding='unicode');model=tree.find('.//mxGraphModel');size=tuple(int(float(model.get(k))) for k in ('pageWidth','pageHeight'));render=front._native(xml,size);dest=R/'clean/compiler_svg_coordinates_negative_controls_v1'/original['id']/uuid.uuid4().hex;dest.mkdir(parents=True);(dest/'candidate.drawio').write_text(xml);(dest/'candidate.png').write_bytes(render['png']);record=copy.deepcopy(original);record.update(code_file=str((dest/'candidate.drawio').relative_to(R)),image_file=str((dest/'candidate.png').relative_to(R)),code_sha256=front.sha(xml.encode()),image_sha256=front.sha(render['png']),quality_state='actual_negative_control',accepted=False);rp=dest/'record.json';rp.write_bytes(front.raw(record));tasks.append({'name':'extra_opposite_arrow','role':'negative','record_file':str(rp)})
 if front.sha(render['png'])==original['image_sha256']:raise ValueError('extra_arrow_negative_did_not_change_actual_native_pixels')
 (parent/'plan.json').write_bytes(front.raw({'tasks':tasks,'workers':2,'once_per_task':True,'frozen_configuration':pin,'new_heldout_consumed':0,'model_calls':0}));print(json.dumps({'controls':str(parent),'jobs':len(tasks),'workers':2}),flush=True);rows=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
  futures=[executor.submit(evaluate,t) for t in tasks]
  for future in concurrent.futures.as_completed(futures):
   row=future.result();rows.append(row);(parent/'progress.json').write_bytes(front.raw(rows));print(json.dumps({k:v for k,v in row.items() if k!='record_file'}),flush=True)
 unchanged=plugin.configuration()==pin;positives=[r for r in rows if r['role']=='positive'];regression=next(r for r in rows if r['role']=='regression');negative=[r for r in rows if r['role']=='negative'];passed=all(r['ok'] for r in positives+[regression]) and all(not r['ok'] for r in negative) and unchanged
 newdev={'schema':'svg_coordinate_final_development_v2','configuration_unchanged':unchanged,'results':[{'id':r['id'],'record_file':r['record_file'],'full_quality':{'ok':r['ok'],'report':str(R/r['quality_report']['file']),'failures':r['failures']}} for r in positives],'previous_development':front._entry(DEVELOPMENT),'new_heldout_consumed':0,'model_calls':0};(parent/'development.json').write_bytes(front.raw(newdev))
 receipt={'schema':'svg_coordinate_actual_controls_v2','positive':prior['positive'],'negative_controls':[{'variant':r['name'],'rejected':not r['ok'],'fresh_actual_png':True,'rehashed_candidate':True,'record':r['record'],'quality_report':r['quality_report'],'failures':r['failures']} for r in negative],'existing_positive':{'id':regression['id'],'ok':regression['ok'],'record':regression['record'],'quality_report':regression['quality_report'],'failures':regression['failures']},'configuration_unchanged':unchanged,'model_calls':0,'new_heldout_consumed':0,'passed':passed};(parent/'receipt.json').write_bytes(front.raw(receipt));print(json.dumps({'receipt':str(parent/'receipt.json'),'development':str(parent/'development.json'),'passed':passed}),flush=True)

if __name__=='__main__':main()
