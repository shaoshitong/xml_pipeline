"""Two consumed-source positives and actual rehashed paint negatives; no heldout."""
import concurrent.futures,copy,json,sqlite3,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
IDS=('05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798','741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd')
NEGATIVES=('deleted_source_label','changed_bound_terminal','opaque_text_cover','oversized_native_marker','missing_source_arrow','wrong_uniform_spacing','wrong_whole_run_origin')

def asset(p):
 import compiler_plantuml_natural_candidate_v10 as c
 p=Path(p);return {'file':str(p),'sha256':c.sha(p.read_bytes())}

def positive(task):
 import compiler_plantuml_natural_candidate_v10 as c
 from deterministic_candidate_quality_ro_v1 import verify
 identifier,owner=task;owner=Path(owner)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
  columns=[x[1] for x in db.execute('pragma table_info(jobs)')];snapshot=db.execute('select * from jobs where id=?',(identifier,)).fetchone();job=dict(zip(columns,snapshot));record=json.loads(job['output_record']);attempt=c.convert(record,job,owner/identifier)
  row={'id':identifier,'converted':attempt['ok'],'reason':attempt.get('reason'),'detail':attempt.get('detail'),'full_quality':None}
  if attempt['ok']:
   q=verify(identifier,attempt['record_file'],R,Path(c.__file__),W/'prototype/candidate_quality_ro_v1'/('plantuml_v10_positive_'+identifier[:8]+'_'+uuid.uuid4().hex));row.update(record=asset(attempt['record_file']),full_quality={'ok':q['ok'],'failures':q['failures'],'report':asset(q['evidence_file'])})
  row['canonical_unchanged']=db.execute('select * from jobs where id=?',(identifier,)).fetchone()==snapshot
 return row

def negative(task):
 import compiler_plantuml_natural_candidate_v10 as c
 from svg_convert_v3 import unpack,pack
 from auto_quality_source_vector_v2 import _world_box
 from clip_canvas_render_v4b import render
 from strict_canvas_gate import require_declared_page
 from deterministic_candidate_quality_ro_v1 import verify
 positive_file,name=task;record=json.loads(Path(positive_file).read_text());tree=E.fromstring((R/record['code_file']).read_text());cells={cell.get('id'):cell for cell in tree.iter('mxCell')};edge=next(cell for cell in cells.values() if cell.get('edge')=='1' and any(unpack(cell.get('style')).get(side+'Arrow','none')!='none' for side in ('start','end')))
 if name=='deleted_source_label':next(cell for cell in cells.values() if cell.get('value','').strip()).set('value','')
 elif name=='changed_bound_terminal':edge.set('target',edge.get('source'))
 elif name in ('wrong_uniform_spacing','wrong_whole_run_origin'):
  label=next(cell for cell in cells.values() if cell.get('value','').strip());value=label.get('value')
  if name=='wrong_uniform_spacing':value=value.replace('letter-spacing:', 'letter-spacing:1.5px;unused-source-spacing:',1)
  else:
   import re
   value=re.sub(r'left:([+\-\d.eE]+)px',lambda m:'left:'+str(float(m[1])+1.)+'px',value,count=1)
  label.set('value',value)
 elif name=='opaque_text_cover':
  label=next(cell for cell in cells.values() if cell.get('value','').strip());x,y,w,h=_world_box(label,cells);cell=E.SubElement(tree.find('.//mxGraphModel/root'),'mxCell',{'id':'actual_negative_opaque_cover','parent':'1','vertex':'1','style':'fillColor=#ffffff;strokeColor=none;opacity=100;'});E.SubElement(cell,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
 else:
  style=unpack(edge.get('style'));side=next(side for side in ('start','end') if style.get(side+'Arrow','none')!='none')
  if name=='oversized_native_marker':style[side+'Size']=str(float(style.get(side+'Size',6))+4)
  elif name=='missing_source_arrow':style[side+'Arrow']='none'
  edge.set('style',pack(style))
 xml=E.tostring(tree,encoding='unicode');model=tree.find('.//mxGraphModel');width,height=[int(float(model.get(k))) for k in ('pageWidth','pageHeight')];actual=render(xml,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 if not actual.get('ok'):raise ValueError('negative_actual_native_render_failed:'+str(actual.get('error')))
 require_declared_page(actual['native_render'],width,height);destination=R/'clean/plantuml_textlength_full_label_release_negative_controls_v1'/record['id']/uuid.uuid4().hex;destination.mkdir(parents=True);(destination/'candidate.drawio').write_text(xml);(destination/'candidate.png').write_bytes(actual['png']);record.update(code_file=str((destination/'candidate.drawio').relative_to(R)),image_file=str((destination/'candidate.png').relative_to(R)),code_sha256=c.sha(xml.encode()),image_sha256=c.sha(actual['png']),accepted=False,quality_state='actual_negative_control');rp=destination/'record.json';rp.write_bytes(c.raw(record));q=verify(record['id'],rp,R,Path(c.__file__),W/'prototype/candidate_quality_ro_v1'/('plantuml_v10_negative_'+name+'_'+uuid.uuid4().hex));profile=q.get('checks',{}).get('source',{});marker=profile.get('evidence',{}).get('source_native_markers',{}).get('actual_full_closed_marker_paint_and_editing',{});bounds=[x['continuous_full_paint_certificate'] for x in marker.get('markers',[])];return {'name':name,'id':record['id'],'rejected':q['ok'] is False,'fresh_source_rejected':profile.get('ok') is False and bool(profile.get('failures')),'full_closed_paint_lower_bound_exceeds_one_pixel':any(x.get('lower_bound_px',0)>1 for x in bounds),'candidate':asset(rp),'qa':asset(q['evidence_file']),'quality_failures':q['failures'],'rehashed_XML_and_actual_native_PNG':True}

def main():
 import compiler_plantuml_natural_candidate_v10 as c
 owner=W/c.VERSION/'release_controls'/uuid.uuid4().hex;owner.mkdir(parents=True);configuration=c.configuration();(owner/'plan.json').write_bytes(c.raw({'source_program':asset(__file__),'ids':IDS,'source_already_consumed':True,'negative_variants':NEGATIVES,'positive_workers':2,'negative_workers':2,'configuration':configuration,'model_calls':0,'new_heldout_consumed':0}));print(json.dumps({'owner':str(owner),'positive_cases':2,'negative_cases':7}),flush=True);positives=[];negatives=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
  for row in executor.map(positive,[(identifier,str(owner)) for identifier in IDS]):positives.append(row);(owner/'positive_progress.json').write_bytes(c.raw(positives));print(json.dumps(row),flush=True)
 good=[r for r in positives if (r.get('full_quality') or {}).get('ok')]
 if good:
  with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
   for row in executor.map(negative,[(good[0]['record']['file'],name) for name in NEGATIVES]):negatives.append(row);(owner/'negative_progress.json').write_bytes(c.raw(negatives));print(json.dumps(row),flush=True)
 unchanged=c.configuration()==configuration;passed=bool(good) and len(negatives)==7 and all(r['rejected'] and r['fresh_source_rejected'] for r in negatives) and next((r['full_closed_paint_lower_bound_exceeds_one_pixel'] for r in negatives if r['name']=='oversized_native_marker'),False) and unchanged and all(r['canonical_unchanged'] for r in positives);report={'schema':'plantuml_textlength_full_source_label_release_controls_v1','configuration':configuration,'configuration_unchanged':unchanged,'positives':positives,'negatives':negatives,'passed':passed,'source_cases':2,'full_quality_positives':len(good),'model_calls':0,'new_heldout_consumed':0,'canonical_mutations':0,'no_validation_reservation_or_mass_dispatch':True};(owner/'report.json').write_bytes(c.raw(report));print(json.dumps({'report':str(owner/'report.json'),'passed':passed,'full_quality_positives':len(good),'negatives':len(negatives)}),flush=True)

if __name__=='__main__':main()
